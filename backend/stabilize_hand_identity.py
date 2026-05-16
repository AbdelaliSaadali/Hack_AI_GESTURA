#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)


def is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def is_point(p: Any) -> bool:
    return isinstance(p, (list, tuple)) and len(p) >= 2 and all(is_number(v) for v in p[:2])


def near_zero_point(p: Any, eps: float = 1e-6) -> bool:
    if not is_point(p):
        return True
    total = sum(abs(float(v)) for v in p[:3])
    return total <= eps


def point_dist_xy(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[float]:
    if a is None or b is None or not is_point(a) or not is_point(b):
        return None
    return math.sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2)


def copy_hand(hand: Any) -> Any:
    return copy.deepcopy(hand)


def hand_present(hand: Any) -> bool:
    if not isinstance(hand, dict):
        return False
    for value in hand.values():
        if is_point(value) and not near_zero_point(value):
            return True
    return False


def hand_wrist(hand: Any) -> Optional[List[float]]:
    if not isinstance(hand, dict):
        return None
    wrist = hand.get("wrist")
    if is_point(wrist) and not near_zero_point(wrist):
        return [float(v) for v in wrist]
    for value in hand.values():
        if is_point(value) and not near_zero_point(value):
            return [float(v) for v in value]
    return None


def find_frames_container(data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    for key in ("frames", "clean_frames"):
        value = data.get(key)
        if isinstance(value, list):
            return value, key
    raise RuntimeError("Could not find frames under 'frames' or 'clean_frames'")


def get_pose_wrist(frame: Dict[str, Any], side: str) -> Optional[List[float]]:
    pose = frame.get("pose")
    key = "left_wrist" if side == "left" else "right_wrist"
    idx = 15 if side == "left" else 16

    if isinstance(pose, dict):
        p = pose.get(key)
        if is_point(p) and not near_zero_point(p):
            return [float(v) for v in p]

    if isinstance(pose, list) and len(pose) > idx:
        p = pose[idx]
        if is_point(p) and not near_zero_point(p):
            return [float(v) for v in p]

    for container_name in ("rig", "rig_points", "joints", "points", "named_points"):
        container = frame.get(container_name)
        if isinstance(container, dict):
            for k in (
                key,
                f"rig:{key}",
                f"rig_{key}",
            ):
                p = container.get(k)
                if is_point(p) and not near_zero_point(p):
                    return [float(v) for v in p]

    return None


def get_body_scale(frame: Dict[str, Any]) -> float:
    pose = frame.get("pose")

    if isinstance(pose, dict):
        ls = pose.get("left_shoulder")
        rs = pose.get("right_shoulder")
        if is_point(ls) and is_point(rs) and not near_zero_point(ls) and not near_zero_point(rs):
            d = point_dist_xy(ls, rs)
            if d and d > 1e-6:
                return max(d, 1e-3)

    if isinstance(pose, list) and len(pose) > 12:
        ls = pose[11]
        rs = pose[12]
        if is_point(ls) and is_point(rs) and not near_zero_point(ls) and not near_zero_point(rs):
            d = point_dist_xy(ls, rs)
            if d and d > 1e-6:
                return max(d, 1e-3)

    lw = get_pose_wrist(frame, "left")
    rw = get_pose_wrist(frame, "right")
    d = point_dist_xy(lw, rw)
    if d and d > 1e-6:
        return max(d, 1e-3)

    return 0.25


def candidate_hands(frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for slot in ("left", "right"):
        hand = frame.get(f"{slot}_hand")
        if hand_present(hand):
            out.append(
                {
                    "slot": slot,
                    "hand": copy_hand(hand),
                    "wrist": hand_wrist(hand),
                }
            )
    return out


def cost_for_side(
    candidate: Dict[str, Any],
    target_side: str,
    frame: Dict[str, Any],
    prev_wrist: Optional[List[float]],
    pose_weight: float,
    prev_weight: float,
    slot_penalty: float,
) -> float:
    wrist = candidate["wrist"]
    scale = get_body_scale(frame)
    total = 0.0

    target_pose = get_pose_wrist(frame, target_side)
    d_pose = point_dist_xy(wrist, target_pose)
    total += pose_weight * ((d_pose / scale) if d_pose is not None else 0.75)

    d_prev = point_dist_xy(wrist, prev_wrist)
    if d_prev is not None:
        total += prev_weight * (d_prev / scale)

    if candidate["slot"] != target_side:
        total += slot_penalty

    return total


def choose_assignment(
    frame: Dict[str, Any],
    prev_left: Optional[List[float]],
    prev_right: Optional[List[float]],
    pose_weight: float,
    prev_weight: float,
    slot_penalty: float,
    keep_margin: float,
) -> Tuple[Any, Any, bool]:
    candidates = candidate_hands(frame)

    if not candidates:
        return {}, {}, False

    if len(candidates) == 1:
        c = candidates[0]
        left_cost = cost_for_side(c, "left", frame, prev_left, pose_weight, prev_weight, slot_penalty)
        right_cost = cost_for_side(c, "right", frame, prev_right, pose_weight, prev_weight, slot_penalty)

        original_side = c["slot"]
        if abs(left_cost - right_cost) <= keep_margin:
            target = original_side
        else:
            target = "left" if left_cost < right_cost else "right"

        return (
            copy_hand(c["hand"]) if target == "left" else {},
            copy_hand(c["hand"]) if target == "right" else {},
            target != original_side,
        )

    a, b = candidates[0], candidates[1]

    keep_cost = (
        cost_for_side(a, "left", frame, prev_left, pose_weight, prev_weight, slot_penalty)
        + cost_for_side(b, "right", frame, prev_right, pose_weight, prev_weight, slot_penalty)
    )
    swap_cost = (
        cost_for_side(b, "left", frame, prev_left, pose_weight, prev_weight, slot_penalty)
        + cost_for_side(a, "right", frame, prev_right, pose_weight, prev_weight, slot_penalty)
    )

    if abs(keep_cost - swap_cost) <= keep_margin:
        return copy_hand(frame.get("left_hand", {})), copy_hand(frame.get("right_hand", {})), False

    if keep_cost < swap_cost:
        return copy_hand(a["hand"]), copy_hand(b["hand"]), False

    return copy_hand(b["hand"]), copy_hand(a["hand"]), True


def translate_hand_to_wrist(hand: Any, target_wrist: Optional[List[float]], wrist_lock: float) -> Any:
    if not hand_present(hand):
        return {}
    src_wrist = hand_wrist(hand)
    if src_wrist is None or target_wrist is None:
        return hand

    out = copy_hand(hand)
    dims = min(len(src_wrist), len(target_wrist), 3)
    delta = [(float(target_wrist[i]) - float(src_wrist[i])) * wrist_lock for i in range(dims)]

    for key, value in out.items():
        if is_point(value):
            new_point = list(value)
            for i in range(min(len(new_point), dims)):
                new_point[i] = float(new_point[i]) + delta[i]
            out[key] = new_point

    return out


def update_tracking_memory(
    prev_wrist: Optional[List[float]],
    prev_age: int,
    current_wrist: Optional[List[float]],
    max_track_gap: int,
) -> Tuple[Optional[List[float]], int]:
    if current_wrist is not None:
        return current_wrist, 0
    if prev_wrist is None:
        return None, max_track_gap + 1
    new_age = prev_age + 1
    if new_age > max_track_gap:
        return None, new_age
    return prev_wrist, new_age


def stabilize(data: Dict[str, Any], args: argparse.Namespace) -> Tuple[Dict[str, Any], int]:
    out = copy.deepcopy(data)
    frames, _ = find_frames_container(out)

    prev_left_wrist = None
    prev_right_wrist = None
    prev_left_age = args.max_track_gap + 1
    prev_right_age = args.max_track_gap + 1

    total_swapped = 0

    for frame in frames:
        if not isinstance(frame, dict):
            continue

        prev_left_for_cost = prev_left_wrist if prev_left_age <= args.max_track_gap else None
        prev_right_for_cost = prev_right_wrist if prev_right_age <= args.max_track_gap else None

        new_left, new_right, swapped = choose_assignment(
            frame=frame,
            prev_left=prev_left_for_cost,
            prev_right=prev_right_for_cost,
            pose_weight=args.pose_weight,
            prev_weight=args.prev_weight,
            slot_penalty=args.slot_penalty,
            keep_margin=args.keep_margin,
        )

        frame["left_hand"] = new_left
        frame["right_hand"] = new_right

        if args.attach_hands:
            left_target = get_pose_wrist(frame, "left")
            right_target = get_pose_wrist(frame, "right")

            if hand_present(frame["left_hand"]) and left_target is not None:
                frame["left_hand"] = translate_hand_to_wrist(frame["left_hand"], left_target, args.wrist_lock)

            if hand_present(frame["right_hand"]) and right_target is not None:
                frame["right_hand"] = translate_hand_to_wrist(frame["right_hand"], right_target, args.wrist_lock)

        left_out_wrist = hand_wrist(frame.get("left_hand"))
        right_out_wrist = hand_wrist(frame.get("right_hand"))

        prev_left_wrist, prev_left_age = update_tracking_memory(
            prev_left_wrist, prev_left_age, left_out_wrist, args.max_track_gap
        )
        prev_right_wrist, prev_right_age = update_tracking_memory(
            prev_right_wrist, prev_right_age, right_out_wrist, args.max_track_gap
        )

        if swapped:
            total_swapped += 1

    return out, total_swapped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_json", required=True)
    parser.add_argument("--output_json", required=True)
    parser.add_argument("--attach_hands", action="store_true")
    parser.add_argument("--wrist_lock", type=float, default=1.0)
    parser.add_argument("--pose_weight", type=float, default=1.0)
    parser.add_argument("--prev_weight", type=float, default=1.6)
    parser.add_argument("--slot_penalty", type=float, default=0.08)
    parser.add_argument("--keep_margin", type=float, default=0.04)
    parser.add_argument("--max_track_gap", type=int, default=6)
    args = parser.parse_args()

    input_path = Path(args.input_json)
    output_path = Path(args.output_json)

    data = load_json(input_path)
    result, total_swapped = stabilize(data, args)
    save_json(output_path, result)

    frames, _ = find_frames_container(result)
    print(f"[OK] {input_path} -> {output_path}")
    print(f"[SUMMARY] frames_total={len(frames)} frames_reassigned={total_swapped} attach_hands={args.attach_hands}")


if __name__ == "__main__":
    main()