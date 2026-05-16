#!/usr/bin/env python3
"""
Gestura Sign-to-Text webcam prototype — HAND-FIRST VERSION.

Goal:
- Open the PC webcam with OpenCV.
- Use MediaPipe Hands as the main recognition source.
- Use MediaPipe Pose only as optional helper.
- Do NOT depend on elbows or full arms.
- Record a short sign sequence when SPACE is pressed.
- Compare the live hand movement with clean_skeletons templates.
- Show the closest word + confidence.

Run:
cd /Users/mac/Desktop/Gestura/backend
source venv/bin/activate

python3 sign_to_text_webcam.py \
  --words help sick eat drink school yes no want family mother
"""

import argparse
import json
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np


# =========================
# MediaPipe landmark indexes
# =========================

NOSE = 0
LEFT_EYE = 2
RIGHT_EYE = 5
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_WRIST_POSE = 15
RIGHT_WRIST_POSE = 16

HAND_NAMES = [
    "wrist",
    "thumb_cmc", "thumb_mcp", "thumb_ip", "thumb_tip",
    "index_mcp", "index_pip", "index_dip", "index_tip",
    "middle_mcp", "middle_pip", "middle_dip", "middle_tip",
    "ring_mcp", "ring_pip", "ring_dip", "ring_tip",
    "pinky_mcp", "pinky_pip", "pinky_dip", "pinky_tip",
]

OPTIONAL_BODY_KEYS = [
    "nose",
    "left_shoulder",
    "right_shoulder",
    "left_wrist_pose",
    "right_wrist_pose",
]

# Feature vector organization.
# Hand-first:
# 1. left hand shape
# 2. right hand shape
# 3. hand placement in signing space
# 4. optional body anchors
FEATURE_KEYS = (
    [f"left_shape:{name}" for name in HAND_NAMES] +
    [f"right_shape:{name}" for name in HAND_NAMES] +
    [
        "space:left_wrist",
        "space:right_wrist",
        "space:left_center",
        "space:right_center",
        "space:hands_midpoint",
        "space:hands_vector",
    ] +
    [f"body:{name}" for name in OPTIONAL_BODY_KEYS]
)


# =========================
# Basic geometry helpers
# =========================

def lm_to_point(lm) -> List[float]:
    return [float(lm.x), float(lm.y), float(lm.z)]


