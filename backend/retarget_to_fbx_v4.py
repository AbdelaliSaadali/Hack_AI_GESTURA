#!/usr/bin/env python3
"""
retarget_to_fbx_v4.py

Gestura Blender retargeting script: clean/avatar skeleton JSON -> animated FBX avatar.

Current v4 strategy:
1. Keep v3 finger animation.
2. Keep v2-style arm rotation normally.
3. Detect when hand is close to the face in the source skeleton.
4. During face-contact frames only, use controlled IK to pull the hand toward the avatar face.
5. Use a pole target so the elbow bends forward instead of behind the body.

Recommended test command:

"/Applications/Blender.app/Contents/MacOS/Blender" --background --python retarget_to_fbx_v4.py -- \
  --fbx avatar/source/Wolf3D_readyplayerme_male_01.fbx \
  --motion_json data/avatar_skeletons/69213_avatar.json \
  --output_fbx data/animated_fbx/69213_v4_contactik.fbx

If the hand still does not touch the face, increase:
  --contact_ik_strength 1.0 --face_contact_radius 1.7

If the elbow bends wrong, try:
  --pole_forward 0.45
or:
  --pole_forward -0.45
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
from mathutils import Matrix, Quaternion, Vector


# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[retarget_to_fbx_v4] {msg}")


# ----------------------------------------------------------------------
# Basic helpers
# ----------------------------------------------------------------------

def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def point3(value: Any) -> Optional[List[float]]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    if not is_number(value[0]) or not is_number(value[1]):
        return None
    x = float(value[0])
    y = float(value[1])
    z = float(value[2]) if len(value) >= 3 and is_number(value[2]) else 0.0
    if not all(math.isfinite(v) for v in (x, y, z)):
        return None
    if abs(x) + abs(y) + abs(z) < 1e-8:
        return None
    return [x, y, z]


def get_named_point(section: Any, name: str) -> Optional[List[float]]:
    if isinstance(section, dict):
        return point3(section.get(name))
    return None


def get_body_point(frame: Dict[str, Any], name: str) -> Optional[List[float]]:
    # Clean/avatar JSON usually has body joints in rig and/or pose.
    for section_name in ("rig", "pose"):
        p = get_named_point(frame.get(section_name), name)
        if p is not None:
            return p
    return None


def get_hand_point(frame: Dict[str, Any], side: str, name: str) -> Optional[List[float]]:
    return get_named_point(frame.get(f"{side}_hand"), name)


def load_motion_json(path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    frames = data.get("frames") or data.get("clean_frames")
    if not isinstance(frames, list) or not frames:
        raise RuntimeError("Motion JSON does not contain a non-empty frames list.")
    return data, frames


def vec_from_points_raw(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[Vector]:
    if a is None or b is None:
        return None
    v = Vector((b[0] - a[0], b[1] - a[1], b[2] - a[2]))
    if v.length < 1e-8:
        return None
    return v.normalized()


def blend_dirs(a: Optional[Vector], b: Optional[Vector], t: float) -> Optional[Vector]:
    if a is None:
        return b
    if b is None:
        return a
    t = max(0.0, min(1.0, t))
    v = a.normalized() * (1.0 - t) + b.normalized() * t
    if v.length < 1e-8:
        return a
    return v.normalized()


# ----------------------------------------------------------------------
# Scene / FBX helpers
# ----------------------------------------------------------------------

def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def import_fbx(path: str) -> List[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    after = set(bpy.data.objects)
    imported = list(after - before)
    if not imported:
        raise RuntimeError(f"No objects imported from FBX: {path}")
    return imported


def find_armature(imported: List[bpy.types.Object], requested_name: Optional[str] = None) -> bpy.types.Object:
    armatures = [obj for obj in imported if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature found in imported FBX.")
    if requested_name:
        for obj in armatures:
            if obj.name == requested_name:
                return obj
        raise RuntimeError(f"Requested armature not found: {requested_name}")
    armatures.sort(key=lambda obj: len(obj.data.bones), reverse=True)
    return armatures[0]


def export_fbx(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=False,
        bake_anim=True,
        add_leaf_bones=False,
        path_mode="AUTO",
        object_types={"ARMATURE", "MESH"},
    )


def list_bones(armature: bpy.types.Object) -> None:
    log(f"Armature object: {armature.name}")
    for bone in armature.data.bones:
        print(bone.name)


# ----------------------------------------------------------------------
# Bone detection
# ----------------------------------------------------------------------

BONE_ALIASES = {
    "hips": ["Hips", "mixamorig:Hips", "hips", "pelvis"],
    "spine": ["Spine", "mixamorig:Spine", "spine"],
    "chest": ["Spine2", "Chest", "UpperChest", "mixamorig:Spine2"],
    "neck": ["Neck", "mixamorig:Neck"],
    "head": ["Head", "mixamorig:Head"],

    "left_upper_arm": ["LeftArm", "mixamorig:LeftArm", "leftarm", "upperarm_l", "arm_l"],
    "left_forearm": ["LeftForeArm", "mixamorig:LeftForeArm", "leftforearm", "forearm_l", "lowerarm_l"],
    "left_hand": ["LeftHand", "mixamorig:LeftHand", "lefthand", "hand_l"],
    "right_upper_arm": ["RightArm", "mixamorig:RightArm", "rightarm", "upperarm_r", "arm_r"],
    "right_forearm": ["RightForeArm", "mixamorig:RightForeArm", "rightforearm", "forearm_r", "lowerarm_r"],
    "right_hand": ["RightHand", "mixamorig:RightHand", "righthand", "hand_r"],

    "left_thumb_1": ["LeftHandThumb1", "mixamorig:LeftHandThumb1", "lefthandthumb1", "thumb.01.L"],
    "left_thumb_2": ["LeftHandThumb2", "mixamorig:LeftHandThumb2", "lefthandthumb2", "thumb.02.L"],
    "left_thumb_3": ["LeftHandThumb3", "mixamorig:LeftHandThumb3", "lefthandthumb3", "thumb.03.L"],
    "left_index_1": ["LeftHandIndex1", "mixamorig:LeftHandIndex1", "lefthandindex1", "index1_l", "f_index.01.L"],
    "left_index_2": ["LeftHandIndex2", "mixamorig:LeftHandIndex2", "lefthandindex2", "index2_l", "f_index.02.L"],
    "left_index_3": ["LeftHandIndex3", "mixamorig:LeftHandIndex3", "lefthandindex3", "index3_l", "f_index.03.L"],
    "left_middle_1": ["LeftHandMiddle1", "mixamorig:LeftHandMiddle1", "lefthandmiddle1", "middle1_l", "f_middle.01.L"],
    "left_middle_2": ["LeftHandMiddle2", "mixamorig:LeftHandMiddle2", "lefthandmiddle2", "middle2_l", "f_middle.02.L"],
    "left_middle_3": ["LeftHandMiddle3", "mixamorig:LeftHandMiddle3", "lefthandmiddle3", "middle3_l", "f_middle.03.L"],
    "left_ring_1": ["LeftHandRing1", "mixamorig:LeftHandRing1", "lefthandring1", "ring1_l", "f_ring.01.L"],
    "left_ring_2": ["LeftHandRing2", "mixamorig:LeftHandRing2", "lefthandring2", "ring2_l", "f_ring.02.L"],
    "left_ring_3": ["LeftHandRing3", "mixamorig:LeftHandRing3", "lefthandring3", "ring3_l", "f_ring.03.L"],
    "left_pinky_1": ["LeftHandPinky1", "mixamorig:LeftHandPinky1", "lefthandpinky1", "pinky1_l", "f_pinky.01.L"],
    "left_pinky_2": ["LeftHandPinky2", "mixamorig:LeftHandPinky2", "lefthandpinky2", "pinky2_l", "f_pinky.02.L"],
    "left_pinky_3": ["LeftHandPinky3", "mixamorig:LeftHandPinky3", "lefthandpinky3", "pinky3_l", "f_pinky.03.L"],

    "right_thumb_1": ["RightHandThumb1", "mixamorig:RightHandThumb1", "righthandthumb1", "thumb.01.R"],
    "right_thumb_2": ["RightHandThumb2", "mixamorig:RightHandThumb2", "righthandthumb2", "thumb.02.R"],
    "right_thumb_3": ["RightHandThumb3", "mixamorig:RightHandThumb3", "righthandthumb3", "thumb.03.R"],
    "right_index_1": ["RightHandIndex1", "mixamorig:RightHandIndex1", "righthandindex1", "index1_r", "f_index.01.R"],
    "right_index_2": ["RightHandIndex2", "mixamorig:RightHandIndex2", "righthandindex2", "index2_r", "f_index.02.R"],
    "right_index_3": ["RightHandIndex3", "mixamorig:RightHandIndex3", "righthandindex3", "index3_r", "f_index.03.R"],
    "right_middle_1": ["RightHandMiddle1", "mixamorig:RightHandMiddle1", "righthandmiddle1", "middle1_r", "f_middle.01.R"],
    "right_middle_2": ["RightHandMiddle2", "mixamorig:RightHandMiddle2", "righthandmiddle2", "middle2_r", "f_middle.02.R"],
    "right_middle_3": ["RightHandMiddle3", "mixamorig:RightHandMiddle3", "righthandmiddle3", "middle3_r", "f_middle.03.R"],
    "right_ring_1": ["RightHandRing1", "mixamorig:RightHandRing1", "righthandring1", "ring1_r", "f_ring.01.R"],
    "right_ring_2": ["RightHandRing2", "mixamorig:RightHandRing2", "righthandring2", "ring2_r", "f_ring.02.R"],
    "right_ring_3": ["RightHandRing3", "mixamorig:RightHandRing3", "righthandring3", "ring3_r", "f_ring.03.R"],
    "right_pinky_1": ["RightHandPinky1", "mixamorig:RightHandPinky1", "righthandpinky1", "pinky1_r", "f_pinky.01.R"],
    "right_pinky_2": ["RightHandPinky2", "mixamorig:RightHandPinky2", "righthandpinky2", "pinky2_r", "f_pinky.02.R"],
    "right_pinky_3": ["RightHandPinky3", "mixamorig:RightHandPinky3", "righthandpinky3", "pinky3_r", "f_pinky.03.R"],
}


def find_bone(armature: bpy.types.Object, aliases: List[str]) -> Optional[str]:
    bones = list(armature.data.bones)
    exact = {normalize_name(b.name): b.name for b in bones}
    for alias in aliases:
        key = normalize_name(alias)
        if key in exact:
            return exact[key]
    for alias in aliases:
        key = normalize_name(alias)
        for bone in bones:
            if normalize_name(bone.name).endswith(key):
                return bone.name
    for alias in aliases:
        key = normalize_name(alias)
        for bone in bones:
            if key in normalize_name(bone.name):
                return bone.name
    return None


def build_bone_map(armature: bpy.types.Object) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for logical, aliases in BONE_ALIASES.items():
        found = find_bone(armature, aliases)
        if found:
            out[logical] = found
    return out


# ----------------------------------------------------------------------
# Coordinate conversion
# ----------------------------------------------------------------------

def source_to_blender(point: List[float], mirror_x: bool, source_scale: float, depth_scale: float) -> Vector:
    """
    Clean skeleton: X horizontal, Y up, Z depth.
    Blender: X horizontal, Z up, Y depth.

    v2 used this mapping and worked best for forearms.
    """
    x = -point[0] if mirror_x else point[0]
    y = point[1]
    z = point[2]
    return Vector((x * source_scale, -z * depth_scale * source_scale, y * source_scale))


def converted_direction(
    a: Optional[List[float]],
    b: Optional[List[float]],
    mirror_x: bool,
    source_scale: float,
    depth_scale: float,
) -> Optional[Vector]:
    if a is None or b is None:
        return None
    av = source_to_blender(a, mirror_x, source_scale, depth_scale)
    bv = source_to_blender(b, mirror_x, source_scale, depth_scale)
    d = bv - av
    if d.length < 1e-8:
        return None
    return d.normalized()


def source_distance(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[float]:
    if a is None or b is None:
        return None
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def source_scale_from_shoulders(frame: Dict[str, Any]) -> float:
    ls = get_body_point(frame, "left_shoulder")
    rs = get_body_point(frame, "right_shoulder")
    d = source_distance(ls, rs)
    if d is not None and d > 1e-6:
        return d
    return 1.0


# ----------------------------------------------------------------------
# Pose helpers
# ----------------------------------------------------------------------

def reset_pose(armature: bpy.types.Object) -> None:
    for pbone in armature.pose.bones:
        pbone.rotation_mode = "QUATERNION"
        pbone.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pbone.location = Vector((0.0, 0.0, 0.0))
        pbone.scale = Vector((1.0, 1.0, 1.0))


def pose_bone_direction(pbone: bpy.types.PoseBone) -> Optional[Vector]:
    d = pbone.tail - pbone.head
    if d.length < 1e-8:
        return None
    return d.normalized()


def rotate_pose_bone_toward(
    armature: bpy.types.Object,
    bone_name: Optional[str],
    target_dir: Optional[Vector],
    strength: float,
) -> bool:
    if not bone_name or bone_name not in armature.pose.bones:
        return False
    if target_dir is None or target_dir.length < 1e-8:
        return False

    pbone = armature.pose.bones[bone_name]
    current_dir = pose_bone_direction(pbone)
    if current_dir is None:
        return False

    try:
        delta = current_dir.rotation_difference(target_dir.normalized())
    except Exception:
        return False

    strength = max(0.0, min(1.0, strength))
    if strength < 1.0:
        delta = Quaternion().slerp(delta, strength)

    head = pbone.head.copy()
    around_head = Matrix.Translation(head) @ delta.to_matrix().to_4x4() @ Matrix.Translation(-head)
    pbone.matrix = around_head @ pbone.matrix
    bpy.context.view_layer.update()
    return True


def local_axis_vector(axis_name: str) -> Vector:
    mapping = {
        "x": Vector((1.0, 0.0, 0.0)),
        "y": Vector((0.0, 1.0, 0.0)),
        "z": Vector((0.0, 0.0, 1.0)),
        "neg_x": Vector((-1.0, 0.0, 0.0)),
        "neg_y": Vector((0.0, -1.0, 0.0)),
        "neg_z": Vector((0.0, 0.0, -1.0)),
    }
    return mapping.get(axis_name, Vector((0.0, 0.0, 1.0)))


def project_on_plane(v: Vector, normal: Vector) -> Optional[Vector]:
    if v.length < 1e-8 or normal.length < 1e-8:
        return None
    n = normal.normalized()
    p = v - n * v.dot(n)
    if p.length < 1e-8:
        return None
    return p.normalized()


def align_hand_with_palm(
    armature: bpy.types.Object,
    bone_name: Optional[str],
    finger_dir: Optional[Vector],
    palm_normal: Optional[Vector],
    direction_strength: float,
    twist_strength: float,
    palm_axis: str,
) -> bool:
    """
    First align the hand toward wrist->middle_mcp.
    Then add twist using the palm normal.

    palm_axis controls which local hand-bone axis is treated as the avatar palm normal.
    If twist looks wrong, try --palm_axis y or --palm_axis neg_y.
    """
    ok = rotate_pose_bone_toward(armature, bone_name, finger_dir, direction_strength)
    if not ok or palm_normal is None or palm_normal.length < 1e-8:
        return ok
    if not bone_name or bone_name not in armature.pose.bones:
        return ok

    pbone = armature.pose.bones[bone_name]
    forward = pose_bone_direction(pbone)
    if forward is None:
        return ok

    target_n = project_on_plane(palm_normal.normalized(), forward)
    if target_n is None:
        return ok

    axis_local = local_axis_vector(palm_axis)
    current_n = pbone.matrix.to_quaternion() @ axis_local
    current_n = project_on_plane(current_n, forward)
    if current_n is None:
        return ok

    try:
        delta = current_n.rotation_difference(target_n)
    except Exception:
        return ok

    twist_strength = max(0.0, min(1.0, twist_strength))
    if twist_strength < 1.0:
        delta = Quaternion().slerp(delta, twist_strength)

    head = pbone.head.copy()
    around_head = Matrix.Translation(head) @ delta.to_matrix().to_4x4() @ Matrix.Translation(-head)
    pbone.matrix = around_head @ pbone.matrix
    bpy.context.view_layer.update()
    return True


def keyframe_pose_bones(armature: bpy.types.Object, bone_names: List[str], frame: int) -> None:
    for bone_name in bone_names:
        if bone_name not in armature.pose.bones:
            continue
        pbone = armature.pose.bones[bone_name]
        pbone.rotation_mode = "QUATERNION"
        pbone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        pbone.keyframe_insert(data_path="location", frame=frame)
        pbone.keyframe_insert(data_path="scale", frame=frame)


# ----------------------------------------------------------------------
# Face-contact and palm geometry
# ----------------------------------------------------------------------

def face_point(frame: Dict[str, Any]) -> Optional[List[float]]:
    # Nose is best if available. If not, approximate from eyes/ears/neck.
    for name in ("nose", "mouth", "left_eye", "right_eye"):
        p = get_body_point(frame, name)
        if p is not None:
            return p
    neck = get_body_point(frame, "neck")
    if neck is not None:
        return neck
    ls = get_body_point(frame, "left_shoulder")
    rs = get_body_point(frame, "right_shoulder")
    if ls is not None and rs is not None:
        return [(ls[0] + rs[0]) * 0.5, (ls[1] + rs[1]) * 0.5 + source_scale_from_shoulders(frame) * 1.4, (ls[2] + rs[2]) * 0.5]
    return None


def face_contact_strength_for_side(frame: Dict[str, Any], side: str, radius: float) -> float:
    wrist = get_body_point(frame, f"{side}_wrist")
    if wrist is None:
        wrist = get_hand_point(frame, side, "wrist")
    face = face_point(frame)
    if wrist is None or face is None:
        return 0.0

    scale = max(source_scale_from_shoulders(frame), 1e-6)
    d = source_distance(wrist, face)
    if d is None:
        return 0.0

    nd = d / scale
    # 1 when very close, fades to 0 at radius.
    return max(0.0, min(1.0, 1.0 - nd / max(radius, 1e-6)))


def avatar_face_target(armature: bpy.types.Object, bone_map: Dict[str, str], side: str, args: argparse.Namespace) -> Optional[Vector]:
    head_name = bone_map.get("head")
    neck_name = bone_map.get("neck")

    if head_name and head_name in armature.pose.bones:
        head = armature.pose.bones[head_name]
        base = head.head.lerp(head.tail, 0.55)
    elif neck_name and neck_name in armature.pose.bones:
        neck = armature.pose.bones[neck_name]
        base = neck.tail.copy()
    else:
        return None

    # Side offset: left hand near left face side, right near right face side.
    side_sign = -1.0 if side == "left" else 1.0
    # Coordinates: Blender X horizontal, Z up, Y depth.
    return Vector((
        base.x + side_sign * args.face_side_offset,
        base.y + args.face_forward_offset,
        base.z + args.face_height_offset,
    ))


def direction_to_target_from_bone(armature: bpy.types.Object, bone_name: Optional[str], target: Optional[Vector]) -> Optional[Vector]:
    if not bone_name or bone_name not in armature.pose.bones or target is None:
        return None
    head = armature.pose.bones[bone_name].head.copy()
    d = target - head
    if d.length < 1e-8:
        return None
    return d.normalized()


def palm_normal_from_hand(frame: Dict[str, Any], side: str, mirror_x: bool, source_scale: float, depth_scale: float) -> Optional[Vector]:
    wrist = get_hand_point(frame, side, "wrist")
    index_mcp = get_hand_point(frame, side, "index_mcp")
    pinky_mcp = get_hand_point(frame, side, "pinky_mcp")
    if wrist is None or index_mcp is None or pinky_mcp is None:
        return None

    w = source_to_blender(wrist, mirror_x, source_scale, depth_scale)
    i = source_to_blender(index_mcp, mirror_x, source_scale, depth_scale)
    p = source_to_blender(pinky_mcp, mirror_x, source_scale, depth_scale)

    iv = i - w
    pv = p - w
    if iv.length < 1e-8 or pv.length < 1e-8:
        return None

    # Handedness-aware cross order. This matches the idea used in your overlay script.
    if side == "left":
        n = iv.cross(pv)
    else:
        n = pv.cross(iv)

    if n.length < 1e-8:
        return None
    return n.normalized()


# ----------------------------------------------------------------------
# Fingers
# ----------------------------------------------------------------------

FINGER_SEGMENTS = [
    ("thumb_1", "thumb_cmc", "thumb_mcp"),
    ("thumb_2", "thumb_mcp", "thumb_ip"),
    ("thumb_3", "thumb_ip", "thumb_tip"),
    ("index_1", "index_mcp", "index_pip"),
    ("index_2", "index_pip", "index_dip"),
    ("index_3", "index_dip", "index_tip"),
    ("middle_1", "middle_mcp", "middle_pip"),
    ("middle_2", "middle_pip", "middle_dip"),
    ("middle_3", "middle_dip", "middle_tip"),
    ("ring_1", "ring_mcp", "ring_pip"),
    ("ring_2", "ring_pip", "ring_dip"),
    ("ring_3", "ring_dip", "ring_tip"),
    ("pinky_1", "pinky_mcp", "pinky_pip"),
    ("pinky_2", "pinky_pip", "pinky_dip"),
    ("pinky_3", "pinky_dip", "pinky_tip"),
]


def finger_bone_names(bone_map: Dict[str, str]) -> List[str]:
    out = []
    for side in ("left", "right"):
        for suffix, _, _ in FINGER_SEGMENTS:
            key = f"{side}_{suffix}"
            if key in bone_map:
                out.append(bone_map[key])
    return out


def animate_fingers_for_frame(
    armature: bpy.types.Object,
    bone_map: Dict[str, str],
    frame: Dict[str, Any],
    mirror_x: bool,
    source_scale: float,
    depth_scale: float,
    strength: float,
) -> None:
    for side in ("left", "right"):
        for suffix, a_name, b_name in FINGER_SEGMENTS:
            bone_name = bone_map.get(f"{side}_{suffix}")
            if not bone_name:
                continue
            a = get_hand_point(frame, side, a_name)
            b = get_hand_point(frame, side, b_name)
            target_dir = converted_direction(a, b, mirror_x, source_scale, depth_scale)
            rotate_pose_bone_toward(armature, bone_name, target_dir, strength)


# ----------------------------------------------------------------------
# Frame targets
# ----------------------------------------------------------------------

def frame_targets(
    frame: Dict[str, Any],
    armature: bpy.types.Object,
    bone_map: Dict[str, str],
    mirror_x: bool,
    source_scale: float,
    depth_scale: float,
    args: argparse.Namespace,
) -> Dict[str, Optional[Vector]]:
    ls = get_body_point(frame, "left_shoulder")
    le = get_body_point(frame, "left_elbow")
    lw = get_body_point(frame, "left_wrist")
    rs = get_body_point(frame, "right_shoulder")
    re = get_body_point(frame, "right_elbow")
    rw = get_body_point(frame, "right_wrist")

    l_mid = get_hand_point(frame, "left", "middle_mcp")
    r_mid = get_hand_point(frame, "right", "middle_mcp")

    targets: Dict[str, Optional[Vector]] = {
        "left_upper_arm": converted_direction(ls, le, mirror_x, source_scale, depth_scale),
        "left_forearm": converted_direction(le, lw, mirror_x, source_scale, depth_scale),
        "left_hand": converted_direction(lw, l_mid, mirror_x, source_scale, depth_scale),
        "right_upper_arm": converted_direction(rs, re, mirror_x, source_scale, depth_scale),
        "right_forearm": converted_direction(re, rw, mirror_x, source_scale, depth_scale),
        "right_hand": converted_direction(rw, r_mid, mirror_x, source_scale, depth_scale),
        "left_palm_normal": palm_normal_from_hand(frame, "left", mirror_x, source_scale, depth_scale),
        "right_palm_normal": palm_normal_from_hand(frame, "right", mirror_x, source_scale, depth_scale),
    }

    for side in ("left", "right"):
        contact = face_contact_strength_for_side(frame, side, args.face_contact_radius)
        if contact <= 0.0:
            continue

        face_target = avatar_face_target(armature, bone_map, side, args)
        if face_target is None:
            continue

        contact *= args.face_contact_strength
        upper_name = bone_map.get(f"{side}_upper_arm")
        forearm_name = bone_map.get(f"{side}_forearm")
        hand_name = bone_map.get(f"{side}_hand")

        face_upper_dir = direction_to_target_from_bone(armature, upper_name, face_target)
        face_forearm_dir = direction_to_target_from_bone(armature, forearm_name, face_target)
        face_hand_dir = direction_to_target_from_bone(armature, hand_name, face_target)

        # IMPORTANT:
        # Do NOT rotate the hand bone toward the face here.
        # Tests showed that forcing hand/palm correction destroys finger pose.
        # We only help the UPPER ARM lift toward the face, while forearm/hand/fingers stay v3-style.
        targets[f"{side}_upper_arm"] = blend_dirs(targets.get(f"{side}_upper_arm"), face_upper_dir, contact)
        if args.face_contact_affects_forearm > 0.0:
            targets[f"{side}_forearm"] = blend_dirs(
                targets.get(f"{side}_forearm"),
                face_forearm_dir,
                contact * args.face_contact_affects_forearm,
            )

    return targets


# ----------------------------------------------------------------------
# Contact IK helpers
# ----------------------------------------------------------------------

def create_empty(name: str) -> bpy.types.Object:
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    obj.empty_display_size = 0.08
    obj.hide_render = True
    return obj


def set_empty_location(obj: bpy.types.Object, armature: bpy.types.Object, loc_armature_space: Vector, frame: int) -> None:
    obj.location = armature.matrix_world @ loc_armature_space
    obj.keyframe_insert(data_path="location", frame=frame)


def add_contact_ik(
    armature: bpy.types.Object,
    forearm_bone_name: Optional[str],
    target: bpy.types.Object,
    pole: bpy.types.Object,
    influence: float,
) -> None:
    if not forearm_bone_name or forearm_bone_name not in armature.pose.bones:
        return
    pbone = armature.pose.bones[forearm_bone_name]
    old = pbone.constraints.get("GESTURA_CONTACT_IK")
    if old:
        pbone.constraints.remove(old)
    con = pbone.constraints.new(type="IK")
    con.name = "GESTURA_CONTACT_IK"
    con.target = target
    con.pole_target = pole
    con.pole_angle = 0.0
    con.chain_count = 2
    con.use_rotation = True
    con.influence = influence


def keyframe_contact_ik(armature: bpy.types.Object, forearm_bone_name: Optional[str], frame: int, influence: float) -> None:
    if not forearm_bone_name or forearm_bone_name not in armature.pose.bones:
        return
    con = armature.pose.bones[forearm_bone_name].constraints.get("GESTURA_CONTACT_IK")
    if con is None:
        return
    con.influence = max(0.0, min(1.0, influence))
    con.keyframe_insert(data_path="influence", frame=frame)


# ----------------------------------------------------------------------
# Main animation
# ----------------------------------------------------------------------

def animate_avatar(
    armature: bpy.types.Object,
    frames: List[Dict[str, Any]],
    bone_map: Dict[str, str],
    args: argparse.Namespace,
) -> int:
    scene = bpy.context.scene
    scene.render.fps = args.fps
    scene.frame_start = args.frame_start
    scene.frame_end = args.frame_start + len(frames) - 1

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")

    solve_order = [
        "left_upper_arm", "left_forearm", "left_hand",
        "right_upper_arm", "right_forearm", "right_hand",
    ]
    main_bones = [bone_map[name] for name in solve_order if name in bone_map]
    finger_bones = finger_bone_names(bone_map)
    all_key_bones = main_bones + finger_bones

    log("Animating main bones:")
    for name in solve_order:
        log(f"  {name} -> {bone_map.get(name, 'MISSING')}")
    log(f"Detected finger bones: {len(finger_bones)}")
    log(f"Face contact radius: {args.face_contact_radius}")
    log(f"Face contact strength: {args.face_contact_strength}")
    log(f"Palm axis: {args.palm_axis}")

    last_valid_targets: Dict[str, Vector] = {}

    # Contact-only IK targets. These are inactive unless source wrist is near the face.
    bpy.ops.object.mode_set(mode="OBJECT")
    left_contact_target = create_empty("GESTURA_LEFT_FACE_TARGET")
    right_contact_target = create_empty("GESTURA_RIGHT_FACE_TARGET")
    left_pole = create_empty("GESTURA_LEFT_ELBOW_POLE")
    right_pole = create_empty("GESTURA_RIGHT_ELBOW_POLE")
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")

    add_contact_ik(armature, bone_map.get("left_forearm"), left_contact_target, left_pole, 0.0)
    add_contact_ik(armature, bone_map.get("right_forearm"), right_contact_target, right_pole, 0.0)

    for i, frame_data in enumerate(frames):
        frame_no = args.frame_start + i
        scene.frame_set(frame_no)

        # Important: same stability principle as v2.
        reset_pose(armature)
        bpy.context.view_layer.update()

        targets = frame_targets(
            frame=frame_data,
            armature=armature,
            bone_map=bone_map,
            mirror_x=args.mirror_x,
            source_scale=args.source_scale,
            depth_scale=args.depth_scale,
            args=args,
        )

        for key, target in list(targets.items()):
            if isinstance(target, Vector) and target.length > 1e-8:
                last_valid_targets[key] = target
            else:
                targets[key] = last_valid_targets.get(key)

        # Contact IK target placement. The target is near the avatar face, but IK only turns on
        # when the source wrist is close to the source face.
        left_contact = face_contact_strength_for_side(frame_data, "left", args.face_contact_radius) * args.contact_ik_strength
        right_contact = face_contact_strength_for_side(frame_data, "right", args.face_contact_radius) * args.contact_ik_strength

        left_face = avatar_face_target(armature, bone_map, "left", args)
        right_face = avatar_face_target(armature, bone_map, "right", args)

        if left_face is not None:
            set_empty_location(left_contact_target, armature, left_face, frame_no)
            upper = armature.pose.bones.get(bone_map.get("left_upper_arm", ""))
            if upper:
                pole_pos = upper.head + Vector((-args.pole_side, args.pole_forward, args.pole_down))
                set_empty_location(left_pole, armature, pole_pos, frame_no)
        if right_face is not None:
            set_empty_location(right_contact_target, armature, right_face, frame_no)
            upper = armature.pose.bones.get(bone_map.get("right_upper_arm", ""))
            if upper:
                pole_pos = upper.head + Vector((args.pole_side, args.pole_forward, args.pole_down))
                set_empty_location(right_pole, armature, pole_pos, frame_no)

        keyframe_contact_ik(armature, bone_map.get("left_forearm"), frame_no, left_contact)
        keyframe_contact_ik(armature, bone_map.get("right_forearm"), frame_no, right_contact)

        # Arms: v2-style direct direction rotation.
        # During contact, IK adds the final reach toward the face.
        rotate_pose_bone_toward(armature, bone_map.get("left_upper_arm"), targets.get("left_upper_arm"), args.rotation_strength)
        rotate_pose_bone_toward(armature, bone_map.get("left_forearm"), targets.get("left_forearm"), args.rotation_strength)
        if args.palm_twist_strength > 0.0:
            align_hand_with_palm(
                armature,
                bone_map.get("left_hand"),
                targets.get("left_hand"),
                targets.get("left_palm_normal"),
                args.hand_strength,
                args.palm_twist_strength,
                args.palm_axis,
            )
        else:
            rotate_pose_bone_toward(armature, bone_map.get("left_hand"), targets.get("left_hand"), args.hand_strength)

        rotate_pose_bone_toward(armature, bone_map.get("right_upper_arm"), targets.get("right_upper_arm"), args.rotation_strength)
        rotate_pose_bone_toward(armature, bone_map.get("right_forearm"), targets.get("right_forearm"), args.rotation_strength)
        if args.palm_twist_strength > 0.0:
            align_hand_with_palm(
                armature,
                bone_map.get("right_hand"),
                targets.get("right_hand"),
                targets.get("right_palm_normal"),
                args.hand_strength,
                args.palm_twist_strength,
                args.palm_axis,
            )
        else:
            rotate_pose_bone_toward(armature, bone_map.get("right_hand"), targets.get("right_hand"), args.hand_strength)

        if args.finger_strength > 0.0:
            animate_fingers_for_frame(
                armature=armature,
                bone_map=bone_map,
                frame=frame_data,
                mirror_x=args.mirror_x,
                source_scale=args.source_scale,
                depth_scale=args.depth_scale,
                strength=args.finger_strength,
            )

        keyframe_pose_bones(armature, all_key_bones, frame_no)

    # Bake the final visual result so IK becomes normal keyframes.
    bpy.context.view_layer.objects.active = armature
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    for pbone in armature.pose.bones:
        pbone.bone.select = pbone.name in all_key_bones

    bpy.ops.nla.bake(
        frame_start=scene.frame_start,
        frame_end=scene.frame_end,
        step=1,
        only_selected=True,
        visual_keying=True,
        clear_constraints=True,
        clear_parents=False,
        use_current_action=True,
        bake_types={"POSE"},
    )

    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in (left_contact_target, right_contact_target, left_pole, right_pole):
        if obj and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

    return scene.frame_end


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True, help="Input avatar FBX")
    parser.add_argument("--motion_json", help="Clean/avatar skeleton JSON")
    parser.add_argument("--output_fbx", help="Output animated FBX")
    parser.add_argument("--armature", default=None)
    parser.add_argument("--list_bones", action="store_true")

    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--frame_start", type=int, default=1)
    parser.add_argument("--mirror_x", action="store_true")
    parser.add_argument("--source_scale", type=float, default=1.0)

    # Your working v2 needed --depth_scale -1.
    parser.add_argument("--depth_scale", type=float, default=-1.0)

    # Arm/finger controls.
    parser.add_argument("--rotation_strength", type=float, default=1.0)
    parser.add_argument("--hand_strength", type=float, default=0.95)
    parser.add_argument("--finger_strength", type=float, default=0.85)

    # Face-contact controls.
    parser.add_argument("--face_contact_radius", type=float, default=1.05)
    parser.add_argument("--face_contact_strength", type=float, default=0.85)
    parser.add_argument("--face_contact_affects_forearm", type=float, default=0.0)
    parser.add_argument("--contact_ik_strength", type=float, default=0.85)
    parser.add_argument("--pole_forward", type=float, default=-0.35)
    parser.add_argument("--pole_side", type=float, default=0.25)
    parser.add_argument("--pole_down", type=float, default=-0.15)
    parser.add_argument("--face_side_offset", type=float, default=0.09)
    parser.add_argument("--face_forward_offset", type=float, default=-0.05)
    parser.add_argument("--face_height_offset", type=float, default=-0.04)

    # Palm orientation controls.
    # Default OFF because first test showed palm twist can destroy fingers.
    # Turn it on later only after face-contact is solved.
    parser.add_argument("--palm_twist_strength", type=float, default=0.0)
    parser.add_argument(
        "--palm_axis",
        default="z",
        choices=["x", "y", "z", "neg_x", "neg_y", "neg_z"],
        help="Which local avatar hand axis acts like the palm normal. Try y/neg_y if palm twist is wrong.",
    )

    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    clear_scene()
    imported = import_fbx(args.fbx)
    armature = find_armature(imported, args.armature)

    log(f"Imported FBX: {args.fbx}")
    log(f"Using armature: {armature.name}")

    if args.list_bones:
        list_bones(armature)
        return

    if not args.motion_json:
        raise RuntimeError("--motion_json is required unless using --list_bones")
    if not args.output_fbx:
        raise RuntimeError("--output_fbx is required unless using --list_bones")

    _, frames = load_motion_json(args.motion_json)
    log(f"Loaded motion frames: {len(frames)} from {args.motion_json}")

    bone_map = build_bone_map(armature)
    needed = [
        "left_upper_arm", "left_forearm", "left_hand",
        "right_upper_arm", "right_forearm", "right_hand",
    ]
    missing = [name for name in needed if name not in bone_map]
    if missing:
        log("WARNING: Missing important bones:")
        for name in missing:
            log(f"  {name}")

    frame_end = animate_avatar(
        armature=armature,
        frames=frames,
        bone_map=bone_map,
        args=args,
    )

    bpy.context.scene.frame_start = args.frame_start
    bpy.context.scene.frame_end = frame_end

    export_fbx(args.output_fbx)
    log(f"Exported animated FBX: {args.output_fbx}")


if __name__ == "__main__":
    main()
