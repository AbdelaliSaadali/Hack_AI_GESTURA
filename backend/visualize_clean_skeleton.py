import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2


BGR = Tuple[int, int, int]
Point3 = List[float]
NamedPoints = Dict[str, Optional[Point3]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize cleaned normalized skeleton JSON with pose and hand connections."
    )
    parser.add_argument(
        "--json",
        required=True,
        help="Path to a cleaned skeleton JSON file produced by build_clean_skeleton.py",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Canvas width in pixels",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Canvas height in pixels",
    )
    parser.add_argument(
        "--margin",
        type=int,
        default=80,
        help="Canvas margin in pixels",
    )
    parser.add_argument(
        "--scale_multiplier",
        type=float,
        default=1.0,
        help="Extra zoom multiplier applied after automatic fit",
    )
    parser.add_argument(
        "--start_frame",
        type=int,
        default=0,
        help="Frame index to start playback from",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier",
    )
    parser.add_argument(
        "--save",
        help="Optional path to save a rendered MP4 instead of only showing a live window",
    )
    parser.add_argument(
        "--no_window",
        action="store_true",
        help="Do not open an interactive window; useful with --save",
    )
    parser.add_argument(
        "--show_pose_landmarks",
        action="store_true",
        help="Also draw the full 33 pose landmarks as small dots",
    )
    parser.add_argument(
        "--show_labels",
        action="store_true",
        help="Start with joint labels enabled",
    )
    parser.add_argument(
        "--show_axes",
        action="store_true",
        help="Draw normalized X/Y axes",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop playback when the clip ends",
    )
    return parser.parse_args()


def load_json(path: str) -> Dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise RuntimeError("Expected top-level JSON object")

    if "frames" not in data or not isinstance(data["frames"], list) or not data["frames"]:
        raise RuntimeError("JSON does not contain a non-empty 'frames' list")

    required_top_keys = ["connections", "landmark_names"]
    for key in required_top_keys:
        if key not in data:
            raise RuntimeError(f"Missing required top-level key: {key}")

    return data


def get_named_point(mapping: Optional[NamedPoints], name: str) -> Optional[Point3]:
    if not isinstance(mapping, dict):
        return None
    value = mapping.get(name)
    if (
        isinstance(value, list)
        and len(value) >= 2
        and all(isinstance(v, (int, float)) for v in value[:2])
    ):
        z = float(value[2]) if len(value) > 2 and isinstance(value[2], (int, float)) else 0.0
        return [float(value[0]), float(value[1]), z]
    return None


def iter_frame_points(frame: Dict[str, Any], include_pose_landmarks: bool) -> Iterable[Point3]:
    for section_name in ["rig", "left_hand", "right_hand"]:
        section = frame.get(section_name, {})
        if isinstance(section, dict):
            for value in section.values():
                if (
                    isinstance(value, list)
                    and len(value) >= 2
                    and all(isinstance(v, (int, float)) for v in value[:2])
                ):
                    yield [float(value[0]), float(value[1]), float(value[2]) if len(value) > 2 else 0.0]

    if include_pose_landmarks:
        pose_section = frame.get("pose", {})
        if isinstance(pose_section, dict):
            for value in pose_section.values():
                if (
                    isinstance(value, list)
                    and len(value) >= 2
                    and all(isinstance(v, (int, float)) for v in value[:2])
                ):
                    yield [float(value[0]), float(value[1]), float(value[2]) if len(value) > 2 else 0.0]


def compute_global_view_transform(
    frames: List[Dict[str, Any]],
    width: int,
    height: int,
    margin: int,
    scale_multiplier: float,
    include_pose_landmarks: bool,
) -> Tuple[float, float, float]:
    points: List[Point3] = []
    for frame in frames:
        points.extend(iter_frame_points(frame, include_pose_landmarks))

    if not points:
        return 200.0, 0.0, 0.0

    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)

    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)

    usable_w = max(100, width - 2 * margin)
    usable_h = max(100, height - 2 * margin)

    scale = min(usable_w / span_x, usable_h / span_y) * scale_multiplier
    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5

    return scale, center_x, center_y


