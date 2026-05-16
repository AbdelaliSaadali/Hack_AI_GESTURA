import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2


# ---------- Constants ----------
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_WRIST = 15
RIGHT_WRIST = 16

BGR = Tuple[int, int, int]
Point3 = List[float]
NamedPoints = Dict[str, Optional[Point3]]


# ---------- Basic math ----------
def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def vec_add(a: Point3, b: Point3) -> Point3:
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def vec_sub(a: Point3, b: Point3) -> Point3:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def vec_mul(a: Point3, s: float) -> Point3:
    return [a[0] * s, a[1] * s, a[2] * s]


def vec_dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vec_cross(a: Point3, b: Point3) -> Point3:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def vec_norm(a: Point3) -> float:
    return math.sqrt(max(1e-12, vec_dot(a, a)))


def vec_normalize(a: Point3) -> Point3:
    n = vec_norm(a)
    if n <= 1e-12:
        return [0.0, 0.0, 0.0]
    return [a[0] / n, a[1] / n, a[2] / n]


def distance_2d(a: Point3, b: Point3) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


def midpoint(a: Point3, b: Point3) -> Point3:
    return [(a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5]


# ---------- JSON helpers ----------
def load_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object in {p}")
    return data


def get_named_point(mapping: Any, name: str) -> Optional[Point3]:
    if not isinstance(mapping, dict):
        return None
    value = mapping.get(name)
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        z = float(value[2]) if len(value) > 2 and isinstance(value[2], (int, float)) else 0.0
        return [float(value[0]), float(value[1]), z]
    return None


def get_raw_point(points: Any, idx: int) -> Optional[Point3]:
    if not isinstance(points, list) or idx >= len(points):
        return None
    p = points[idx]
    if (
        isinstance(p, list)
        and len(p) >= 2
        and isinstance(p[0], (int, float))
        and isinstance(p[1], (int, float))
    ):
        z = float(p[2]) if len(p) > 2 and isinstance(p[2], (int, float)) else 0.0
        return [float(p[0]), float(p[1]), z]
    return None


# ---------- Projection / denormalization ----------
def recover_basis_from_raw_pose(raw_frame: Dict[str, Any]) -> Optional[Tuple[Point3, float]]:
    pose = raw_frame.get("pose")
    left_shoulder = get_raw_point(pose, LEFT_SHOULDER)
    right_shoulder = get_raw_point(pose, RIGHT_SHOULDER)
    if left_shoulder is None or right_shoulder is None:
        return None

    center = midpoint(left_shoulder, right_shoulder)
    scale = distance_2d(left_shoulder, right_shoulder)
    if scale <= 1e-8:
        return None
    return center, scale


def denormalize_clean_point(
    clean_point: Optional[Point3],
    basis_center: Point3,
    basis_scale: float,
    flip_y: bool,
) -> Optional[Point3]:
    if clean_point is None:
        return None

    # build_clean_skeleton used:
    # x = (raw_x - center_x) / scale
    # y = -(raw_y - center_y) / scale   when flip_y=True
    # z = raw_z / scale
    raw_x = clean_point[0] * basis_scale + basis_center[0]
    if flip_y:
        raw_y = basis_center[1] - clean_point[1] * basis_scale
    else:
        raw_y = clean_point[1] * basis_scale + basis_center[1]
    raw_z = clean_point[2] * basis_scale
    return [raw_x, raw_y, raw_z]


def perspective_project_to_pixels(
    point: Point3,
    anchor_xy: Tuple[float, float],
    anchor_z: float,
    width: int,
    height: int,
    perspective_strength: float,
    min_factor: float,
    max_factor: float,
) -> Tuple[int, int]:
    """
    point:
      x,y in raw image-normalized coordinates [roughly 0..1]
      z in denormalized normalized-units (same kind of scale used in clean build)
    """
    base_x = point[0]
    base_y = point[1]
    rel_z = point[2] - anchor_z

    # In MediaPipe-style coordinates here, more negative z is usually closer.
    # So closer points should get slightly larger displacement from the anchor.
    factor = 1.0 + (-rel_z) * perspective_strength
    factor = clamp(factor, min_factor, max_factor)

    proj_x = anchor_xy[0] + (base_x - anchor_xy[0]) * factor
    proj_y = anchor_xy[1] + (base_y - anchor_xy[1]) * factor

    px = int(round(proj_x * width))
    py = int(round(proj_y * height))
    return px, py


def depth_brightness(z: float, z_near: float, z_far: float) -> float:
    """
    Convert z to a brightness multiplier in [0.45, 1.0].
    More negative = closer = brighter.
    """
    if abs(z_far - z_near) < 1e-8:
        return 1.0
    t = (z - z_far) / (z_near - z_far)
    t = clamp(t, 0.0, 1.0)
    return lerp(0.45, 1.0, t)


def modulate_color(color: BGR, brightness: float) -> BGR:
    return (
        int(clamp(color[0] * brightness, 0, 255)),
        int(clamp(color[1] * brightness, 0, 255)),
        int(clamp(color[2] * brightness, 0, 255)),
    )


# ---------- Hand orientation ----------
def compute_palm_geometry(
    hand: NamedPoints,
    side: str,
) -> Optional[Tuple[Point3, Point3, Point3, Point3, float]]:
    wrist = get_named_point(hand, "wrist")
    index_mcp = get_named_point(hand, "index_mcp")
    pinky_mcp = get_named_point(hand, "pinky_mcp")
    middle_mcp = get_named_point(hand, "middle_mcp")

    if wrist is None or index_mcp is None or pinky_mcp is None or middle_mcp is None:
        return None

    palm_center = [
        (wrist[0] + index_mcp[0] + pinky_mcp[0] + middle_mcp[0]) / 4.0,
        (wrist[1] + index_mcp[1] + pinky_mcp[1] + middle_mcp[1]) / 4.0,
        (wrist[2] + index_mcp[2] + pinky_mcp[2] + middle_mcp[2]) / 4.0,
    ]

    index_vec = vec_sub(index_mcp, wrist)
    pinky_vec = vec_sub(pinky_mcp, wrist)
    middle_vec = vec_sub(middle_mcp, wrist)

    # Use handedness-aware cross order to keep the palm normal roughly consistent.
    if side == "left":
        palm_normal = vec_cross(index_vec, pinky_vec)
    else:
        palm_normal = vec_cross(pinky_vec, index_vec)

    palm_normal = vec_normalize(palm_normal)
    finger_axis = vec_normalize(middle_vec)

    hand_span = max(1e-6, distance_2d(index_mcp, pinky_mcp))
    return wrist, palm_center, palm_normal, finger_axis, hand_span


# ---------- Drawing ----------
def draw_text_block(frame: Any, lines: List[str], origin: Tuple[int, int]) -> None:
    x, y = origin
    for line in lines:
        cv2.putText(
            frame,
            line,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (20, 20, 20),
            2,
            lineType=cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            line,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (245, 245, 245),
            1,
            lineType=cv2.LINE_AA,
        )
        y += 24


def gather_visible_z_values(
    clean_frame: Dict[str, Any],
) -> List[float]:
    values: List[float] = []
    for section_name in ["rig", "pose", "left_hand", "right_hand"]:
        section = clean_frame.get(section_name, {})
        if isinstance(section, dict):
            for value in section.values():
                if (
                    isinstance(value, list)
                    and len(value) >= 3
                    and all(isinstance(v, (int, float)) for v in value[:3])
                ):
                    values.append(float(value[2]))
    return values


def draw_connection_list(
    frame: Any,
    mapping: NamedPoints,
    connections: List[List[str]],
    basis_center: Point3,
    basis_scale: float,
    flip_y: bool,
    width: int,
    height: int,
    anchor_xy: Tuple[float, float],
    anchor_z: float,
    perspective_strength: float,
    min_factor: float,
    max_factor: float,
    base_color: BGR,
    thickness: int,
    z_near: float,
    z_far: float,
) -> None:
    segments: List[Tuple[float, Tuple[int, int], Tuple[int, int], BGR, int]] = []

    for pair in connections:
        if len(pair) != 2:
            continue
        a = get_named_point(mapping, pair[0])
        b = get_named_point(mapping, pair[1])
        if a is None or b is None:
            continue

        a_denorm = denormalize_clean_point(a, basis_center, basis_scale, flip_y)
        b_denorm = denormalize_clean_point(b, basis_center, basis_scale, flip_y)
        if a_denorm is None or b_denorm is None:
            continue

        pa = perspective_project_to_pixels(
            a_denorm, anchor_xy, anchor_z, width, height,
            perspective_strength, min_factor, max_factor
        )
        pb = perspective_project_to_pixels(
            b_denorm, anchor_xy, anchor_z, width, height,
            perspective_strength, min_factor, max_factor
        )

        z_avg = (a[2] + b[2]) * 0.5
        brightness = depth_brightness(z_avg, z_near, z_far)
        color = modulate_color(base_color, brightness)
        thick = max(1, int(round(thickness * brightness)))
        segments.append((z_avg, pa, pb, color, thick))

    # Farther first, closer last.
    segments.sort(key=lambda item: item[0], reverse=True)

    for _, pa, pb, color, thick in segments:
        cv2.line(frame, pa, pb, color, thick, lineType=cv2.LINE_AA)


def draw_named_points(
    frame: Any,
    mapping: NamedPoints,
    basis_center: Point3,
    basis_scale: float,
    flip_y: bool,
    width: int,
    height: int,
    anchor_xy: Tuple[float, float],
    anchor_z: float,
    perspective_strength: float,
    min_factor: float,
    max_factor: float,
    base_color: BGR,
    radius: int,
    z_near: float,
    z_far: float,
    show_labels: bool = False,
    label_prefix: str = "",
) -> None:
    joints: List[Tuple[float, str, Tuple[int, int], BGR, int]] = []

    for name, value in mapping.items():
        p = get_named_point(mapping, name)
        if p is None:
            continue

        p_denorm = denormalize_clean_point(p, basis_center, basis_scale, flip_y)
        if p_denorm is None:
            continue

        px, py = perspective_project_to_pixels(
            p_denorm, anchor_xy, anchor_z, width, height,
            perspective_strength, min_factor, max_factor
        )

        brightness = depth_brightness(p[2], z_near, z_far)
        color = modulate_color(base_color, brightness)
        rad = max(1, int(round(radius * brightness)))
        joints.append((p[2], name, (px, py), color, rad))

    joints.sort(key=lambda item: item[0], reverse=True)

    for _, name, (px, py), color, rad in joints:
        cv2.circle(frame, (px, py), rad, color, -1, lineType=cv2.LINE_AA)
        if show_labels:
            cv2.putText(
                frame,
                f"{label_prefix}{name}",
                (px + 5, py - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                color,
                1,
                lineType=cv2.LINE_AA,
            )


def draw_palm_orientation(
    frame: Any,
    hand: NamedPoints,
    side: str,
    basis_center: Point3,
    basis_scale: float,
    flip_y: bool,
    width: int,
    height: int,
    anchor_xy: Tuple[float, float],
    anchor_z: float,
    perspective_strength: float,
    min_factor: float,
    max_factor: float,
    z_near: float,
    z_far: float,
    normal_length_factor: float,
) -> None:
    palm = compute_palm_geometry(hand, side)
    if palm is None:
        return

    wrist, palm_center, palm_normal, finger_axis, hand_span = palm
    base_len = max(0.015, hand_span * normal_length_factor)

    # Palm normal arrow
    palm_tip = vec_add(palm_center, vec_mul(palm_normal, base_len))
    # Finger direction arrow
    finger_tip = vec_add(palm_center, vec_mul(finger_axis, base_len))

    palm_center_d = denormalize_clean_point(palm_center, basis_center, basis_scale, flip_y)
    palm_tip_d = denormalize_clean_point(palm_tip, basis_center, basis_scale, flip_y)
    finger_tip_d = denormalize_clean_point(finger_tip, basis_center, basis_scale, flip_y)

    if palm_center_d is None or palm_tip_d is None or finger_tip_d is None:
        return

    p0 = perspective_project_to_pixels(
        palm_center_d, anchor_xy, anchor_z, width, height,
        perspective_strength, min_factor, max_factor
    )
    p1 = perspective_project_to_pixels(
        palm_tip_d, anchor_xy, anchor_z, width, height,
        perspective_strength, min_factor, max_factor
    )
    p2 = perspective_project_to_pixels(
        finger_tip_d, anchor_xy, anchor_z, width, height,
        perspective_strength, min_factor, max_factor
    )

    brightness = depth_brightness(palm_center[2], z_near, z_far)

    normal_color = modulate_color((220, 80, 220), brightness)   # magenta
    finger_color = modulate_color((80, 220, 220), brightness)   # cyan
    center_color = modulate_color((255, 255, 255), brightness)

    cv2.circle(frame, p0, 4, center_color, -1, lineType=cv2.LINE_AA)
    cv2.arrowedLine(frame, p0, p1, normal_color, 2, tipLength=0.28, line_type=cv2.LINE_AA)
    cv2.arrowedLine(frame, p0, p2, finger_color, 2, tipLength=0.28, line_type=cv2.LINE_AA)

    palm_facing_score = palm_normal[2]
    facing_text = f"{side[0].upper()} palm_z={palm_facing_score:+.2f}"
    cv2.putText(
        frame,
        facing_text,
        (p0[0] + 6, p0[1] + 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.35,
        normal_color,
        1,
        lineType=cv2.LINE_AA,
    )


def draw_raw_reference_points(
    frame: Any,
    raw_frame: Dict[str, Any],
    width: int,
    height: int,
    show_raw_pose: bool,
    show_raw_hands: bool,
) -> None:
    if show_raw_pose:
        pose = raw_frame.get("pose", [])
        if isinstance(pose, list):
            for p in pose:
                if (
                    isinstance(p, list)
                    and len(p) >= 2
                    and isinstance(p[0], (int, float))
                    and isinstance(p[1], (int, float))
                ):
                    px = int(round(float(p[0]) * width))
                    py = int(round(float(p[1]) * height))
                    cv2.circle(frame, (px, py), 1, (180, 180, 180), -1, lineType=cv2.LINE_AA)

    if show_raw_hands:
        for key, color in [("left_hand", (0, 255, 0)), ("right_hand", (0, 170, 255))]:
            hand = raw_frame.get(key, [])
            if isinstance(hand, list):
                for p in hand:
                    if (
                        isinstance(p, list)
                        and len(p) >= 2
                        and isinstance(p[0], (int, float))
                        and isinstance(p[1], (int, float))
                    ):
                        px = int(round(float(p[0]) * width))
                        py = int(round(float(p[1]) * height))
                        cv2.circle(frame, (px, py), 2, color, -1, lineType=cv2.LINE_AA)


# ---------- Frame alignment ----------
def get_trim_start_index(clean_data: Dict[str, Any]) -> int:
    source_trim = clean_data.get("source_trim", {})
    if not isinstance(source_trim, dict):
        return 0
    frame_start = source_trim.get("frame_start")
    try:
        if frame_start is None:
            return 0
        return max(0, int(frame_start) - 1)
    except Exception:
        return 0


def get_video_frame(cap: cv2.VideoCapture, frame_idx: int) -> Optional[Any]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    if not ok:
        return None
    return frame


# ---------- Main rendering ----------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overlay cleaned 3D-aware skeleton on the original video."
    )
    parser.add_argument("--video", required=True, help="Original source video path")
    parser.add_argument("--raw_json", required=True, help="Raw extracted landmarks JSON")
    parser.add_argument("--clean_json", required=True, help="Clean normalized skeleton JSON")
    parser.add_argument("--save", help="Optional output MP4 path")
    parser.add_argument("--no_window", action="store_true", help="Do not open an interactive window")
    parser.add_argument("--start_frame", type=int, default=0, help="Clean-frame index to start from")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    parser.add_argument("--loop", action="store_true", help="Loop playback")
    parser.add_argument("--perspective_strength", type=float, default=0.12, help="Depth perspective strength")
    parser.add_argument("--min_perspective_factor", type=float, default=0.78, help="Minimum perspective factor")
    parser.add_argument("--max_perspective_factor", type=float, default=1.40, help="Maximum perspective factor")
    parser.add_argument("--normal_length_factor", type=float, default=0.85, help="Palm/finger arrow length scale")
    parser.add_argument("--show_labels", action="store_true", help="Show joint labels")
    parser.add_argument("--show_raw_pose", action="store_true", help="Overlay raw pose dots for reference")
    parser.add_argument("--show_raw_hands", action="store_true", help="Overlay raw hand dots for reference")
    parser.add_argument("--show_pose_landmarks", action="store_true", help="Show cleaned pose landmarks in addition to rig")
    parser.add_argument("--alpha", type=float, default=1.0, help="Overlay alpha multiplier for drawings")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    video_path = Path(args.video)
    raw_json_path = Path(args.raw_json)
    clean_json_path = Path(args.clean_json)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not raw_json_path.exists():
        raise FileNotFoundError(f"Raw JSON not found: {raw_json_path}")
    if not clean_json_path.exists():
        raise FileNotFoundError(f"Clean JSON not found: {clean_json_path}")

    raw_data = load_json(str(raw_json_path))
    clean_data = load_json(str(clean_json_path))

    raw_frames = raw_data.get("frames", [])
    clean_frames = clean_data.get("frames", [])

    if not isinstance(raw_frames, list) or not raw_frames:
        raise RuntimeError("Raw JSON has no frames")
    if not isinstance(clean_frames, list) or not clean_frames:
        raise RuntimeError("Clean JSON has no frames")

    flip_y = bool(clean_data.get("normalization", {}).get("flip_y", True))
    pose_connections = clean_data.get("connections", {}).get("pose", [])
    left_hand_connections = clean_data.get("connections", {}).get("left_hand", [])
    right_hand_connections = clean_data.get("connections", {}).get("right_hand", [])

    trim_start = get_trim_start_index(clean_data)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if not video_fps or video_fps <= 0:
        video_fps = float(clean_data.get("fps", 30.0) or 30.0)

    video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_clean = len(clean_frames)

    writer = None
    if args.save:
        out_path = Path(args.save)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_path), fourcc, float(video_fps), (video_w, video_h))
        if not writer.isOpened():
            raise RuntimeError(f"Could not open video writer: {out_path}")

    current_idx = max(0, min(int(args.start_frame), total_clean - 1))
    paused = False
    speed = max(0.05, float(args.speed))

    show_labels = bool(args.show_labels)
    show_raw_pose = bool(args.show_raw_pose)
    show_raw_hands = bool(args.show_raw_hands)
    show_pose_landmarks = bool(args.show_pose_landmarks)

    window_name = "Clean Skeleton Overlay 3D"
    if not args.no_window:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    def render_clean_frame(clean_idx: int) -> Optional[Any]:
        raw_idx = trim_start + clean_idx
        if raw_idx < 0 or raw_idx >= len(raw_frames):
            return None

        frame = get_video_frame(cap, raw_idx)
        if frame is None:
            return None

        raw_frame = raw_frames[raw_idx]
        clean_frame = clean_frames[clean_idx]

        basis = recover_basis_from_raw_pose(raw_frame)
        if basis is None:
            return frame

        basis_center, basis_scale = basis
        anchor_xy = (basis_center[0], basis_center[1])

        # Use shoulders' average z from clean pose as depth anchor when available.
        clean_pose: NamedPoints = clean_frame.get("pose", {})
        ls = get_named_point(clean_pose, "left_shoulder")
        rs = get_named_point(clean_pose, "right_shoulder")
        anchor_z = 0.0
        if ls is not None and rs is not None:
            anchor_z = (ls[2] + rs[2]) * 0.5

        z_values = gather_visible_z_values(clean_frame)
        if not z_values:
            z_values = [anchor_z]
        z_near = min(z_values)   # more negative usually closer
        z_far = max(z_values)

        overlay = frame.copy()

        if show_raw_pose or show_raw_hands:
            draw_raw_reference_points(
                overlay,
                raw_frame,
                video_w,
                video_h,
                show_raw_pose=show_raw_pose,
                show_raw_hands=show_raw_hands,
            )

        rig: NamedPoints = clean_frame.get("rig", {})
        left_hand: NamedPoints = clean_frame.get("left_hand", {})
        right_hand: NamedPoints = clean_frame.get("right_hand", {})
        flags = clean_frame.get("flags", {})

        # Main colors
        rig_color = (40, 40, 40)
        pose_landmark_color = (150, 150, 150)
        left_color = (60, 220, 60)
        right_color = (0, 170, 255)
        filled_color = (80, 220, 255)
        rejected_color = (220, 60, 220)

        if bool(flags.get("left_hand_rejected_as_outlier", False)):
            left_color = rejected_color
        elif bool(flags.get("left_hand_filled", False)):
            left_color = filled_color

        if bool(flags.get("right_hand_rejected_as_outlier", False)):
            right_color = rejected_color
        elif bool(flags.get("right_hand_filled", False)):
            right_color = filled_color

        draw_connection_list(
            overlay, rig, pose_connections,
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            rig_color, 3, z_near, z_far
        )
        draw_connection_list(
            overlay, left_hand, left_hand_connections,
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            left_color, 2, z_near, z_far
        )
        draw_connection_list(
            overlay, right_hand, right_hand_connections,
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            right_color, 2, z_near, z_far
        )

        # Wrist bridges
        left_bridge = {
            "rig_left_wrist": get_named_point(rig, "left_wrist"),
            "hand_left_wrist": get_named_point(left_hand, "wrist"),
        }
        right_bridge = {
            "rig_right_wrist": get_named_point(rig, "right_wrist"),
            "hand_right_wrist": get_named_point(right_hand, "wrist"),
        }
        draw_connection_list(
            overlay, left_bridge, [["rig_left_wrist", "hand_left_wrist"]],
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            (180, 180, 180), 1, z_near, z_far
        )
        draw_connection_list(
            overlay, right_bridge, [["rig_right_wrist", "hand_right_wrist"]],
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            (180, 180, 180), 1, z_near, z_far
        )

        draw_named_points(
            overlay, rig,
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            rig_color, 4, z_near, z_far,
            show_labels=show_labels, label_prefix="rig:"
        )

        if show_pose_landmarks:
            draw_named_points(
                overlay, clean_pose,
                basis_center, basis_scale, flip_y,
                video_w, video_h,
                anchor_xy, anchor_z,
                args.perspective_strength,
                args.min_perspective_factor,
                args.max_perspective_factor,
                pose_landmark_color, 2, z_near, z_far,
                show_labels=False, label_prefix=""
            )

        draw_named_points(
            overlay, left_hand,
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            left_color, 3, z_near, z_far,
            show_labels=show_labels, label_prefix="L:"
        )
        draw_named_points(
            overlay, right_hand,
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            right_color, 3, z_near, z_far,
            show_labels=show_labels, label_prefix="R:"
        )

        draw_palm_orientation(
            overlay, left_hand, "left",
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            z_near, z_far,
            args.normal_length_factor,
        )
        draw_palm_orientation(
            overlay, right_hand, "right",
            basis_center, basis_scale, flip_y,
            video_w, video_h,
            anchor_xy, anchor_z,
            args.perspective_strength,
            args.min_perspective_factor,
            args.max_perspective_factor,
            z_near, z_far,
            args.normal_length_factor,
        )

        # Blend overlay onto frame
        alpha = clamp(float(args.alpha), 0.0, 1.0)
        output = cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0.0)

        info_lines = [
            f"gloss={clean_data.get('gloss')}  video_id={clean_data.get('video_id')}  split={clean_data.get('split')}",
            f"clean_frame={clean_idx + 1}/{total_clean}  raw_frame={raw_idx + 1}/{len(raw_frames)}  fps={video_fps:.2f}  speed={speed:.2f}x",
            f"left raw={bool(flags.get('has_left_hand_raw'))} filled={bool(flags.get('left_hand_filled'))} rejected={bool(flags.get('left_hand_rejected_as_outlier'))}",
            f"right raw={bool(flags.get('has_right_hand_raw'))} filled={bool(flags.get('right_hand_filled'))} rejected={bool(flags.get('right_hand_rejected_as_outlier'))}",
            f"keys: space play/pause | left/right step | +/- speed | l labels | p pose | o raw hands | i raw pose | r restart | q quit",
        ]
        draw_text_block(output, info_lines, (16, 28))

        return output

    while True:
        output = render_clean_frame(current_idx)
        if output is None:
            break

        if writer is not None:
            writer.write(output)

        if not args.no_window:
            cv2.imshow(window_name, output)

        delay_ms = 1 if paused else max(1, int(round(1000.0 / (video_fps * speed))))
        key = cv2.waitKey(delay_ms) & 0xFF

        if key in (27, ord("q")):
            break
        elif key == ord(" "):
            paused = not paused
        elif key in (81, ord("j")):  # left arrow on some systems, or j
            paused = True
            current_idx = max(0, current_idx - 1)
        elif key in (83, ord("k")):  # right arrow on some systems, or k
            paused = True
            current_idx = min(total_clean - 1, current_idx + 1)
        elif key in (ord("+"), ord("=")):
            speed = min(8.0, speed * 1.25)
        elif key in (ord("-"), ord("_")):
            speed = max(0.05, speed / 1.25)
        elif key == ord("l"):
            show_labels = not show_labels
        elif key == ord("p"):
            show_pose_landmarks = not show_pose_landmarks
        elif key == ord("o"):
            show_raw_hands = not show_raw_hands
        elif key == ord("i"):
            show_raw_pose = not show_raw_pose
        elif key == ord("r"):
            current_idx = 0
            paused = False

        if not paused:
            current_idx += 1
            if current_idx >= total_clean:
                if args.loop:
                    current_idx = 0
                else:
                    break

    cap.release()
    if writer is not None:
        writer.release()
        print(f"[OK] Saved overlay video to {args.save}")
    if not args.no_window:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()