def xy_dist(a: List[float], b: List[float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def midpoint(a: List[float], b: List[float]) -> List[float]:
    return [
        (a[0] + b[0]) / 2.0,
        (a[1] + b[1]) / 2.0,
        (a[2] + b[2]) / 2.0,
    ]


def safe_scale(value: float, minimum: float = 1e-5) -> float:
    return max(abs(value), minimum)


def normalize_global_point(
    p: List[float],
    origin: List[float],
    scale: float,
) -> List[float]:
    """
    Normalize a point in signing space.

    x: right/left camera space
    y: inverted so up is positive
    z: depth-like MediaPipe coordinate
    """
    s = safe_scale(scale)
    return [
        (p[0] - origin[0]) / s,
        -(p[1] - origin[1]) / s,
        (p[2] - origin[2]) / s,
    ]


def hand_center(hand: List[List[float]]) -> List[float]:
    arr = np.array(hand, dtype=np.float32)
    return [
        float(np.nanmean(arr[:, 0])),
        float(np.nanmean(arr[:, 1])),
        float(np.nanmean(arr[:, 2])),
    ]


def hand_size(hand: List[List[float]]) -> float:
    """
    Approximate hand size using wrist-to-MCP distances.
    This makes hand shape less dependent on camera distance.
    """
    wrist = hand[0]
    candidates = [5, 9, 13, 17]  # MCP joints
    dists = []

    for idx in candidates:
        if idx < len(hand):
            dists.append(xy_dist(wrist, hand[idx]))

    if not dists:
        return 0.05

    return safe_scale(float(np.mean(dists)), minimum=0.02)


def normalize_hand_shape(hand: List[List[float]], flip_y: bool = True) -> List[List[float]]:
    """
    Normalize each hand by its own wrist and size.

    Live MediaPipe input has image Y downward, so flip_y=True.
    Clean skeleton templates are already flip_y=True from build_clean_skeleton.py,
    so for templates use flip_y=False.
    """
    wrist = hand[0]
    scale = hand_size(hand)

    normalized = []
    for p in hand:
        y = (p[1] - wrist[1]) / scale
        if flip_y:
            y = -y

        normalized.append([
            (p[0] - wrist[0]) / scale,
            y,
            (p[2] - wrist[2]) / scale,
        ])

    return normalized


# =========================
# Hand assignment
# =========================

def assign_hands(
    multi_hand_landmarks,
    multi_handedness,
    pose_points: Optional[List[List[float]]],
) -> Tuple[Optional[List[List[float]]], Optional[List[List[float]]]]:
    """
    Hand assignment for webcam demo.

    This version ignores small/background hands.

    Problem fixed:
    - MediaPipe may detect another person's hand in the background.
    - That can falsely create Hands: L+R.
    - We keep only the largest visible hands because the real signer is closer to the camera.
    """
    if not multi_hand_landmarks:
        return None, None

    hands = []

    for hand_lm in multi_hand_landmarks:
        pts = [lm_to_point(lm) for lm in hand_lm.landmark]
        center = hand_center(pts)
        size = hand_size(pts)

        hands.append({
            "points": pts,
            "center": center,
            "size": size,
        })

    # Remove very small hands, usually background hands.
    # Tune this if needed:
    # - If it ignores your real hand, lower to 0.020
    # - If it still detects background hands, raise to 0.040
    MIN_HAND_SIZE = 0.030

    hands = [h for h in hands if h["size"] >= MIN_HAND_SIZE]

    if not hands:
        return None, None

    # Keep only the two largest hands.
    # This avoids background people being detected as the second hand.
    hands = sorted(hands, key=lambda h: h["size"], reverse=True)[:2]

    # Then assign left/right by screen position.
    hands_sorted = sorted(hands, key=lambda h: h["center"][0])

    if len(hands_sorted) == 1:
        h = hands_sorted[0]

        if h["center"][0] < 0.5:
            return h["points"], None
        else:
            return None, h["points"]

    left_hand = hands_sorted[0]["points"]
    right_hand = hands_sorted[1]["points"]

    return left_hand, right_hand

# =========================
# Feature extraction
# =========================

def compute_global_reference(
    pose_points: Optional[List[List[float]]],
    left_hand: Optional[List[List[float]]],
    right_hand: Optional[List[List[float]]],
) -> Tuple[List[float], float]:
    """
    Global signing-space normalization.

    Priority:
    1. Shoulders if visible
    2. Face/nose and eyes if visible
    3. Both hands bounding distance
    4. One hand size
    5. Default camera center

    This avoids failing when elbows/arms are cropped.
    """
    # 1. Shoulders
    if pose_points and len(pose_points) > RIGHT_SHOULDER:
        ls = pose_points[LEFT_SHOULDER]
        rs = pose_points[RIGHT_SHOULDER]
        shoulder_width = xy_dist(ls, rs)

        if shoulder_width > 0.03:
            return midpoint(ls, rs), shoulder_width

    # 2. Face
    if pose_points and len(pose_points) > RIGHT_EYE:
        nose = pose_points[NOSE]
        le = pose_points[LEFT_EYE]
        re = pose_points[RIGHT_EYE]
        eye_dist = xy_dist(le, re)

        if eye_dist > 0.01:
            # Face scale is smaller than shoulder scale, enlarge it.
            return nose, eye_dist * 3.2

    # 3. Both hands
    if left_hand is not None and right_hand is not None:
        lc = hand_center(left_hand)
        rc = hand_center(right_hand)
        hands_dist = xy_dist(lc, rc)

        if hands_dist > 0.03:
            return midpoint(lc, rc), hands_dist

    # 4. One hand
    if left_hand is not None:
        return hand_center(left_hand), hand_size(left_hand) * 5.0

    if right_hand is not None:
        return hand_center(right_hand), hand_size(right_hand) * 5.0

    # 5. Default
    return [0.5, 0.5, 0.0], 0.5


def extract_hand_first_features(
    pose_points: Optional[List[List[float]]],
    left_hand: Optional[List[List[float]]],
    right_hand: Optional[List[List[float]]],
) -> Optional[Dict[str, List[float]]]:
    """
    Main feature extractor.

    It works even if:
    - elbows are missing
    - shoulders are missing
    - only hands are visible

    It returns None only if no hand is detected.
    """
    if left_hand is None and right_hand is None:
        return None

    features: Dict[str, List[float]] = {}

    origin, scale = compute_global_reference(pose_points, left_hand, right_hand)

    # Hand shape features
    if left_hand is not None:
        norm_left = normalize_hand_shape(left_hand)
        for i, name in enumerate(HAND_NAMES):
            features[f"left_shape:{name}"] = norm_left[i]

    if right_hand is not None:
        norm_right = normalize_hand_shape(right_hand)
        for i, name in enumerate(HAND_NAMES):
            features[f"right_shape:{name}"] = norm_right[i]

    # Hand placement features in global signing space
    if left_hand is not None:
        lw = left_hand[0]
        lc = hand_center(left_hand)
        features["space:left_wrist"] = normalize_global_point(lw, origin, scale)
        features["space:left_center"] = normalize_global_point(lc, origin, scale)

    if right_hand is not None:
        rw = right_hand[0]
        rc = hand_center(right_hand)
        features["space:right_wrist"] = normalize_global_point(rw, origin, scale)
        features["space:right_center"] = normalize_global_point(rc, origin, scale)

    if left_hand is not None and right_hand is not None:
        lc = hand_center(left_hand)
        rc = hand_center(right_hand)

        mid = midpoint(lc, rc)
        vec = [
            (rc[0] - lc[0]) / safe_scale(scale),
            -(rc[1] - lc[1]) / safe_scale(scale),
            (rc[2] - lc[2]) / safe_scale(scale),
        ]

        features["space:hands_midpoint"] = normalize_global_point(mid, origin, scale)
        features["space:hands_vector"] = vec

    # Optional body anchors
    if pose_points:
        body_map = {
            "nose": NOSE,
            "left_shoulder": LEFT_SHOULDER,
            "right_shoulder": RIGHT_SHOULDER,
            "left_wrist_pose": LEFT_WRIST_POSE,
            "right_wrist_pose": RIGHT_WRIST_POSE,
        }

        for name, idx in body_map.items():
            if idx < len(pose_points):
                features[f"body:{name}"] = normalize_global_point(
                    pose_points[idx],
                    origin,
                    scale,
                )

    return features


# =========================
# Template loading
# =========================

def load_video_id_to_word(path: Path) -> Dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping: Dict[str, str] = {}

    for video_id, value in data.items():
        if isinstance(value, dict):
            word = value.get("word") or value.get("gloss")
        else:
            word = str(value)

        if word:
            mapping[str(video_id)] = word.lower().strip()

    return mapping


def get_point_from_dict(obj: dict) -> Optional[List[float]]:
    """
    Accepts either:
    [x, y, z]
    or:
    {"x": ..., "y": ..., "z": ...}
    """
    if obj is None:
        return None

    if isinstance(obj, list) and len(obj) >= 3:
        return [float(obj[0]), float(obj[1]), float(obj[2])]

    if isinstance(obj, dict):
        if "x" in obj and "y" in obj:
            return [
                float(obj.get("x", 0.0)),
                float(obj.get("y", 0.0)),
                float(obj.get("z", 0.0)),
            ]

    return None


def parse_hand_from_frame(frame: dict, side: str) -> Optional[List[List[float]]]:
    """
    Tries multiple possible formats for clean skeleton hand data.
    """
    raw = frame.get(side)

    if raw is None:
        raw = frame.get(f"{side}_hand")

    if raw is None:
        raw = frame.get(f"{side}Hand")

    if raw is None:
        return None

    # Format 1: dict with landmark names.
    if isinstance(raw, dict):
        hand = []

        for name in HAND_NAMES:
            p = get_point_from_dict(raw.get(name))
            if p is None:
                return None
            hand.append(p)

        return hand

    # Format 2: list of 21 points.
    if isinstance(raw, list) and len(raw) >= 21:
        hand = []

        for i in range(21):
            p = get_point_from_dict(raw[i])
            if p is None:
                return None
            hand.append(p)

        return hand

    return None


def parse_pose_from_frame(frame: dict) -> Optional[List[List[float]]]:
    """
    Converts clean_skeleton frame pose into a list similar to MediaPipe pose indexes.

    Supports:
    frame["pose"]["nose"]
    frame["pose"]["left_shoulder"]
    etc.
    """
    raw = frame.get("pose")

    if raw is None or not isinstance(raw, dict):
        return None

    pose = [[np.nan, np.nan, np.nan] for _ in range(33)]

    key_to_idx = {
        "nose": NOSE,
        "left_eye": LEFT_EYE,
        "right_eye": RIGHT_EYE,
        "left_shoulder": LEFT_SHOULDER,
        "right_shoulder": RIGHT_SHOULDER,
        "left_wrist": LEFT_WRIST_POSE,
        "right_wrist": RIGHT_WRIST_POSE,
        "left_wrist_pose": LEFT_WRIST_POSE,
        "right_wrist_pose": RIGHT_WRIST_POSE,
    }

    found = False

    for key, idx in key_to_idx.items():
        p = get_point_from_dict(raw.get(key))
        if p is not None:
            pose[idx] = p
            found = True

    return pose if found else None


def clean_template_frame_to_features(frame: dict) -> Optional[Dict[str, List[float]]]:
    """
    Converts one clean_skeleton template frame into features.

    IMPORTANT:
    clean_skeletons are already normalized by build_clean_skeleton.py:
    - origin = shoulder_midpoint
    - scale = shoulder_width
    - flip_y = true

    So we must NOT apply global shoulder normalization again.
    We only compute:
    - hand shape relative to each wrist
    - already-normalized hand/body positions directly
    """
    features: Dict[str, List[float]] = {}

    left_hand = parse_hand_from_frame(frame, "left")
    right_hand = parse_hand_from_frame(frame, "right")
    pose = frame.get("pose") if isinstance(frame.get("pose"), dict) else {}

    if left_hand is None and right_hand is None:
        return None

    # Hand shape: template Y is already flipped, so do not flip again.
    if left_hand is not None:
        norm_left = normalize_hand_shape(left_hand, flip_y=False)
        for i, name in enumerate(HAND_NAMES):
            features[f"left_shape:{name}"] = norm_left[i]

        features["space:left_wrist"] = left_hand[0]
        features["space:left_center"] = hand_center(left_hand)

    if right_hand is not None:
        norm_right = normalize_hand_shape(right_hand, flip_y=False)
        for i, name in enumerate(HAND_NAMES):
            features[f"right_shape:{name}"] = norm_right[i]

        features["space:right_wrist"] = right_hand[0]
        features["space:right_center"] = hand_center(right_hand)

    if left_hand is not None and right_hand is not None:
        lc = hand_center(left_hand)
        rc = hand_center(right_hand)

        features["space:hands_midpoint"] = midpoint(lc, rc)
        features["space:hands_vector"] = [
            rc[0] - lc[0],
            rc[1] - lc[1],
            rc[2] - lc[2],
        ]

    body_map = {
        "nose": "nose",
        "left_shoulder": "left_shoulder",
        "right_shoulder": "right_shoulder",
        "left_wrist_pose": "left_wrist",
        "right_wrist_pose": "right_wrist",
    }

    for out_name, pose_name in body_map.items():
        p = get_point_from_dict(pose.get(pose_name))
        if p is not None:
            features[f"body:{out_name}"] = p

    return features


def template_frame_to_features(frame: dict) -> Optional[Dict[str, List[float]]]:
    """
    Converts one clean_skeleton template frame into hand-first features.

    Clean skeletons are already normalized, so use the clean-template path.
    """
    return clean_template_frame_to_features(frame)


# =========================
# Matrix conversion / matching
# =========================

def features_to_matrix(sequence: List[Dict[str, List[float]]]) -> np.ndarray:
    mat = np.full((len(sequence), len(FEATURE_KEYS) * 3), np.nan, dtype=np.float32)

    for t, frame_features in enumerate(sequence):
        for i, key in enumerate(FEATURE_KEYS):
            p = frame_features.get(key)

            if p is not None and len(p) == 3:
                mat[t, i * 3:(i + 1) * 3] = np.array(p, dtype=np.float32)

    return mat


def resample_matrix(mat: np.ndarray, target_len: int) -> np.ndarray:
    if mat.shape[0] == target_len:
        return mat.copy()

    if mat.shape[0] == 0:
        return np.full((target_len, mat.shape[1]), np.nan, dtype=np.float32)

    old_x = np.linspace(0.0, 1.0, mat.shape[0])
    new_x = np.linspace(0.0, 1.0, target_len)
    out = np.full((target_len, mat.shape[1]), np.nan, dtype=np.float32)

    for c in range(mat.shape[1]):
        col = mat[:, c]
        valid = ~np.isnan(col)

        if valid.sum() == 0:
            continue

        if valid.sum() == 1:
            out[:, c] = col[valid][0]
        else:
            out[:, c] = np.interp(new_x, old_x[valid], col[valid])

    return out


def key_group_weight(key: str) -> float:
    """
    Experiment 2:
    Use hand shape + relation between both hands.
    Ignore body.
    Reduce absolute placement.
    """

    if key.startswith("left_shape:") or key.startswith("right_shape:"):
        return 3.0

    if key == "space:hands_vector":
        return 2.5

    if key == "space:hands_midpoint":
        return 0.5

    if key in ["space:left_wrist", "space:right_wrist", "space:left_center", "space:right_center"]:
        return 0.3

    if key.startswith("body:"):
        return 0.0

    return 0.0


WEIGHTS = np.array(
    [key_group_weight(k) for k in FEATURE_KEYS for _ in range(3)],
    dtype=np.float32,
)


def group_distance_debug(a: np.ndarray, b: np.ndarray) -> Dict[str, float]:
    """
    Compute distance by feature group:
    - left_shape
    - right_shape
    - space
    - body
    """
    groups = {
        "left_shape": [],
        "right_shape": [],
        "space": [],
        "body": [],
    }

    for i, key in enumerate(FEATURE_KEYS):
        start = i * 3
        end = start + 3

        aa = a[:, start:end]
        bb = b[:, start:end]

        valid = ~np.isnan(aa) & ~np.isnan(bb)

        if valid.sum() == 0:
            continue

        d = np.abs(aa - bb)
        value = float(np.nanmean(d[valid]))

        if key.startswith("left_shape:"):
            groups["left_shape"].append(value)
        elif key.startswith("right_shape:"):
            groups["right_shape"].append(value)
        elif key.startswith("space:"):
            groups["space"].append(value)
        elif key.startswith("body:"):
            groups["body"].append(value)

    result = {}

    for name, values in groups.items():
        if values:
            result[name] = float(np.mean(values))
        else:
            result[name] = float("nan")

    return result


def weighted_sequence_distance(a: np.ndarray, b: np.ndarray) -> float:
    """
    Weighted distance that tolerates missing features.

    If elbows/body are missing, it still works because body has low weight.
    """
    if a.shape != b.shape:
        raise ValueError("Sequences must have the same shape")

    valid = ~np.isnan(a) & ~np.isnan(b)

    if valid.sum() < 20:
        return float("inf")

    diff = np.abs(a - b)

    # WEIGHTS is 1D: one weight per feature column.
    # a/b are 2D: frames x feature_columns.
    # So we broadcast weights across all frames.
    weights_2d = np.broadcast_to(WEIGHTS, a.shape)

    valid_weights = weights_2d[valid]
    valid_diff = diff[valid]

    weighted_mean = np.sum(valid_diff * valid_weights) / np.sum(valid_weights)
    return float(weighted_mean)


def confidence_from_distance(distance: float) -> float:
    """
    Simple confidence approximation.

    You can tune threshold after testing:
    - smaller distance = better match
    """
    if not math.isfinite(distance):
        return 0.0

    # Hand-first normalized distances are often around 0.15 - 0.90.
    conf = (1.0 - distance / 0.95) * 100.0
    return float(max(0.0, min(100.0, conf)))


def load_templates(
    templates_dir: Path,
    id_to_word: Dict[str, str],
    target_len: int,
    allowed_words: Optional[List[str]] = None,
) -> List[dict]:
    allowed = {w.lower().strip() for w in allowed_words} if allowed_words else None
    templates = []

    json_files = sorted(templates_dir.glob("*.json"))

    for path in json_files:
        video_id = path.stem

        if video_id.endswith("_clean"):
            video_id = video_id.replace("_clean", "")

        if video_id.endswith("_stable"):
            video_id = video_id.replace("_stable", "")

        if video_id.endswith("_avatar"):
            video_id = video_id.replace("_avatar", "")

        word = id_to_word.get(video_id, video_id).lower().strip()

        if allowed is not None and word not in allowed:
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            if isinstance(data, dict):
                frames = data.get("frames", [])
            elif isinstance(data, list):
                frames = data
            else:
                frames = []

            sequence = []

            for frame in frames:
                feat = template_frame_to_features(frame)
                if feat is not None:
                    sequence.append(feat)

            if len(sequence) < 5:
                print(f"[WARN] Template skipped, too few usable frames: {path.name}")
                continue

            mat = features_to_matrix(sequence)
            mat = resample_matrix(mat, target_len)

            templates.append({
                "video_id": video_id,
                "word": word,
                "matrix": mat,
                "path": str(path),
            })

        except Exception as e:
            print(f"[WARN] Failed to load template {path.name}: {e}")

    if not templates:
        raise RuntimeError(
            "No templates loaded. Check --templates, --map, or --words. "
            "Maybe your clean_skeletons JSON format is different."
        )

    return templates

def swap_left_right_features(sequence: List[Dict[str, List[float]]]) -> List[Dict[str, List[float]]]:
    """
    Create a version of the sequence where left/right hand features are swapped.

    This helps when:
    - webcam mirror reverses hands
    - MediaPipe assigns hands differently
    - user performs sign with opposite hand
    """
    swapped_sequence = []

    for frame in sequence:
        new_frame = {}

        for key, value in frame.items():
            new_key = key

            if key.startswith("left_shape:"):
                new_key = key.replace("left_shape:", "right_shape:", 1)

            elif key.startswith("right_shape:"):
                new_key = key.replace("right_shape:", "left_shape:", 1)

            elif key == "space:left_wrist":
                new_key = "space:right_wrist"

            elif key == "space:right_wrist":
                new_key = "space:left_wrist"

            elif key == "space:left_center":
                new_key = "space:right_center"

            elif key == "space:right_center":
                new_key = "space:left_center"

            elif key == "body:left_wrist_pose":
                new_key = "body:right_wrist_pose"

            elif key == "body:right_wrist_pose":
                new_key = "body:left_wrist_pose"

            elif key == "body:left_shoulder":
                new_key = "body:right_shoulder"

            elif key == "body:right_shoulder":
                new_key = "body:left_shoulder"

            new_frame[new_key] = value

        swapped_sequence.append(new_frame)

    return swapped_sequence

def group_valid_ratio(mat: np.ndarray, prefix: str) -> float:
    """
    Returns how much of a feature group is present in a matrix.
    Example prefixes:
    - "left_shape:"
    - "right_shape:"
    """
    cols = []

    for i, key in enumerate(FEATURE_KEYS):
        if key.startswith(prefix):
            cols.extend([i * 3, i * 3 + 1, i * 3 + 2])

    if not cols:
        return 0.0

    sub = mat[:, cols]
    total = sub.size

    if total == 0:
        return 0.0

    valid = np.isfinite(sub).sum()
    return float(valid / total)


def has_hand_group(mat: np.ndarray, prefix: str, threshold: float = 0.15) -> bool:
    return group_valid_ratio(mat, prefix) >= threshold


def hand_count_penalty(query: np.ndarray, template: np.ndarray) -> float:
    """
    Penalize mismatches between one-hand and two-hand signs.

    This fixes cases like:
    - live family uses two hands
    - mother template uses one hand
    - mother wins only because one hand shape is close
    """
    q_left = has_hand_group(query, "left_shape:")
    q_right = has_hand_group(query, "right_shape:")

    t_left = has_hand_group(template, "left_shape:")
    t_right = has_hand_group(template, "right_shape:")

    q_count = int(q_left) + int(q_right)
    t_count = int(t_left) + int(t_right)

    # Live two-hand sign vs one-hand template
    if q_count == 2 and t_count == 1:
        return 0.28

    # Live one-hand sign vs two-hand template
    if q_count == 1 and t_count == 2:
        return 0.32

    # Strong mismatch / missing hands
    if q_count == 0 or t_count == 0:
        return 0.40

    return 0.0


def predict(
    sequence: List[Dict[str, List[float]]],
    templates: List[dict],
    target_len: int,
    top_k: int = 5,
) -> List[dict]:
    query_normal = features_to_matrix(sequence)
    query_normal = resample_matrix(query_normal, target_len)

    swapped_sequence = swap_left_right_features(sequence)
    query_swapped = features_to_matrix(swapped_sequence)
    query_swapped = resample_matrix(query_swapped, target_len)

    results = []

    for tpl in templates:
        tpl_matrix = tpl["matrix"]

        d_normal_base = weighted_sequence_distance(query_normal, tpl_matrix)
        d_swapped_base = weighted_sequence_distance(query_swapped, tpl_matrix)

        penalty_normal = hand_count_penalty(query_normal, tpl_matrix)
        penalty_swapped = hand_count_penalty(query_swapped, tpl_matrix)

        d_normal = d_normal_base + penalty_normal
        d_swapped = d_swapped_base + penalty_swapped

        debug_normal = group_distance_debug(query_normal, tpl_matrix)
        debug_swapped = group_distance_debug(query_swapped, tpl_matrix)

        if d_swapped < d_normal:
            d = d_swapped
            base_distance = d_swapped_base
            penalty = penalty_swapped
            mode = "swapped"
            debug = debug_swapped
        else:
            d = d_normal
            base_distance = d_normal_base
            penalty = penalty_normal
            mode = "normal"
            debug = debug_normal

        conf = confidence_from_distance(d)

        if math.isfinite(d):
            results.append({
                "word": tpl["word"],
                "video_id": tpl["video_id"],
                "distance": d,
                "base_distance": base_distance,
                "penalty": penalty,
                "confidence": conf,
                "mode": mode,
                "debug": debug,
                "path": tpl["path"],
            })

    results.sort(key=lambda x: x["distance"])
    return results[:top_k]

# =========================
# UI drawing
# =========================

def draw_text_panel(frame, lines: List[str]) -> None:
    x = 18
    y = 34
    line_height = 31

    # translucent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (8, 8), (frame.shape[1] - 8, 170), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

    for line in lines:
        cv2.putText(
            frame,
            line,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        y += line_height


def draw_recording_bar(frame, progress: float) -> None:
    h, w = frame.shape[:2]
    progress = max(0.0, min(1.0, progress))

    x1, y1 = 20, h - 35
    x2, y2 = w - 20, h - 18

    cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 80, 80), -1)
    cv2.rectangle(frame, (x1, y1), (int(x1 + (x2 - x1) * progress), y2), (0, 255, 0), -1)


def process_video_file(
    video_path: str,
    pose,
    hands,
    templates: List[dict],
    target_len: int,
    top_k: int,
    mirror: bool = False,
) -> None:
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    sequence = []
    frame_count = 0
    valid_count = 0

    mp_pose = mp.solutions.pose
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_count += 1

        if mirror:
            frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False

        pose_res = pose.process(rgb)
        hands_res = hands.process(rgb)

        rgb.flags.writeable = True

        pose_points = None

        if pose_res.pose_landmarks:
            pose_points = [lm_to_point(lm) for lm in pose_res.pose_landmarks.landmark]
            mp_draw.draw_landmarks(frame, pose_res.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        left_hand, right_hand = assign_hands(
            hands_res.multi_hand_landmarks if hands_res.multi_hand_landmarks else None,
            hands_res.multi_handedness if hands_res.multi_handedness else None,
            pose_points,
        )

        if hands_res.multi_hand_landmarks:
            for hand_lm in hands_res.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)

        features = extract_hand_first_features(
            pose_points=pose_points,
            left_hand=left_hand,
            right_hand=right_hand,
        )

        if features is not None:
            sequence.append(features)
            valid_count += 1

        lines = [
            "Gestura Video Test Mode",
            f"Video: {video_path}",
            f"Frames: {frame_count}",
            f"Valid hand frames: {valid_count}",
        ]

        draw_text_panel(frame, lines)
        cv2.imshow("Gestura Video Test", frame)

        key = cv2.waitKey(20) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyWindow("Gestura Video Test")

    print(f"\n[VIDEO TEST]")
    print(f"Total frames: {frame_count}")
    print(f"Valid feature frames: {len(sequence)}")

    if len(sequence) < 5:
        print("[ERROR] Too few valid frames extracted from video")
        return

    top = predict(
        sequence=sequence,
        templates=templates,
        target_len=target_len,
        top_k=top_k,
    )

    print("\n[PREDICTION FROM FULL VIDEO]")
    for i, r in enumerate(top, 1):
        print(
            f"{i}. {r['word']:<14} "
            f"conf={r['confidence']:5.1f}% "
            f"dist={r['distance']:.4f} "
            f"mode={r.get('mode', '-'):<8} "
            f"id={r['video_id']}"
        )

        dbg = r.get("debug", {})
        print(
            f"   groups: "
            f"Lshape={dbg.get('left_shape', float('nan')):.4f} | "
            f"Rshape={dbg.get('right_shape', float('nan')):.4f} | "
            f"space={dbg.get('space', float('nan')):.4f} | "
            f"body={dbg.get('body', float('nan')):.4f}"
        )


# =========================
# Main
# =========================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gestura hand-first Sign-to-Text webcam prototype"
    )

    parser.add_argument("--camera", default="0")
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--resample", type=int, default=32)
    parser.add_argument("--templates", default="data/clean_skeletons")
    parser.add_argument("--map", default="../app/src/main/assets/video_id_to_word.json")
    parser.add_argument("--words", nargs="*", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-confidence", type=float, default=35.0)
    parser.add_argument("--mirror", action="store_true", help="Mirror webcam preview")
    parser.add_argument("--min-frames", type=int, default=8)
    parser.add_argument("--auto-video", action="store_true", help="Automatically process the full video file without pressing SPACE")
    parser.add_argument("--min-margin", type=float, default=0.0)
    parser.add_argument("--use-motion", action="store_true")
    parser.add_argument("--use-contact", action="store_true")
    parser.add_argument("--debug-distances", action="store_true")
    parser.add_argument("--practice-target", default=None, help="Target word to practice and get specific match score")
    parser.add_argument("--practice-min-confidence", type=float, default=45.0)
    parser.add_argument("--practice-min-margin", type=float, default=8.0)

    args = parser.parse_args()

    templates_dir = Path(args.templates)
    map_path = Path(args.map)

    if not map_path.exists():
        fallback = Path("data/video_id_to_word.json")
        if fallback.exists():
            map_path = fallback

    print("[INFO] Loading video_id_to_word:", map_path)
    id_to_word = load_video_id_to_word(map_path)

    print("[INFO] Loading templates from:", templates_dir)
    templates = load_templates(
        templates_dir=templates_dir,
        id_to_word=id_to_word,
        target_len=args.resample,
        allowed_words=args.words,
    )

    print(f"[OK] Loaded {len(templates)} templates")

    if args.words:
        print("[INFO] Allowed demo words:", ", ".join(args.words))

    if args.practice_target:
        print(f"[INFO] Practice mode active! Target: {args.practice_target.upper()}")
        # Ensure the target word is in the allowed words if --words was used
        if args.words and args.practice_target.lower() not in [w.lower() for w in args.words]:
            print(f"[WARN] Practice target '{args.practice_target}' not in --words list. Results might be limited.")

    print("[INFO] Controls:")
    print("  SPACE = record sign")
    print("  Q     = quit")

    mp_pose = mp.solutions.pose
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    camera_source = int(args.camera) if str(args.camera).isdigit() else args.camera
    cap = cv2.VideoCapture(camera_source)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {args.camera}")

    recording = False
    record_start = 0.0
    record_until = 0.0
    current_sequence: List[Dict[str, List[float]]] = []

    last_prediction = "No prediction yet"
    last_top_results: List[dict] = []

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        enable_segmentation=False,
        min_detection_confidence=0.45,
        min_tracking_confidence=0.45,
    ) as pose, mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=1,
        min_detection_confidence=0.45,
        min_tracking_confidence=0.45,
    ) as hands:

        if args.auto_video and not str(args.camera).isdigit():
            process_video_file(
                video_path=str(args.camera),
                pose=pose,
                hands=hands,
                templates=templates,
                target_len=args.resample,
                top_k=args.top_k,
                mirror=args.mirror,
            )
            return

        while True:
            ok, frame = cap.read()

            if not ok:
                print("[ERROR] Failed to read camera frame")
                break

            if args.mirror:
                frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False

            pose_res = pose.process(rgb)
            hands_res = hands.process(rgb)

            rgb.flags.writeable = True

            pose_points = None

            if pose_res.pose_landmarks:
                pose_points = [lm_to_point(lm) for lm in pose_res.pose_landmarks.landmark]
                mp_draw.draw_landmarks(
                    frame,
                    pose_res.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                )

            left_hand, right_hand = assign_hands(
                hands_res.multi_hand_landmarks if hands_res.multi_hand_landmarks else None,
                hands_res.multi_handedness if hands_res.multi_handedness else None,
                pose_points,
            )

            if hands_res.multi_hand_landmarks:
                for hand_lm in hands_res.multi_hand_landmarks:
                    mp_draw.draw_landmarks(
                        frame,
                        hand_lm,
                        mp_hands.HAND_CONNECTIONS,
                    )

            features = extract_hand_first_features(
                pose_points=pose_points,
                left_hand=left_hand,
                right_hand=right_hand,
            )

            now = time.time()

            if recording:
                if features is not None:
                    current_sequence.append(features)

                if now >= record_until:
                    recording = False

                    if len(current_sequence) >= args.min_frames:
                        top = predict(
                            sequence=current_sequence,
                            templates=templates,
                            target_len=args.resample,
                            top_k=args.top_k,
                        )

                        last_top_results = top

                        if top:
                            best = top[0]

                            print("\n[PREDICTION]")
                            for i, r in enumerate(top, 1):
                                print(
                                    f"{i}. {r['word']:<14} "
                                    f"conf={r['confidence']:5.1f}% "
                                    f"dist={r['distance']:.4f} "
                                    f"base={r.get('base_distance', r['distance']):.4f} "
                                    f"penalty={r.get('penalty', 0.0):.2f} "
                                    f"mode={r.get('mode', '-'):<8} "
                                    f"id={r['video_id']}"
                                )

                                dbg = r.get("debug", {})
                                print(
                                    f"   groups: "
                                    f"Lshape={dbg.get('left_shape', float('nan')):.4f} | "
                                    f"Rshape={dbg.get('right_shape', float('nan')):.4f} | "
                                    f"space={dbg.get('space', float('nan')):.4f} | "
                                    f"body={dbg.get('body', float('nan')):.4f}"
                                )

                            if best["confidence"] >= args.min_confidence:
                                last_prediction = f"{best['word']} ({best['confidence']:.1f}%)"
                            else:
                                last_prediction = (
                                    f"No confident match "
                                    f"(best: {best['word']} {best['confidence']:.1f}%)"
                                )

                            if args.practice_target:
                                target_word = args.practice_target.lower().strip()
                                # Find target in top results or search all results
                                target_match = None
                                # Re-calculate for target if not in top
                                for r in top:
                                    if r["word"] == target_word:
                                        target_match = r
                                        break
                                
                                if not target_match:
                                    # Fallback: search the templates to get the score even if it's very bad
                                    full_results = predict(
                                        sequence=current_sequence,
                                        templates=templates,
                                        target_len=args.resample,
                                        top_k=len(templates)
                                    )
                                    for r in full_results:
                                        if r["word"] == target_word:
                                            target_match = r
                                            break
                                
                                if target_match:
                                    last_prediction = f"Practice '{target_word.upper()}': {target_match['confidence']:.1f}% Match"
                                    print(f"\n[PRACTICE RESULT] Target: {target_word.upper()} | Score: {target_match['confidence']:.1f}%")
                                else:
                                    last_prediction = f"Target '{target_word}' not found in database"
                        else:
                            last_prediction = "No confident match"
                            print("[WARN] No confident match")

                    else:
                        last_prediction = "Too few valid hand frames"
                        last_top_results = []
                        print("[WARN] Too few valid hand frames")

            hand_status = []
            if left_hand is not None:
                hand_status.append("L")
            if right_hand is not None:
                hand_status.append("R")

            hand_status_text = "Hands: " + ("+".join(hand_status) if hand_status else "none")

            lines = [
                "Gestura Sign-to-Text — Hand-First Backend",
                "SPACE: record sign | Q: quit",
                hand_status_text,
                f"Prediction: {last_prediction}",
            ]

            if recording:
                lines.append(f"Recording... frames={len(current_sequence)}")
            else:
                lines.append("Ready — keep hands visible")

            if last_top_results:
                compact = " | ".join(
                    [f"{r['word']} {r['confidence']:.0f}%" for r in last_top_results[:3]]
                )
                lines.append(f"Top: {compact}")

            draw_text_panel(frame, lines)

            if recording:
                progress = (now - record_start) / max(0.001, args.seconds)
                draw_recording_bar(frame, progress)

            cv2.imshow("Gestura Sign-to-Text", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == 32 and not recording:
                current_sequence = []
                recording = True
                record_start = time.time()
                record_until = record_start + args.seconds
                last_prediction = "Recording..."
                last_top_results = []

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()