def project_point(
    point: Point3,
    width: int,
    height: int,
    scale: float,
    center_x: float,
    center_y: float,
) -> Tuple[int, int]:
    x = int(round((point[0] - center_x) * scale + width * 0.5))
    y = int(round(height * 0.5 - (point[1] - center_y) * scale))
    return x, y


def draw_joint(
    canvas: Any,
    point: Point3,
    width: int,
    height: int,
    scale: float,
    center_x: float,
    center_y: float,
    color: BGR,
    radius: int,
) -> Tuple[int, int]:
    px, py = project_point(point, width, height, scale, center_x, center_y)
    cv2.circle(canvas, (px, py), radius, color, -1, lineType=cv2.LINE_AA)
    return px, py


def draw_named_connection(
    canvas: Any,
    mapping: NamedPoints,
    a_name: str,
    b_name: str,
    width: int,
    height: int,
    scale: float,
    center_x: float,
    center_y: float,
    color: BGR,
    thickness: int,
) -> None:
    a = get_named_point(mapping, a_name)
    b = get_named_point(mapping, b_name)
    if a is None or b is None:
        return

    pa = project_point(a, width, height, scale, center_x, center_y)
    pb = project_point(b, width, height, scale, center_x, center_y)
    cv2.line(canvas, pa, pb, color, thickness, lineType=cv2.LINE_AA)


