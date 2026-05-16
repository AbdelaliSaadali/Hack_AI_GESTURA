import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import cv2  # Optional, only used to estimate fps if available
except Exception:
    cv2 = None


POSE_NAMES = [
    "nose",
    "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear",
    "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_pinky", "right_pinky",
    "left_index", "right_index",
    "left_thumb", "right_thumb",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
    "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]

HAND_NAMES = [
    "wrist",
    "thumb_cmc", "thumb_mcp", "thumb_ip", "thumb_tip",
    "index_mcp", "index_pip", "index_dip", "index_tip",
    "middle_mcp", "middle_pip", "middle_dip", "middle_tip",
    "ring_mcp", "ring_pip", "ring_dip", "ring_tip",
    "pinky_mcp", "pinky_pip", "pinky_dip", "pinky_tip",
]

POSE_CONNECTIONS = [
    ["root", "spine"],
    ["spine", "chest"],
    ["chest", "neck"],
    ["neck", "head"],
    ["chest", "left_shoulder"],
    ["left_shoulder", "left_elbow"],
    ["left_elbow", "left_wrist"],
    ["chest", "right_shoulder"],
    ["right_shoulder", "right_elbow"],
    ["right_elbow", "right_wrist"],
    ["root", "left_hip"],
    ["root", "right_hip"],
]

HAND_CONNECTIONS = [
    ["wrist", "thumb_cmc"],
    ["thumb_cmc", "thumb_mcp"],
    ["thumb_mcp", "thumb_ip"],
    ["thumb_ip", "thumb_tip"],

    ["wrist", "index_mcp"],
    ["index_mcp", "index_pip"],
    ["index_pip", "index_dip"],
    ["index_dip", "index_tip"],

    ["wrist", "middle_mcp"],
    ["middle_mcp", "middle_pip"],
    ["middle_pip", "middle_dip"],
    ["middle_dip", "middle_tip"],

    ["wrist", "ring_mcp"],
    ["ring_mcp", "ring_pip"],
    ["ring_pip", "ring_dip"],
    ["ring_dip", "ring_tip"],

    ["wrist", "pinky_mcp"],
    ["pinky_mcp", "pinky_pip"],
    ["pinky_pip", "pinky_dip"],
    ["pinky_dip", "pinky_tip"],
]

LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_EAR = 7
RIGHT_EAR = 8
NOSE = 0


def deep_copy_points(points: List[List[float]]) -> List[List[float]]:
    return [[float(p[0]), float(p[1]), float(p[2])] for p in points]


def point_add(a: List[float], b: List[float]) -> List[float]:
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def point_sub(a: List[float], b: List[float]) -> List[float]:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def point_mul(a: List[float], s: float) -> List[float]:
    return [a[0] * s, a[1] * s, a[2] * s]


def point_lerp(a: List[float], b: List[float], t: float) -> List[float]:
    return [
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    ]


def midpoint(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[List[float]]:
    if a is None or b is None:
        return None
    return [(a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5]


def distance_2d(a: List[float], b: List[float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def distance_3d(a: List[float], b: List[float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def valid_pose(points: Any) -> bool:
    return isinstance(points, list) and len(points) >= len(POSE_NAMES)


def valid_hand(points: Any) -> bool:
    return isinstance(points, list) and len(points) == len(HAND_NAMES)


def normalize_point(
    point: List[float],
    center: List[float],
    scale: float,
    flip_y: bool = True,
) -> List[float]:
    x = (point[0] - center[0]) / scale
    y = (point[1] - center[1]) / scale
    z = point[2] / scale
    if flip_y:
        y = -y
    return [x, y, z]


def normalize_points(
    points: List[List[float]],
    center: List[float],
    scale: float,
    flip_y: bool = True,
) -> List[List[float]]:
    return [normalize_point(p, center, scale, flip_y=flip_y) for p in points]


def attach_hand_to_wrist(
    hand_points: Optional[List[List[float]]],
    wrist_point: Optional[List[float]],
    wrist_lock: float = 1.0,
) -> Optional[List[List[float]]]:
    if hand_points is None or wrist_point is None or not valid_hand(hand_points):
        return hand_points
    hand_root = hand_points[0]
    offset = point_mul(point_sub(wrist_point, hand_root), wrist_lock)
    return [point_add(p, offset) for p in hand_points]


def points_to_named_dict(
    points: Optional[List[List[float]]],
    names: List[str],
) -> Dict[str, Optional[List[float]]]:
    if not points:
        return {name: None for name in names}
    out: Dict[str, Optional[List[float]]] = {}
    for i, name in enumerate(names):
        if i < len(points):
            out[name] = [float(points[i][0]), float(points[i][1]), float(points[i][2])]
        else:
            out[name] = None
    return out


def deep_copy_optional_point_sequence(
    sequence: List[Optional[List[float]]],
) -> List[Optional[List[float]]]:
    return [[float(v[0]), float(v[1]), float(v[2])] for v in sequence if False]  # unreachable placeholder


def clone_vector(v: Optional[List[float]]) -> Optional[List[float]]:
    if v is None:
        return None
    return [float(v[0]), float(v[1]), float(v[2])]


def clone_scalar(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return float(v)


def interpolate_vector_sequence(
    sequence: List[Optional[List[float]]],
    max_gap: int,
    edge_gap: int,
) -> List[Optional[List[float]]]:
    result = [clone_vector(v) for v in sequence]
    valid_indices = [i for i, v in enumerate(result) if v is not None]
    if not valid_indices:
        return result

    first_valid = valid_indices[0]
    if first_valid > 0 and first_valid <= edge_gap:
        for i in range(first_valid):
            result[i] = clone_vector(result[first_valid])

    last_valid = valid_indices[-1]
    trailing_gap = len(result) - 1 - last_valid
    if trailing_gap > 0 and trailing_gap <= edge_gap:
        for i in range(last_valid + 1, len(result)):
            result[i] = clone_vector(result[last_valid])

    for left_idx, right_idx in zip(valid_indices[:-1], valid_indices[1:]):
        gap = right_idx - left_idx - 1
        if gap <= 0 or gap > max_gap:
            continue
        left = result[left_idx]
        right = result[right_idx]
        if left is None or right is None:
            continue
        for step in range(1, gap + 1):
            t = step / (gap + 1)
            result[left_idx + step] = point_lerp(left, right, t)

    return result


def interpolate_scalar_sequence(
    sequence: List[Optional[float]],
    max_gap: int,
    edge_gap: int,
) -> List[Optional[float]]:
    result = [clone_scalar(v) for v in sequence]
    valid_indices = [i for i, v in enumerate(result) if v is not None]
    if not valid_indices:
        return result

    first_valid = valid_indices[0]
    if first_valid > 0 and first_valid <= edge_gap:
        for i in range(first_valid):
            result[i] = clone_scalar(result[first_valid])

    last_valid = valid_indices[-1]
    trailing_gap = len(result) - 1 - last_valid
    if trailing_gap > 0 and trailing_gap <= edge_gap:
        for i in range(last_valid + 1, len(result)):
            result[i] = clone_scalar(result[last_valid])

    for left_idx, right_idx in zip(valid_indices[:-1], valid_indices[1:]):
        gap = right_idx - left_idx - 1
        if gap <= 0 or gap > max_gap:
            continue
        left = result[left_idx]
        right = result[right_idx]
        if left is None or right is None:
            continue
        for step in range(1, gap + 1):
            t = step / (gap + 1)
            result[left_idx + step] = left + (right - left) * t

    return result


def smooth_vector_sequence(
    sequence: List[Optional[List[float]]],
    window: int,
) -> List[Optional[List[float]]]:
    if window <= 0:
        return [clone_vector(v) for v in sequence]

    result: List[Optional[List[float]]] = []
    n = len(sequence)

    for i in range(n):
        values: List[List[float]] = []
        for j in range(max(0, i - window), min(n, i + window + 1)):
            if sequence[j] is not None:
                values.append(sequence[j])  # type: ignore[arg-type]
        if not values:
            result.append(None)
            continue
        result.append([
            sum(v[0] for v in values) / len(values),
            sum(v[1] for v in values) / len(values),
            sum(v[2] for v in values) / len(values),
        ])
    return result


def smooth_scalar_sequence(
    sequence: List[Optional[float]],
    window: int,
) -> List[Optional[float]]:
    if window <= 0:
        return [clone_scalar(v) for v in sequence]

    result: List[Optional[float]] = []
    n = len(sequence)

    for i in range(n):
        values: List[float] = []
        for j in range(max(0, i - window), min(n, i + window + 1)):
            if sequence[j] is not None:
                values.append(sequence[j])  # type: ignore[arg-type]
        if not values:
            result.append(None)
            continue
        result.append(sum(values) / len(values))
    return result


def interpolate_hand_sequence(
    sequence: List[Optional[List[List[float]]]],
    max_hand_gap: int,
    edge_hand_gap: int,
) -> List[Optional[List[List[float]]]]:
    """
    Fill short gaps in a hand sequence.
    - leading/trailing gaps up to edge_hand_gap are copied from nearest valid frame
    - internal gaps up to max_hand_gap are linearly interpolated
    """
    result: List[Optional[List[List[float]]]] = [
        deep_copy_points(s) if s is not None else None for s in sequence
    ]

    valid_indices = [i for i, s in enumerate(result) if s is not None]
    if not valid_indices:
        return result

    first_valid = valid_indices[0]
    if first_valid > 0 and first_valid <= edge_hand_gap:
        for i in range(first_valid):
            result[i] = deep_copy_points(result[first_valid])  # type: ignore[arg-type]

    last_valid = valid_indices[-1]
    trailing_gap = len(result) - 1 - last_valid
    if trailing_gap > 0 and trailing_gap <= edge_hand_gap:
        for i in range(last_valid + 1, len(result)):
            result[i] = deep_copy_points(result[last_valid])  # type: ignore[arg-type]

    for left_idx, right_idx in zip(valid_indices[:-1], valid_indices[1:]):
        gap = right_idx - left_idx - 1
        if gap <= 0 or gap > max_hand_gap:
            continue

        left_points = result[left_idx]
        right_points = result[right_idx]
        if left_points is None or right_points is None:
            continue

        for step in range(1, gap + 1):
            t = step / (gap + 1)
            interp_points = []
            for lp, rp in zip(left_points, right_points):
                interp_points.append(point_lerp(lp, rp, t))
            result[left_idx + step] = interp_points

    return result


def smooth_landmark_sequence(
    sequence: List[Optional[List[List[float]]]],
    window: int,
) -> List[Optional[List[List[float]]]]:
    if window <= 0:
        return [deep_copy_points(s) if s is not None else None for s in sequence]

    result: List[Optional[List[List[float]]]] = []
    n = len(sequence)

    for i in range(n):
        if sequence[i] is None:
            result.append(None)
            continue

        point_count = len(sequence[i])  # type: ignore[arg-type]
        accum = [[0.0, 0.0, 0.0] for _ in range(point_count)]
        counts = [0] * point_count

        for j in range(max(0, i - window), min(n, i + window + 1)):
            frame_points = sequence[j]
            if frame_points is None or len(frame_points) != point_count:
                continue
            for pidx, point in enumerate(frame_points):
                accum[pidx][0] += point[0]
                accum[pidx][1] += point[1]
                accum[pidx][2] += point[2]
                counts[pidx] += 1

        smoothed_points: List[List[float]] = []
        for pidx in range(point_count):
            c = counts[pidx]
            if c <= 0:
                smoothed_points.append(sequence[i][pidx])  # type: ignore[index]
            else:
                smoothed_points.append([
                    accum[pidx][0] / c,
                    accum[pidx][1] / c,
                    accum[pidx][2] / c,
                ])
        result.append(smoothed_points)

    return result


def smooth_pose_sequence(
    sequence: List[Optional[List[List[float]]]],
    window: int,
) -> List[Optional[List[List[float]]]]:
    return smooth_landmark_sequence(sequence, window)


def hand_root_distance(
    hand_a: Optional[List[List[float]]],
    hand_b: Optional[List[List[float]]],
) -> Optional[float]:
    if hand_a is None or hand_b is None or not hand_a or not hand_b:
        return None
    return distance_3d(hand_a[0], hand_b[0])


def reject_hand_outliers(
    sequence: List[Optional[List[List[float]]]],
    jump_threshold: float,
) -> Tuple[List[Optional[List[List[float]]]], int]:
    """
    Mark isolated hand detections as missing when the hand root jumps sharply
    relative to both neighbors, while the neighbors remain mutually consistent.
    """
    if jump_threshold <= 0:
        return [deep_copy_points(s) if s is not None else None for s in sequence], 0

    result = [deep_copy_points(s) if s is not None else None for s in sequence]
    rejected = 0

    for i in range(1, len(sequence) - 1):
        prev_points = sequence[i - 1]
        curr_points = sequence[i]
        next_points = sequence[i + 1]

        if prev_points is None or curr_points is None or next_points is None:
            continue

        d_prev = hand_root_distance(curr_points, prev_points)
        d_next = hand_root_distance(curr_points, next_points)
        d_bridge = hand_root_distance(prev_points, next_points)

        if d_prev is None or d_next is None or d_bridge is None:
            continue

        if d_prev > jump_threshold and d_next > jump_threshold and d_bridge < jump_threshold:
            result[i] = None
            rejected += 1

    return result, rejected


def derive_fps(video_path: Optional[str]) -> Optional[float]:
    if video_path is None or cv2 is None:
        return None
    path = Path(video_path)
    if not path.exists():
        return None
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if fps and fps > 0:
        return float(fps)
    return None


def derive_video_id(path_like: Optional[str]) -> Optional[str]:
    if not path_like:
        return None
    return Path(path_like).stem


def iter_manifest_entries(data: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            yield from iter_manifest_entries(item)
        return

    if not isinstance(data, dict):
        return

    if "instances" in data and isinstance(data["instances"], list):
        parent = {k: v for k, v in data.items() if k != "instances"}
        for inst in data["instances"]:
            if not isinstance(inst, dict):
                continue
            merged = dict(parent)
            merged.update(inst)
            yield merged
        return

    if "video_id" in data or "gloss" in data or "video_path" in data:
        yield data
        return

    for value in data.values():
        yield from iter_manifest_entries(value)


def load_manifest_lookup(manifest_path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not manifest_path:
        return {}

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lookup: Dict[str, Dict[str, Any]] = {}
    for entry in iter_manifest_entries(data):
        raw_video_id = entry.get("video_id")
        video_path = entry.get("video_path") or entry.get("video") or entry.get("url")

        video_id = None
        if raw_video_id is not None:
            video_id = str(raw_video_id).strip()
        if not video_id and video_path:
            video_id = derive_video_id(str(video_path))

        if video_id:
            lookup[video_id] = entry

    return lookup


def trim_frames_by_manifest(
    frames: List[Dict[str, Any]],
    manifest_entry: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Optional[int]]]:
    if not manifest_entry:
        return frames, {"frame_start": None, "frame_end": None}

    frame_start = manifest_entry.get("frame_start")
    frame_end = manifest_entry.get("frame_end")

    if frame_start is None and frame_end is None:
        return frames, {"frame_start": None, "frame_end": None}

    start_idx = 0
    end_idx = len(frames)

    try:
        if frame_start is not None:
            start_idx = max(0, int(frame_start) - 1)
    except Exception:
        start_idx = 0

    try:
        if frame_end is not None and int(frame_end) > 0:
            end_idx = min(len(frames), int(frame_end))
    except Exception:
        end_idx = len(frames)

    if start_idx >= end_idx:
        return frames, {"frame_start": None, "frame_end": None}

    return frames[start_idx:end_idx], {
        "frame_start": start_idx + 1,
        "frame_end": end_idx,
    }


def build_rig_from_pose(pose_named: Dict[str, Optional[List[float]]]) -> Dict[str, Optional[List[float]]]:
    left_shoulder = pose_named.get("left_shoulder")
    right_shoulder = pose_named.get("right_shoulder")
    left_hip = pose_named.get("left_hip")
    right_hip = pose_named.get("right_hip")
    left_ear = pose_named.get("left_ear")
    right_ear = pose_named.get("right_ear")
    nose = pose_named.get("nose")

    hip_center = midpoint(left_hip, right_hip)
    shoulder_center = midpoint(left_shoulder, right_shoulder)

    root = hip_center
    chest = shoulder_center
    spine = midpoint(root, chest) if root is not None and chest is not None else None
    neck = chest

    if left_ear is not None and right_ear is not None:
        head = midpoint(left_ear, right_ear)
    else:
        head = nose

    return {
        "root": root,
        "spine": spine,
        "chest": chest,
        "neck": neck,
        "head": head,
        "left_hip": left_hip,
        "right_hip": right_hip,
        "left_shoulder": left_shoulder,
        "right_shoulder": right_shoulder,
        "left_elbow": pose_named.get("left_elbow"),
        "right_elbow": pose_named.get("right_elbow"),
        "left_wrist": pose_named.get("left_wrist"),
        "right_wrist": pose_named.get("right_wrist"),
    }


def count_non_empty(sequence: List[Optional[List[List[float]]]]) -> int:
    return sum(1 for item in sequence if item is not None)


def compute_raw_normalization_basis(
    frames: List[Dict[str, Any]],
) -> Tuple[List[Optional[List[float]]], List[Optional[float]]]:
    centers: List[Optional[List[float]]] = []
    scales: List[Optional[float]] = []

    for frame in frames:
        pose_points = frame.get("pose")
        if valid_pose(pose_points):
            left_shoulder = pose_points[LEFT_SHOULDER]
            right_shoulder = pose_points[RIGHT_SHOULDER]
            center = midpoint(left_shoulder, right_shoulder)
            scale = distance_2d(left_shoulder, right_shoulder)
            if center is not None and scale > 1e-6:
                centers.append(center)
                scales.append(scale)
            else:
                centers.append(None)
                scales.append(None)
        else:
            centers.append(None)
            scales.append(None)

    return centers, scales


def fill_basis_sequences(
    centers: List[Optional[List[float]]],
    scales: List[Optional[float]],
    edge_gap: int,
) -> Tuple[List[Optional[List[float]]], List[Optional[float]]]:
    max_gap = max(1, len(centers))
    filled_centers = interpolate_vector_sequence(centers, max_gap=max_gap, edge_gap=edge_gap)
    filled_scales = interpolate_scalar_sequence(scales, max_gap=max_gap, edge_gap=edge_gap)

    last_center: Optional[List[float]] = None
    last_scale: Optional[float] = None

    for i in range(len(filled_centers)):
        if filled_centers[i] is None and last_center is not None:
            filled_centers[i] = clone_vector(last_center)
        elif filled_centers[i] is not None:
            last_center = filled_centers[i]

        if filled_scales[i] is None and last_scale is not None:
            filled_scales[i] = clone_scalar(last_scale)
        elif filled_scales[i] is not None:
            last_scale = filled_scales[i]

    return filled_centers, filled_scales


def process_one_file(
    input_json: str,
    output_json: str,
    manifest_lookup: Dict[str, Dict[str, Any]],
    max_hand_gap: int,
    edge_hand_gap: int,
    hand_smoothing_window: int,
    pose_smoothing_window: int,
    basis_smoothing_window: int,
    hand_jump_threshold: float,
    reject_hand_jumps_enabled: bool,
    flip_y: bool,
    attach_hands: bool,
    wrist_lock: float,
    fps_override: Optional[float],
) -> None:
    with open(input_json, "r", encoding="utf-8") as f:
        raw = json.load(f)

    raw_frames = raw.get("frames", [])
    if not isinstance(raw_frames, list) or not raw_frames:
        raise RuntimeError(f"No frames found in {input_json}")

    video_path = raw.get("video_path")
    video_id = derive_video_id(video_path) or derive_video_id(input_json)
    manifest_entry = manifest_lookup.get(video_id, {}) if video_id else {}

    trimmed_frames, trim_info = trim_frames_by_manifest(raw_frames, manifest_entry)

    raw_centers, raw_scales = compute_raw_normalization_basis(trimmed_frames)
    filled_centers, filled_scales = fill_basis_sequences(raw_centers, raw_scales, edge_gap=max(2, edge_hand_gap))
    smooth_centers = smooth_vector_sequence(filled_centers, basis_smoothing_window)
    smooth_scales = smooth_scalar_sequence(filled_scales, basis_smoothing_window)

    pose_raw_sequence: List[Optional[List[List[float]]]] = []
    left_raw_sequence: List[Optional[List[List[float]]]] = []
    right_raw_sequence: List[Optional[List[List[float]]]] = []

    pose_normalized_raw: List[Optional[List[List[float]]]] = []
    left_normalized_raw: List[Optional[List[List[float]]]] = []
    right_normalized_raw: List[Optional[List[List[float]]]] = []

    pose_detected_frames = 0

    for i, frame in enumerate(trimmed_frames):
        pose_points = frame.get("pose")
        left_points = frame.get("left_hand")
        right_points = frame.get("right_hand")

        pose_raw_sequence.append(deep_copy_points(pose_points) if valid_pose(pose_points) else None)
        left_raw_sequence.append(deep_copy_points(left_points) if valid_hand(left_points) else None)
        right_raw_sequence.append(deep_copy_points(right_points) if valid_hand(right_points) else None)

        if valid_pose(pose_points):
            pose_detected_frames += 1

        center = smooth_centers[i]
        scale = smooth_scales[i]

        if center is None or scale is None or scale <= 1e-6:
            pose_normalized_raw.append(None)
            left_normalized_raw.append(None)
            right_normalized_raw.append(None)
            continue

        pose_normalized_raw.append(
            normalize_points(pose_points, center, scale, flip_y=flip_y) if valid_pose(pose_points) else None
        )
        left_normalized_raw.append(
            normalize_points(left_points, center, scale, flip_y=flip_y) if valid_hand(left_points) else None
        )
        right_normalized_raw.append(
            normalize_points(right_points, center, scale, flip_y=flip_y) if valid_hand(right_points) else None
        )

    left_detected_raw = count_non_empty(left_raw_sequence)
    right_detected_raw = count_non_empty(right_raw_sequence)

    rejected_left = 0
    rejected_right = 0

    left_after_reject = [deep_copy_points(s) if s is not None else None for s in left_normalized_raw]
    right_after_reject = [deep_copy_points(s) if s is not None else None for s in right_normalized_raw]

    if reject_hand_jumps_enabled:
        left_after_reject, rejected_left = reject_hand_outliers(left_after_reject, hand_jump_threshold)
        right_after_reject, rejected_right = reject_hand_outliers(right_after_reject, hand_jump_threshold)

    left_after_fill = interpolate_hand_sequence(
        left_after_reject,
        max_hand_gap=max_hand_gap,
        edge_hand_gap=edge_hand_gap,
    )
    right_after_fill = interpolate_hand_sequence(
        right_after_reject,
        max_hand_gap=max_hand_gap,
        edge_hand_gap=edge_hand_gap,
    )

    pose_after_smooth = smooth_pose_sequence(pose_normalized_raw, pose_smoothing_window)
    left_after_smooth = smooth_landmark_sequence(left_after_fill, hand_smoothing_window)
    right_after_smooth = smooth_landmark_sequence(right_after_fill, hand_smoothing_window)

    output_frames: List[Dict[str, Any]] = []

    left_detected_after_reject = count_non_empty(left_after_reject)
    right_detected_after_reject = count_non_empty(right_after_reject)
    left_detected_after_fill = count_non_empty(left_after_fill)
    right_detected_after_fill = count_non_empty(right_after_fill)

    for i, frame in enumerate(trimmed_frames):
        pose_norm = pose_after_smooth[i]
        left_norm = left_after_smooth[i]
        right_norm = right_after_smooth[i]

        if attach_hands and pose_norm is not None:
            left_wrist = pose_norm[LEFT_WRIST]
            right_wrist = pose_norm[RIGHT_WRIST]
            left_norm = attach_hand_to_wrist(left_norm, left_wrist, wrist_lock=wrist_lock)
            right_norm = attach_hand_to_wrist(right_norm, right_wrist, wrist_lock=wrist_lock)

        pose_named = points_to_named_dict(pose_norm, POSE_NAMES) if pose_norm is not None else {name: None for name in POSE_NAMES}
        left_hand_named = points_to_named_dict(left_norm, HAND_NAMES) if left_norm is not None else {name: None for name in HAND_NAMES}
        right_hand_named = points_to_named_dict(right_norm, HAND_NAMES) if right_norm is not None else {name: None for name in HAND_NAMES}

        rig = build_rig_from_pose(pose_named)

        output_frames.append({
            "frame_index": i,
            "rig": rig,
            "pose": pose_named,
            "left_hand": left_hand_named,
            "right_hand": right_hand_named,
            "flags": {
                "has_pose_raw": pose_raw_sequence[i] is not None,
                "has_left_hand_raw": left_raw_sequence[i] is not None,
                "has_right_hand_raw": right_raw_sequence[i] is not None,
                "has_left_hand_after_reject": left_after_reject[i] is not None,
                "has_right_hand_after_reject": right_after_reject[i] is not None,
                "has_left_hand_after_fill": left_after_fill[i] is not None,
                "has_right_hand_after_fill": right_after_fill[i] is not None,
                "left_hand_rejected_as_outlier": left_raw_sequence[i] is not None and left_after_reject[i] is None,
                "right_hand_rejected_as_outlier": right_raw_sequence[i] is not None and right_after_reject[i] is None,
                "left_hand_filled": left_raw_sequence[i] is None and left_after_fill[i] is not None,
                "right_hand_filled": right_raw_sequence[i] is None and right_after_fill[i] is not None,
            }
        })

    fps = fps_override if fps_override is not None else derive_fps(video_path)
    if fps is None:
        fps = 30.0

    out = {
        "schema_version": 2,
        "video_id": video_id,
        "video_path": video_path,
        "gloss": manifest_entry.get("gloss"),
        "split": manifest_entry.get("split"),
        "instance_id": manifest_entry.get("instance_id"),
        "fps": fps,
        "frame_count": len(output_frames),
        "source_trim": trim_info,
        "normalization": {
            "origin": "shoulder_midpoint",
            "scale": "shoulder_width",
            "flip_y": flip_y,
            "basis_smoothing_window": basis_smoothing_window,
            "pose_smoothing_window": pose_smoothing_window,
            "hand_smoothing_window": hand_smoothing_window,
            "attach_hands_to_pose_wrists": attach_hands,
            "wrist_lock": wrist_lock,
            "max_hand_gap_filled": max_hand_gap,
            "edge_hand_gap_filled": edge_hand_gap,
            "reject_hand_jumps": reject_hand_jumps_enabled,
            "hand_jump_threshold": hand_jump_threshold,
        },
        "landmark_names": {
            "pose": POSE_NAMES,
            "hand": HAND_NAMES,
        },
        "connections": {
            "pose": POSE_CONNECTIONS,
            "left_hand": HAND_CONNECTIONS,
            "right_hand": HAND_CONNECTIONS,
        },
        "frames": output_frames,
        "summary": {
            "pose_detected_frames_raw": pose_detected_frames,
            "left_hand_detected_frames_raw": left_detected_raw,
            "right_hand_detected_frames_raw": right_detected_raw,
            "left_hand_rejected_outliers": rejected_left,
            "right_hand_rejected_outliers": rejected_right,
            "left_hand_detected_frames_after_reject": left_detected_after_reject,
            "right_hand_detected_frames_after_reject": right_detected_after_reject,
            "left_hand_detected_frames_after_fill": left_detected_after_fill,
            "right_hand_detected_frames_after_fill": right_detected_after_fill,
        },
    }

    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] {input_json} -> {output_json}")
    print(
        "[SUMMARY]",
        f"frames={out['frame_count']}",
        f"pose_raw={out['summary']['pose_detected_frames_raw']}",
        f"left_raw={out['summary']['left_hand_detected_frames_raw']}",
        f"right_raw={out['summary']['right_hand_detected_frames_raw']}",
        f"left_rejected={out['summary']['left_hand_rejected_outliers']}",
        f"right_rejected={out['summary']['right_hand_rejected_outliers']}",
        f"left_after_reject={out['summary']['left_hand_detected_frames_after_reject']}",
        f"right_after_reject={out['summary']['right_hand_detected_frames_after_reject']}",
        f"left_after_fill={out['summary']['left_hand_detected_frames_after_fill']}",
        f"right_after_fill={out['summary']['right_hand_detected_frames_after_fill']}",
    )


def process_directory(
    input_dir: str,
    output_dir: str,
    manifest_lookup: Dict[str, Dict[str, Any]],
    max_hand_gap: int,
    edge_hand_gap: int,
    hand_smoothing_window: int,
    pose_smoothing_window: int,
    basis_smoothing_window: int,
    hand_jump_threshold: float,
    reject_hand_jumps_enabled: bool,
    flip_y: bool,
    attach_hands: bool,
    wrist_lock: float,
    fps_override: Optional[float],
) -> None:
    in_dir = Path(input_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.json"))
    if not files:
        raise RuntimeError(f"No .json files found in {input_dir}")

    for input_file in files:
        output_file = out_dir / input_file.name
        process_one_file(
            input_json=str(input_file),
            output_json=str(output_file),
            manifest_lookup=manifest_lookup,
            max_hand_gap=max_hand_gap,
            edge_hand_gap=edge_hand_gap,
            hand_smoothing_window=hand_smoothing_window,
            pose_smoothing_window=pose_smoothing_window,
            basis_smoothing_window=basis_smoothing_window,
            hand_jump_threshold=hand_jump_threshold,
            reject_hand_jumps_enabled=reject_hand_jumps_enabled,
            flip_y=flip_y,
            attach_hands=attach_hands,
            wrist_lock=wrist_lock,
            fps_override=fps_override,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a clean, normalized, rig-friendly skeleton JSON from extracted MediaPipe landmarks."
    )

    parser.add_argument("--input_json", help="Path to one extracted landmark JSON file")
    parser.add_argument("--input_dir", help="Path to a folder of extracted landmark JSON files")
    parser.add_argument("--output_json", help="Output path for one cleaned skeleton JSON")
    parser.add_argument("--output_dir", help="Output folder for cleaned skeleton JSON files")
    parser.add_argument("--manifest", help="Optional WLASL_parsed_data.json path to enrich gloss metadata and apply frame trimming")

    parser.add_argument("--max_hand_gap", type=int, default=2, help="Interpolate internal hand gaps up to this many frames")
    parser.add_argument("--edge_hand_gap", type=int, default=2, help="Copy nearest hand frame into leading/trailing gaps up to this many frames")
    parser.add_argument("--hand_smoothing_window", type=int, default=2, help="Temporal smoothing window for hands")
    parser.add_argument("--pose_smoothing_window", type=int, default=1, help="Temporal smoothing window for pose")
    parser.add_argument("--basis_smoothing_window", type=int, default=2, help="Temporal smoothing window for normalization center/scale")
    parser.add_argument("--hand_jump_threshold", type=float, default=0.35, help="Reject isolated hand detections whose root jumps more than this normalized distance")

    parser.add_argument("--fps", type=float, default=None, help="Override fps instead of reading from video")
    parser.add_argument("--wrist_lock", type=float, default=1.0, help="0.0 keeps raw hand root, 1.0 snaps hand root fully to pose wrist")

    parser.add_argument("--no_reject_hand_jumps", action="store_true", help="Disable isolated hand outlier rejection")
    parser.add_argument("--no_flip_y", action="store_true", help="Keep image Y axis downward")
    parser.add_argument("--no_attach_hands", action="store_true", help="Do not attach hand root to pose wrist")

    args = parser.parse_args()

    single_mode = bool(args.input_json)
    dir_mode = bool(args.input_dir)

    if single_mode == dir_mode:
        raise SystemExit("Provide exactly one of --input_json or --input_dir")

    if single_mode and not args.output_json:
        raise SystemExit("--output_json is required with --input_json")

    if dir_mode and not args.output_dir:
        raise SystemExit("--output_dir is required with --input_dir")

    manifest_lookup = load_manifest_lookup(args.manifest)
    flip_y = not args.no_flip_y
    attach_hands = not args.no_attach_hands
    reject_hand_jumps_enabled = not args.no_reject_hand_jumps

    if single_mode:
        process_one_file(
            input_json=args.input_json,
            output_json=args.output_json,
            manifest_lookup=manifest_lookup,
            max_hand_gap=args.max_hand_gap,
            edge_hand_gap=args.edge_hand_gap,
            hand_smoothing_window=args.hand_smoothing_window,
            pose_smoothing_window=args.pose_smoothing_window,
            basis_smoothing_window=args.basis_smoothing_window,
            hand_jump_threshold=args.hand_jump_threshold,
            reject_hand_jumps_enabled=reject_hand_jumps_enabled,
            flip_y=flip_y,
            attach_hands=attach_hands,
            wrist_lock=args.wrist_lock,
            fps_override=args.fps,
        )
    else:
        process_directory(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            manifest_lookup=manifest_lookup,
            max_hand_gap=args.max_hand_gap,
            edge_hand_gap=args.edge_hand_gap,
            hand_smoothing_window=args.hand_smoothing_window,
            pose_smoothing_window=args.pose_smoothing_window,
            basis_smoothing_window=args.basis_smoothing_window,
            hand_jump_threshold=args.hand_jump_threshold,
            reject_hand_jumps_enabled=reject_hand_jumps_enabled,
            flip_y=flip_y,
            attach_hands=attach_hands,
            wrist_lock=args.wrist_lock,
            fps_override=args.fps,
        )


if __name__ == "__main__":
    main()