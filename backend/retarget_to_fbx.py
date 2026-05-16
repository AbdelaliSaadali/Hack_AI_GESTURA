#!/usr/bin/env python3
"""
retarget_to_fbx.py

Blender retargeting script for Gestura clean skeleton JSON -> rigged FBX avatar.

Main idea:
- import the avatar FBX
- detect or load a bone map
- create helper empties for source joints from the clean JSON
- animate those empties frame by frame
- constrain avatar bones to track those empties
- bake the animation
- export a new animated FBX

Run from Blender:

    blender --background --python retarget_to_fbx.py -- \
      --fbx /abs/path/avatar.fbx \
      --motion_json /abs/path/69206_avatar.json \
      --output_fbx /abs/path/69206_animated.fbx

Useful helper modes:

    blender --background --python retarget_to_fbx.py -- \
      --fbx /abs/path/avatar.fbx \
      --list_bones

    blender --background --python retarget_to_fbx.py -- \
      --fbx /abs/path/avatar.fbx \
      --write_bone_map /abs/path/avatar_bone_map.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
from mathutils import Vector


# ----------------------------------------------------------------------
# Source landmark aliases
# ----------------------------------------------------------------------

POSE_INDEX = {
    "nose": 0,
    "left_eye_inner": 1,
    "left_eye": 2,
    "left_eye_outer": 3,
    "right_eye_inner": 4,
    "right_eye": 5,
    "right_eye_outer": 6,
    "left_ear": 7,
    "right_ear": 8,
    "mouth_left": 9,
    "mouth_right": 10,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_pinky": 17,
    "right_pinky": 18,
    "left_index": 19,
    "right_index": 20,
    "left_thumb": 21,
    "right_thumb": 22,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_heel": 29,
    "right_heel": 30,
    "left_foot_index": 31,
    "right_foot_index": 32,
}

HAND_INDEX = {
    "wrist": 0,
    "thumb_cmc": 1,
    "thumb_mcp": 2,
    "thumb_ip": 3,
    "thumb_tip": 4,
    "index_mcp": 5,
    "index_pip": 6,
    "index_dip": 7,
    "index_tip": 8,
    "middle_mcp": 9,
    "middle_pip": 10,
    "middle_dip": 11,
    "middle_tip": 12,
    "ring_mcp": 13,
    "ring_pip": 14,
    "ring_dip": 15,
    "ring_tip": 16,
    "pinky_mcp": 17,
    "pinky_pip": 18,
    "pinky_dip": 19,
    "pinky_tip": 20,
}


# ----------------------------------------------------------------------
# Canonical avatar bones -> source targets
# These targets are used when auto-detecting a rig.
# ----------------------------------------------------------------------

CANONICAL_TARGETS = {
    "hips": {"target": "mid(pose.left_hip,pose.right_hip)", "track_axis": "TRACK_Y"},
    "spine": {"target": "mid(pose.left_shoulder,pose.right_shoulder)", "track_axis": "TRACK_Y"},
    "chest": {"target": "mid(pose.left_shoulder,pose.right_shoulder)", "track_axis": "TRACK_Y"},
    "neck": {"target": "pose.nose", "track_axis": "TRACK_Y"},
    "head": {"target": "pose.nose", "track_axis": "TRACK_Y"},

    "left_upper_arm": {"target": "pose.left_elbow", "track_axis": "TRACK_Y"},
    "left_forearm": {"target": "pose.left_wrist", "track_axis": "TRACK_Y"},
    "left_hand": {"target": "left_hand.middle_mcp", "track_axis": "TRACK_Y"},

    "right_upper_arm": {"target": "pose.right_elbow", "track_axis": "TRACK_Y"},
    "right_forearm": {"target": "pose.right_wrist", "track_axis": "TRACK_Y"},
    "right_hand": {"target": "right_hand.middle_mcp", "track_axis": "TRACK_Y"},

    "left_thumb_1": {"target": "left_hand.thumb_mcp", "track_axis": "TRACK_Y"},
    "left_thumb_2": {"target": "left_hand.thumb_ip", "track_axis": "TRACK_Y"},
    "left_thumb_3": {"target": "left_hand.thumb_tip", "track_axis": "TRACK_Y"},

    "left_index_1": {"target": "left_hand.index_pip", "track_axis": "TRACK_Y"},
    "left_index_2": {"target": "left_hand.index_dip", "track_axis": "TRACK_Y"},
    "left_index_3": {"target": "left_hand.index_tip", "track_axis": "TRACK_Y"},

    "left_middle_1": {"target": "left_hand.middle_pip", "track_axis": "TRACK_Y"},
    "left_middle_2": {"target": "left_hand.middle_dip", "track_axis": "TRACK_Y"},
    "left_middle_3": {"target": "left_hand.middle_tip", "track_axis": "TRACK_Y"},

    "left_ring_1": {"target": "left_hand.ring_pip", "track_axis": "TRACK_Y"},
    "left_ring_2": {"target": "left_hand.ring_dip", "track_axis": "TRACK_Y"},
    "left_ring_3": {"target": "left_hand.ring_tip", "track_axis": "TRACK_Y"},

    "left_pinky_1": {"target": "left_hand.pinky_pip", "track_axis": "TRACK_Y"},
    "left_pinky_2": {"target": "left_hand.pinky_dip", "track_axis": "TRACK_Y"},
    "left_pinky_3": {"target": "left_hand.pinky_tip", "track_axis": "TRACK_Y"},

    "right_thumb_1": {"target": "right_hand.thumb_mcp", "track_axis": "TRACK_Y"},
    "right_thumb_2": {"target": "right_hand.thumb_ip", "track_axis": "TRACK_Y"},
    "right_thumb_3": {"target": "right_hand.thumb_tip", "track_axis": "TRACK_Y"},

    "right_index_1": {"target": "right_hand.index_pip", "track_axis": "TRACK_Y"},
    "right_index_2": {"target": "right_hand.index_dip", "track_axis": "TRACK_Y"},
    "right_index_3": {"target": "right_hand.index_tip", "track_axis": "TRACK_Y"},

    "right_middle_1": {"target": "right_hand.middle_pip", "track_axis": "TRACK_Y"},
    "right_middle_2": {"target": "right_hand.middle_dip", "track_axis": "TRACK_Y"},
    "right_middle_3": {"target": "right_hand.middle_tip", "track_axis": "TRACK_Y"},

    "right_ring_1": {"target": "right_hand.ring_pip", "track_axis": "TRACK_Y"},
    "right_ring_2": {"target": "right_hand.ring_dip", "track_axis": "TRACK_Y"},
    "right_ring_3": {"target": "right_hand.ring_tip", "track_axis": "TRACK_Y"},

    "right_pinky_1": {"target": "right_hand.pinky_pip", "track_axis": "TRACK_Y"},
    "right_pinky_2": {"target": "right_hand.pinky_dip", "track_axis": "TRACK_Y"},
    "right_pinky_3": {"target": "right_hand.pinky_tip", "track_axis": "TRACK_Y"},
}


# ----------------------------------------------------------------------
# Auto-detection aliases for common rigs (Mixamo-like + common variants)
# ----------------------------------------------------------------------

AUTO_BONE_ALIASES = {
    "hips": [
        "hips", "pelvis", "root", "mixamorig:Hips", "c_hips", "hip", "spine_root"
    ],
    "spine": [
        "spine", "spine1", "spine01", "mixamorig:Spine", "abdomen", "torso"
    ],
    "chest": [
        "spine2", "chest", "spine02", "upperchest", "mixamorig:Spine1", "mixamorig:Spine2"
    ],
    "neck": [
        "neck", "mixamorig:Neck"
    ],
    "head": [
        "head", "mixamorig:Head"
    ],

    "left_upper_arm": [
        "mixamorig:LeftArm", "leftarm", "left_upper_arm", "upperarm_l", "arm_l", "l_upperarm"
    ],
    "left_forearm": [
        "mixamorig:LeftForeArm", "leftforearm", "left_lower_arm", "forearm_l", "lowerarm_l", "l_forearm"
    ],
    "left_hand": [
        "mixamorig:LeftHand", "lefthand", "hand_l", "l_hand"
    ],

    "right_upper_arm": [
        "mixamorig:RightArm", "rightarm", "right_upper_arm", "upperarm_r", "arm_r", "r_upperarm"
    ],
    "right_forearm": [
        "mixamorig:RightForeArm", "rightforearm", "right_lower_arm", "forearm_r", "lowerarm_r", "r_forearm"
    ],
    "right_hand": [
        "mixamorig:RightHand", "righthand", "hand_r", "r_hand"
    ],

    "left_thumb_1": [
        "mixamorig:LeftHandThumb1", "lefthandthumb1", "thumb.01.L", "thumb1_l", "l_thumb1"
    ],
    "left_thumb_2": [
        "mixamorig:LeftHandThumb2", "lefthandthumb2", "thumb.02.L", "thumb2_l", "l_thumb2"
    ],
    "left_thumb_3": [
        "mixamorig:LeftHandThumb3", "lefthandthumb3", "thumb.03.L", "thumb3_l", "l_thumb3"
    ],

    "left_index_1": [
        "mixamorig:LeftHandIndex1", "lefthandindex1", "f_index.01.L", "index1_l", "l_index1"
    ],
    "left_index_2": [
        "mixamorig:LeftHandIndex2", "lefthandindex2", "f_index.02.L", "index2_l", "l_index2"
    ],
    "left_index_3": [
        "mixamorig:LeftHandIndex3", "lefthandindex3", "f_index.03.L", "index3_l", "l_index3"
    ],

    "left_middle_1": [
        "mixamorig:LeftHandMiddle1", "lefthandmiddle1", "f_middle.01.L", "middle1_l", "l_middle1"
    ],
    "left_middle_2": [
        "mixamorig:LeftHandMiddle2", "lefthandmiddle2", "f_middle.02.L", "middle2_l", "l_middle2"
    ],
    "left_middle_3": [
        "mixamorig:LeftHandMiddle3", "lefthandmiddle3", "f_middle.03.L", "middle3_l", "l_middle3"
    ],

    "left_ring_1": [
        "mixamorig:LeftHandRing1", "lefthandring1", "f_ring.01.L", "ring1_l", "l_ring1"
    ],
    "left_ring_2": [
        "mixamorig:LeftHandRing2", "lefthandring2", "f_ring.02.L", "ring2_l", "l_ring2"
    ],
    "left_ring_3": [
        "mixamorig:LeftHandRing3", "lefthandring3", "f_ring.03.L", "ring3_l", "l_ring3"
    ],

    "left_pinky_1": [
        "mixamorig:LeftHandPinky1", "lefthandpinky1", "f_pinky.01.L", "pinky1_l", "l_pinky1"
    ],
    "left_pinky_2": [
        "mixamorig:LeftHandPinky2", "lefthandpinky2", "f_pinky.02.L", "pinky2_l", "l_pinky2"
    ],
    "left_pinky_3": [
        "mixamorig:LeftHandPinky3", "lefthandpinky3", "f_pinky.03.L", "pinky3_l", "l_pinky3"
    ],

    "right_thumb_1": [
        "mixamorig:RightHandThumb1", "righthandthumb1", "thumb.01.R", "thumb1_r", "r_thumb1"
    ],
    "right_thumb_2": [
        "mixamorig:RightHandThumb2", "righthandthumb2", "thumb.02.R", "thumb2_r", "r_thumb2"
    ],
    "right_thumb_3": [
        "mixamorig:RightHandThumb3", "righthandthumb3", "thumb.03.R", "thumb3_r", "r_thumb3"
    ],

    "right_index_1": [
        "mixamorig:RightHandIndex1", "righthandindex1", "f_index.01.R", "index1_r", "r_index1"
    ],
    "right_index_2": [
        "mixamorig:RightHandIndex2", "righthandindex2", "f_index.02.R", "index2_r", "r_index2"
    ],
    "right_index_3": [
        "mixamorig:RightHandIndex3", "righthandindex3", "f_index.03.R", "index3_r", "r_index3"
    ],

    "right_middle_1": [
        "mixamorig:RightHandMiddle1", "righthandmiddle1", "f_middle.01.R", "middle1_r", "r_middle1"
    ],
    "right_middle_2": [
        "mixamorig:RightHandMiddle2", "righthandmiddle2", "f_middle.02.R", "middle2_r", "r_middle2"
    ],
    "right_middle_3": [
        "mixamorig:RightHandMiddle3", "righthandmiddle3", "f_middle.03.R", "middle3_r", "r_middle3"
    ],

    "right_ring_1": [
        "mixamorig:RightHandRing1", "righthandring1", "f_ring.01.R", "ring1_r", "r_ring1"
    ],
    "right_ring_2": [
        "mixamorig:RightHandRing2", "righthandring2", "f_ring.02.R", "ring2_r", "r_ring2"
    ],
    "right_ring_3": [
        "mixamorig:RightHandRing3", "righthandring3", "f_ring.03.R", "ring3_r", "r_ring3"
    ],

    "right_pinky_1": [
        "mixamorig:RightHandPinky1", "righthandpinky1", "f_pinky.01.R", "pinky1_r", "r_pinky1"
    ],
    "right_pinky_2": [
        "mixamorig:RightHandPinky2", "righthandpinky2", "f_pinky.02.R", "pinky2_r", "r_pinky2"
    ],
    "right_pinky_3": [
        "mixamorig:RightHandPinky3", "righthandpinky3", "f_pinky.03.R", "pinky3_r", "r_pinky3"
    ],
}


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[retarget_to_fbx] {msg}")


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_")


def is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def is_point(p: Any) -> bool:
    return isinstance(p, (list, tuple)) and len(p) >= 2 and is_number(p[0]) and is_number(p[1])


def point3(p: Any) -> Optional[List[float]]:
    if not is_point(p):
        return None
    x = float(p[0])
    y = float(p[1])
    z = float(p[2]) if len(p) >= 3 and is_number(p[2]) else 0.0
    return [x, y, z]


def clear_scene() -> None:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.armatures:
        if block.users == 0:
            bpy.data.armatures.remove(block)
    for block in bpy.data.actions:
        if block.users == 0:
            bpy.data.actions.remove(block)


def import_fbx(filepath: str) -> List[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=filepath, automatic_bone_orientation=False)
    after = set(bpy.data.objects)
    imported = list(after - before)
    if not imported:
        raise RuntimeError(f"No objects imported from FBX: {filepath}")
    return imported


def find_armature(imported: List[bpy.types.Object], armature_name: Optional[str] = None) -> bpy.types.Object:
    armatures = [obj for obj in imported if obj.type == 'ARMATURE']
    if not armatures:
        raise RuntimeError("No armature found in imported FBX.")

    if armature_name:
        for obj in armatures:
            if obj.name == armature_name:
                return obj

    # Prefer first armature with most bones
    armatures.sort(key=lambda o: len(o.data.bones), reverse=True)
    return armatures[0]


def list_bones(armature: bpy.types.Object) -> None:
    log(f"Armature: {armature.name}")
    for bone in armature.data.bones:
        print(bone.name)


def find_frames(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("frames", "clean_frames"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    raise RuntimeError("Could not find frame list under 'frames' or 'clean_frames'.")


def load_motion_json(path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    frames = find_frames(data)
    if not frames:
        raise RuntimeError("Motion JSON contains zero frames.")
    return data, frames


def get_from_container(container: Any, key: str, alias_map: Dict[str, int]) -> Optional[List[float]]:
    if isinstance(container, dict):
        return point3(container.get(key))

    if isinstance(container, list):
        if key in alias_map:
            idx = alias_map[key]
            if 0 <= idx < len(container):
                return point3(container[idx])

    return None


def split_top_level_args(s: str) -> List[str]:
    out = []
    current = []
    depth = 0
    for ch in s:
        if ch == ',' and depth == 0:
            out.append("".join(current).strip())
            current = []
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        current.append(ch)
    if current:
        out.append("".join(current).strip())
    return out


def resolve_expr(frame: Dict[str, Any], expr: str) -> Optional[List[float]]:
    expr = expr.strip()

    if expr.startswith("mid(") and expr.endswith(")"):
        inner = expr[4:-1].strip()
        parts = split_top_level_args(inner)
        if len(parts) != 2:
            return None
        a = resolve_expr(frame, parts[0])
        b = resolve_expr(frame, parts[1])
        if a is None or b is None:
            return None
        return [
            0.5 * (a[0] + b[0]),
            0.5 * (a[1] + b[1]),
            0.5 * (a[2] + b[2]),
        ]

    if expr.startswith("avg(") and expr.endswith(")"):
        inner = expr[4:-1].strip()
        parts = split_top_level_args(inner)
        pts = [resolve_expr(frame, p) for p in parts]
        pts = [p for p in pts if p is not None]
        if not pts:
            return None
        n = len(pts)
        return [
            sum(p[0] for p in pts) / n,
            sum(p[1] for p in pts) / n,
            sum(p[2] for p in pts) / n,
        ]

    parts = expr.split(".")
    if len(parts) == 1:
        # Implicit pose alias
        pose = frame.get("pose")
        p = get_from_container(pose, parts[0], POSE_INDEX)
        if p is not None:
            return p
        # Implicit hand aliases are ambiguous, so skip
        return None

    root = parts[0]
    rest = parts[1:]

    if root == "pose":
        container = frame.get("pose")
        if len(rest) != 1:
            return None
        return get_from_container(container, rest[0], POSE_INDEX)

    if root in ("left_hand", "right_hand"):
        container = frame.get(root)
        if len(rest) != 1:
            return None
        return get_from_container(container, rest[0], HAND_INDEX)

    # other named containers if present
    container = frame.get(root)
    if isinstance(container, dict) and len(rest) == 1:
        return point3(container.get(rest[0]))

    return None


def source_to_blender_vec(
    p: List[float],
    screen_scale: float,
    depth_scale: float,
    mirror_x: bool,
) -> Vector:
    x = float(p[0]) - 0.5
    y = float(p[1]) - 0.5
    z = float(p[2])

    bx = (-x if mirror_x else x) * screen_scale
    by = (-z) * depth_scale
    bz = (-y) * screen_scale

    return Vector((bx, by, bz))


def first_valid_anchor(
    frames: List[Dict[str, Any]],
    anchor_expr: str,
    screen_scale: float,
    depth_scale: float,
    mirror_x: bool,
) -> Vector:
    for frame in frames:
        p = resolve_expr(frame, anchor_expr)
        if p is not None:
            return source_to_blender_vec(p, screen_scale, depth_scale, mirror_x)
    return Vector((0.0, 0.0, 0.0))


def create_empty(name: str, location: Vector) -> bpy.types.Object:
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.empty_display_size = 0.03
    obj.hide_render = True
    return obj


def remove_rt_constraints(armature: bpy.types.Object) -> None:
    for pbone in armature.pose.bones:
        for con in list(pbone.constraints):
            if con.name.startswith("GESTURA_RT_"):
                pbone.constraints.remove(con)


def deselect_all() -> None:
    for obj in bpy.context.selected_objects:
        obj.select_set(False)


def make_bone_lookup(armature: bpy.types.Object) -> Dict[str, str]:
    return {normalize_name(b.name): b.name for b in armature.data.bones}


def find_bone_by_aliases(armature: bpy.types.Object, aliases: List[str]) -> Optional[str]:
    bones = list(armature.data.bones)
    if not bones:
        return None

    exact = {normalize_name(b.name): b.name for b in bones}

    for alias in aliases:
        na = normalize_name(alias)
        if na in exact:
            return exact[na]

    # endswith fallback
    for alias in aliases:
        na = normalize_name(alias)
        for bone in bones:
            nb = normalize_name(bone.name)
            if nb.endswith(na):
                return bone.name

    # contains fallback
    for alias in aliases:
        na = normalize_name(alias)
        for bone in bones:
            nb = normalize_name(bone.name)
            if na in nb:
                return bone.name

    return None


def auto_build_bone_map(armature: bpy.types.Object) -> Dict[str, Any]:
    mapping = {
        "armature_name": armature.name,
        "root_bone": None,
        "root_source": "mid(pose.left_hip,pose.right_hip)",
        "default_track_axis": "TRACK_Y",
        "bones": []
    }

    for canonical_name, aliases in AUTO_BONE_ALIASES.items():
        bone_name = find_bone_by_aliases(armature, aliases)
        if bone_name is None:
            continue

        if canonical_name == "hips":
            mapping["root_bone"] = bone_name

        target_info = CANONICAL_TARGETS.get(canonical_name)
        if not target_info:
            continue

        mapping["bones"].append({
            "canonical": canonical_name,
            "bone": bone_name,
            "target": target_info["target"],
            "track_axis": target_info.get("track_axis", "TRACK_Y"),
        })

    return mapping


def write_json(path: str, data: Dict[str, Any]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_bone_map(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_bone_exists(armature: bpy.types.Object, bone_name: str) -> None:
    if bone_name not in armature.pose.bones:
        raise RuntimeError(f"Bone '{bone_name}' not found in armature '{armature.name}'.")


def create_helper_empties(
    frames: List[Dict[str, Any]],
    bone_map: Dict[str, Any],
    frame_start: int,
    fps: int,
    screen_scale: float,
    depth_scale: float,
    mirror_x: bool,
) -> Tuple[Dict[str, bpy.types.Object], Optional[bpy.types.Object], int]:
    scene = bpy.context.scene
    scene.render.fps = fps

    exprs = []
    for entry in bone_map.get("bones", []):
        target_expr = entry.get("target")
        if target_expr:
            exprs.append(target_expr)

    root_expr = bone_map.get("root_source")
    if root_expr:
        exprs.append(root_expr)

    unique_exprs = []
    seen = set()
    for expr in exprs:
        if expr not in seen:
            seen.add(expr)
            unique_exprs.append(expr)

    anchor_expr = root_expr or "mid(pose.left_hip,pose.right_hip)"
    anchor0 = first_valid_anchor(frames, anchor_expr, screen_scale, depth_scale, mirror_x)

    expr_to_empty: Dict[str, bpy.types.Object] = {}
    last_valid_locations: Dict[str, Vector] = {}

    for expr in unique_exprs:
        empty_name = f"RT_{slugify(expr)}"
        expr_to_empty[expr] = create_empty(empty_name, Vector((0.0, 0.0, 0.0)))

    root_empty = expr_to_empty.get(root_expr) if root_expr else None

    frame_end = frame_start + len(frames) - 1

    for i, frame in enumerate(frames):
        scene_frame = frame_start + i
        scene.frame_set(scene_frame)

        for expr, empty in expr_to_empty.items():
            src = resolve_expr(frame, expr)
            if src is not None:
                loc = source_to_blender_vec(src, screen_scale, depth_scale, mirror_x) - anchor0
                last_valid_locations[expr] = loc
            else:
                loc = last_valid_locations.get(expr)

            if loc is None:
                continue

            empty.location = loc
            empty.keyframe_insert(data_path="location", frame=scene_frame)

    return expr_to_empty, root_empty, frame_end


def apply_constraints(
    armature: bpy.types.Object,
    bone_map: Dict[str, Any],
    expr_to_empty: Dict[str, bpy.types.Object],
    root_empty: Optional[bpy.types.Object],
    root_location_strength: float,
) -> None:
    remove_rt_constraints(armature)

    root_bone_name = bone_map.get("root_bone")
    if root_bone_name and root_empty is not None and root_bone_name in armature.pose.bones:
        pbone = armature.pose.bones[root_bone_name]

        con_loc = pbone.constraints.new('COPY_LOCATION')
        con_loc.name = "GESTURA_RT_ROOT_LOC"
        con_loc.target = root_empty
        con_loc.target_space = 'WORLD'
        con_loc.owner_space = 'WORLD'
        con_loc.influence = root_location_strength

    for entry in bone_map.get("bones", []):
        bone_name = entry.get("bone")
        target_expr = entry.get("target")
        track_axis = entry.get("track_axis", bone_map.get("default_track_axis", "TRACK_Y"))

        if not bone_name or not target_expr:
            continue
        if bone_name not in armature.pose.bones:
            continue
        if target_expr not in expr_to_empty:
            continue

        pbone = armature.pose.bones[bone_name]
        empty = expr_to_empty[target_expr]

        con = pbone.constraints.new('DAMPED_TRACK')
        con.name = f"GESTURA_RT_TRACK_{slugify(target_expr)}"
        con.target = empty
        con.track_axis = track_axis


def bake_pose_animation(
    armature: bpy.types.Object,
    frame_start: int,
    frame_end: int,
) -> None:
    bpy.context.view_layer.objects.active = armature
    deselect_all()
    armature.select_set(True)

    bpy.ops.object.mode_set(mode='POSE')

    for pbone in armature.pose.bones:
        pbone.bone.select = True

    bpy.ops.nla.bake(
        frame_start=frame_start,
        frame_end=frame_end,
        step=1,
        only_selected=False,
        visual_keying=True,
        clear_constraints=True,
        clear_parents=False,
        use_current_action=True,
        bake_types={'POSE'},
    )

    bpy.ops.object.mode_set(mode='OBJECT')


def delete_helper_empties(expr_to_empty: Dict[str, bpy.types.Object]) -> None:
    deselect_all()
    for obj in expr_to_empty.values():
        if obj and obj.name in bpy.data.objects:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)


def export_fbx(filepath: str) -> None:
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=False,
        bake_anim=True,
        add_leaf_bones=False,
        path_mode='AUTO',
        object_types={'ARMATURE', 'MESH'},
    )


def parse_blender_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser()

    parser.add_argument("--fbx", type=str, help="Path to input avatar FBX")
    parser.add_argument("--motion_json", type=str, help="Path to clean Gestura motion JSON (use *_avatar.json)")
    parser.add_argument("--output_fbx", type=str, help="Path to output animated FBX")
    parser.add_argument("--bone_map", type=str, default=None, help="Optional JSON file describing bone->target map")
    parser.add_argument("--write_bone_map", type=str, default=None, help="Write auto-detected bone map and exit")
    parser.add_argument("--armature", type=str, default=None, help="Optional armature object name")
    parser.add_argument("--list_bones", action="store_true", help="Print all bone names and exit")

    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--frame_start", type=int, default=1)

    parser.add_argument("--screen_scale", type=float, default=2.0,
                        help="Scale for x/z from normalized image coords")
    parser.add_argument("--depth_scale", type=float, default=1.2,
                        help="Scale for mediapipe z depth")
    parser.add_argument("--mirror_x", action="store_true",
                        help="Mirror horizontal motion if your avatar faces the opposite way")
    parser.add_argument("--root_location_strength", type=float, default=1.0,
                        help="Influence of root bone location copy constraint")

    return parser.parse_args(argv)


def validate_main_args(args: argparse.Namespace) -> None:
    if not args.fbx:
        raise RuntimeError("--fbx is required")
    if args.list_bones:
        return
    if args.write_bone_map:
        return
    if not args.motion_json:
        raise RuntimeError("--motion_json is required")
    if not args.output_fbx:
        raise RuntimeError("--output_fbx is required")


def main() -> None:
    args = parse_blender_args()
    validate_main_args(args)

    clear_scene()

    imported = import_fbx(args.fbx)
    armature = find_armature(imported, args.armature)

    log(f"Imported FBX: {args.fbx}")
    log(f"Using armature: {armature.name}")

    if args.list_bones:
        list_bones(armature)
        return

    auto_map = auto_build_bone_map(armature)

    if args.write_bone_map:
        write_json(args.write_bone_map, auto_map)
        log(f"Wrote bone map template: {args.write_bone_map}")
        return

    bone_map = load_bone_map(args.bone_map) if args.bone_map else auto_map

    if not bone_map.get("bones"):
        raise RuntimeError(
            "Bone map is empty. Run with --list_bones or --write_bone_map first, "
            "then edit the bone map manually."
        )

    motion_data, frames = load_motion_json(args.motion_json)
    log(f"Loaded motion frames: {len(frames)} from {args.motion_json}")

    expr_to_empty, root_empty, frame_end = create_helper_empties(
        frames=frames,
        bone_map=bone_map,
        frame_start=args.frame_start,
        fps=args.fps,
        screen_scale=args.screen_scale,
        depth_scale=args.depth_scale,
        mirror_x=args.mirror_x,
    )

    apply_constraints(
        armature=armature,
        bone_map=bone_map,
        expr_to_empty=expr_to_empty,
        root_empty=root_empty,
        root_location_strength=args.root_location_strength,
    )

    bpy.context.scene.frame_start = args.frame_start
    bpy.context.scene.frame_end = frame_end

    bake_pose_animation(
        armature=armature,
        frame_start=args.frame_start,
        frame_end=frame_end,
    )

    delete_helper_empties(expr_to_empty)

    export_fbx(args.output_fbx)
    log(f"Exported animated FBX: {args.output_fbx}")


if __name__ == "__main__":
    main()