def draw_named_points(
    canvas: Any,
    mapping: NamedPoints,
    width: int,
    height: int,
    scale: float,
    center_x: float,
    center_y: float,
    color: BGR,
    radius: int,
    labels: bool = False,
    label_prefix: str = "",
    label_limit: Optional[int] = None,
) -> None:
    count = 0
    for name, value in mapping.items():
        if label_limit is not None and count >= label_limit:
            break
        point = get_named_point(mapping, name)
        if point is None:
            continue
        px, py = draw_joint(canvas, point, width, height, scale, center_x, center_y, color, radius)
        if labels:
            text = f"{label_prefix}{name}"
            cv2.putText(
                canvas,
                text,
                (px + 6, py - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                color,
                1,
                lineType=cv2.LINE_AA,
            )
        count += 1


def draw_axes(
    canvas: Any,
    width: int,
    height: int,
    scale: float,
    center_x: float,
    center_y: float,
) -> None:
    origin = project_point([0.0, 0.0, 0.0], width, height, scale, center_x, center_y)
    x_axis = project_point([0.6, 0.0, 0.0], width, height, scale, center_x, center_y)
    y_axis = project_point([0.0, 0.6, 0.0], width, height, scale, center_x, center_y)

    cv2.line(canvas, origin, x_axis, (180, 180, 180), 1, lineType=cv2.LINE_AA)
    cv2.line(canvas, origin, y_axis, (180, 180, 180), 1, lineType=cv2.LINE_AA)
    cv2.circle(canvas, origin, 3, (220, 220, 220), -1, lineType=cv2.LINE_AA)
    cv2.putText(canvas, "X+", (x_axis[0] + 4, x_axis[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1, lineType=cv2.LINE_AA)
    cv2.putText(canvas, "Y+", (y_axis[0] + 4, y_axis[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1, lineType=cv2.LINE_AA)


def hand_colors(flags: Dict[str, Any], side: str) -> Tuple[BGR, BGR]:
    if side == "left":
        raw_color = (60, 220, 60)
        filled_color = (80, 200, 255)
        rejected_color = (255, 80, 220)
    else:
        raw_color = (0, 170, 255)
        filled_color = (80, 220, 255)
        rejected_color = (255, 80, 220)

    if flags.get(f"{side}_hand_rejected_as_outlier", False):
        return rejected_color, rejected_color
    if flags.get(f"{side}_hand_filled", False):
        return filled_color, filled_color
    return raw_color, raw_color


def draw_frame(
    frame: Dict[str, Any],
    meta: Dict[str, Any],
    width: int,
    height: int,
    scale: float,
    center_x: float,
    center_y: float,
    show_pose_landmarks: bool,
    show_labels: bool,
    show_axes: bool,
    playback_speed: float,
) -> Any:
    canvas = 255 * (cv2.UMat(height, width, cv2.CV_8UC3).get() * 0 + 1)

    if show_axes:
        draw_axes(canvas, width, height, scale, center_x, center_y)

    rig: NamedPoints = frame.get("rig", {})
    pose: NamedPoints = frame.get("pose", {})
    left_hand: NamedPoints = frame.get("left_hand", {})
    right_hand: NamedPoints = frame.get("right_hand", {})
    flags: Dict[str, Any] = frame.get("flags", {})

    pose_connections = meta["connections"].get("pose", [])
    left_connections = meta["connections"].get("left_hand", [])
    right_connections = meta["connections"].get("right_hand", [])

    pose_bone_color = (60, 60, 60)
    pose_joint_color = (40, 40, 40)

    left_bone_color, left_joint_color = hand_colors(flags, "left")
    right_bone_color, right_joint_color = hand_colors(flags, "right")

    for a_name, b_name in pose_connections:
        draw_named_connection(
            canvas,
            rig,
            a_name,
            b_name,
            width,
            height,
            scale,
            center_x,
            center_y,
            pose_bone_color,
            3,
        )

    for a_name, b_name in left_connections:
        draw_named_connection(
            canvas,
            left_hand,
            a_name,
            b_name,
            width,
            height,
            scale,
            center_x,
            center_y,
            left_bone_color,
            2,
        )

    for a_name, b_name in right_connections:
        draw_named_connection(
            canvas,
            right_hand,
            a_name,
            b_name,
            width,
            height,
            scale,
            center_x,
            center_y,
            right_bone_color,
            2,
        )

    # Optional wrist bridges from rig wrists to hand wrists.
    draw_named_connection(
        canvas,
        {
            "rig_left_wrist": get_named_point(rig, "left_wrist"),
            "hand_left_wrist": get_named_point(left_hand, "wrist"),
        },
        "rig_left_wrist",
        "hand_left_wrist",
        width,
        height,
        scale,
        center_x,
        center_y,
        (150, 150, 150),
        1,
    )
    draw_named_connection(
        canvas,
        {
            "rig_right_wrist": get_named_point(rig, "right_wrist"),
            "hand_right_wrist": get_named_point(right_hand, "wrist"),
        },
        "rig_right_wrist",
        "hand_right_wrist",
        width,
        height,
        scale,
        center_x,
        center_y,
        (150, 150, 150),
        1,
    )

    draw_named_points(
        canvas,
        rig,
        width,
        height,
        scale,
        center_x,
        center_y,
        pose_joint_color,
        radius=5,
        labels=show_labels,
        label_prefix="rig:",
    )

    if show_pose_landmarks:
        draw_named_points(
            canvas,
            pose,
            width,
            height,
            scale,
            center_x,
            center_y,
            color=(170, 170, 170),
            radius=2,
            labels=False,
        )

    draw_named_points(
        canvas,
        left_hand,
        width,
        height,
        scale,
        center_x,
        center_y,
        left_joint_color,
        radius=3,
        labels=show_labels,
        label_prefix="L:",
    )
    draw_named_points(
        canvas,
        right_hand,
        width,
        height,
        scale,
        center_x,
        center_y,
        right_joint_color,
        radius=3,
        labels=show_labels,
        label_prefix="R:",
    )

    draw_overlay_text(canvas, frame, meta, playback_speed, show_pose_landmarks, show_labels, show_axes)
    return canvas


def draw_overlay_text(
    canvas: Any,
    frame: Dict[str, Any],
    meta: Dict[str, Any],
    playback_speed: float,
    show_pose_landmarks: bool,
    show_labels: bool,
    show_axes: bool,
) -> None:
    h, w = canvas.shape[:2]
    flags = frame.get("flags", {})

    lines = [
        f"gloss={meta.get('gloss')}  video_id={meta.get('video_id')}  split={meta.get('split')}",
        f"frame={frame.get('frame_index', 0) + 1}/{meta.get('frame_count', '?')}  fps={meta.get('fps', 30):.2f}  speed={playback_speed:.2f}x",
        f"left raw={bool(flags.get('has_left_hand_raw'))} filled={bool(flags.get('left_hand_filled'))} rejected={bool(flags.get('left_hand_rejected_as_outlier'))}",
        f"right raw={bool(flags.get('has_right_hand_raw'))} filled={bool(flags.get('right_hand_filled'))} rejected={bool(flags.get('right_hand_rejected_as_outlier'))}",
        f"toggles: labels={show_labels} pose_landmarks={show_pose_landmarks} axes={show_axes}",
        "keys: space play/pause | left/right step | +/- speed | l labels | p pose dots | a axes | r restart | q quit",
    ]

    y = 26
    for line in lines:
        cv2.putText(
            canvas,
            line,
            (18, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (30, 30, 30),
            2,
            lineType=cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            line,
            (18, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (245, 245, 245),
            1,
            lineType=cv2.LINE_AA,
        )
        y += 24

    cv2.rectangle(canvas, (10, 10), (w - 10, h - 10), (220, 220, 220), 1, lineType=cv2.LINE_AA)


def create_video_writer(path: str, width: int, height: int, fps: float) -> cv2.VideoWriter:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer for: {out_path}")
    return writer


def clamp_frame_index(idx: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(idx, total - 1))


def key_is(key: int, chars: str) -> bool:
    return key in [ord(c) for c in chars]


def main() -> None:
    args = parse_args()
    data = load_json(args.json)

    frames: List[Dict[str, Any]] = data["frames"]
    total_frames = len(frames)
    if total_frames == 0:
        raise RuntimeError("No frames to render")

    fps = float(data.get("fps", 30.0) or 30.0)
    speed = max(0.05, float(args.speed))
    current = clamp_frame_index(args.start_frame, total_frames)

    show_pose_landmarks = bool(args.show_pose_landmarks)
    show_labels = bool(args.show_labels)
    show_axes = bool(args.show_axes)
    paused = False

    scale, center_x, center_y = compute_global_view_transform(
        frames=frames,
        width=args.width,
        height=args.height,
        margin=args.margin,
        scale_multiplier=args.scale_multiplier,
        include_pose_landmarks=show_pose_landmarks,
    )

    writer: Optional[cv2.VideoWriter] = None
    if args.save:
        writer = create_video_writer(args.save, args.width, args.height, fps=max(1.0, fps))

    def render_one(frame_idx: int) -> Any:
        return draw_frame(
            frame=frames[frame_idx],
            meta=data,
            width=args.width,
            height=args.height,
            scale=scale,
            center_x=center_x,
            center_y=center_y,
            show_pose_landmarks=show_pose_landmarks,
            show_labels=show_labels,
            show_axes=show_axes,
            playback_speed=speed,
        )

    if writer is not None and args.no_window:
        for i in range(total_frames):
            canvas = render_one(i)
            writer.write(canvas)
        writer.release()
        print(f"[OK] Saved video to {args.save}")
        return

    window_name = "Clean Skeleton Viewer"
    if not args.no_window:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        canvas = render_one(current)

        if writer is not None:
            writer.write(canvas)

        if not args.no_window:
            cv2.imshow(window_name, canvas)

        delay_ms = 1 if paused else max(1, int(round(1000.0 / (fps * speed))))
        key = cv2.waitKey(delay_ms) & 0xFF

        if key in (27, ord("q")):
            break
        elif key == ord(" "):
            paused = not paused
        elif key in (81, ord("j")):  # left arrow on some systems, or j
            paused = True
            current = clamp_frame_index(current - 1, total_frames)
        elif key in (83, ord("k")):  # right arrow on some systems, or k
            paused = True
            current = clamp_frame_index(current + 1, total_frames)
        elif key_is(key, "+="):
            speed = min(8.0, speed * 1.25)
        elif key in (ord("-"), ord("_")):
            speed = max(0.05, speed / 1.25)
        elif key == ord("l"):
            show_labels = not show_labels
        elif key == ord("p"):
            show_pose_landmarks = not show_pose_landmarks
        elif key == ord("a"):
            show_axes = not show_axes
        elif key == ord("r"):
            current = 0
            paused = False

        if not paused:
            current += 1
            if current >= total_frames:
                if args.loop:
                    current = 0
                else:
                    break

    if writer is not None:
        writer.release()
        print(f"[OK] Saved video to {args.save}")

    if not args.no_window:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()