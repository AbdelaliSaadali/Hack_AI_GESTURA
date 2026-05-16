#!/usr/bin/env python3
"""
retarget_to_fbx_v3_bendonly_clean.py

Clean version after the broken patch attempts.

Goal:
- Keep v3/v2-style arm motion.
- Keep IK OFF by default because IK pushed forearms behind the body.
- Use bend-only finger animation so fingers do not twist/explode.
- Add a simple optional palm twist on the hand bone only.

Test command from backend folder:

"/Applications/Blender.app/Contents/MacOS/Blender" --background --python retarget_to_fbx_v3_bendonly_clean.py -- \
  --fbx avatar/source/Wolf3D_readyplayerme_male_01.fbx \
  --motion_json data/avatar_skeletons/69413_avatar.json \
  --output_fbx data/animated_fbx/69413_v3_bendonly_clean.fbx

If palm turns wrong way, try:
  --palm_twist_strength -0.7

If palm movement is too much, try:
  --palm_twist_strength 0.35

If you want no palm twist:
  --palm_twist_strength 0
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


def log(msg: str) -> None:
    print(f"[retarget_to_fbx_v3_bendonly_spreadfix] {msg}")


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
    if abs(x) + abs(y) + abs(z) < 1e-8:
        return None
    return [x, y, z]


def get_named_point(section: Any, name: str) -> Optional[List[float]]:
    if isinstance(section, dict):
        return point3(section.get(name))
    return None


def get_body_point(frame: Dict[str, Any], name: str) -> Optional[List[float]]:
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


def source_to_blender_raw(point: List[float], mirror_x: bool, depth_scale: float) -> Vector:
    x = -point[0] if mirror_x else point[0]
    y = point[1]
    z = point[2]
    return Vector((x, -z * depth_scale, y))


def source_to_blender_position(point: List[float], mirror_x: bool, depth_scale: float, position_depth_scale: float) -> Vector:
    x = -point[0] if mirror_x else point[0]
    y = point[1]
    z = point[2]
    return Vector((x, -z * depth_scale * position_depth_scale, y))


def get_avatar_shoulder_info(armature: bpy.types.Object, bone_map: Dict[str, str]) -> Tuple[Vector, float]:
    left_name = bone_map.get("left_upper_arm")
    right_name = bone_map.get("right_upper_arm")
    if not left_name or not right_name:
        return Vector((0.0, 0.0, 1.5)), 1.0
    left = armature.pose.bones[left_name].head.copy()
    right = armature.pose.bones[right_name].head.copy()
    center = (left + right) * 0.5
    width = max((left - right).length, 1e-6)
    return center, width


def first_valid_source_shoulders(frames: List[Dict[str, Any]], mirror_x: bool, depth_scale: float) -> Tuple[Vector, float]:
    for frame in frames:
        ls = get_body_point(frame, "left_shoulder")
        rs = get_body_point(frame, "right_shoulder")
        if ls is None or rs is None:
            continue
        lsv = source_to_blender_raw(ls, mirror_x, depth_scale)
        rsv = source_to_blender_raw(rs, mirror_x, depth_scale)
        width = (lsv - rsv).length
        if width > 1e-6:
            return (lsv + rsv) * 0.5, width
    return Vector((0.0, 0.0, 0.0)), 1.0


def make_calibrator(frames, armature, bone_map, mirror_x, depth_scale, position_scale):
    source_center, source_width = first_valid_source_shoulders(frames, mirror_x, depth_scale)
    avatar_center, avatar_width = get_avatar_shoulder_info(armature, bone_map)
    scale = (avatar_width / max(source_width, 1e-6)) * position_scale
    log(f"Source shoulder width: {source_width:.4f}")
    log(f"Avatar shoulder width: {avatar_width:.4f}")
    log(f"Position scale: {scale:.4f}")
    return source_center, avatar_center, scale


def calibrated_point(point, source_center, avatar_center, scale, mirror_x, depth_scale, position_depth_scale, wrist_y_offset=0.0):
    if point is None:
        return None
    raw = source_to_blender_position(point, mirror_x, depth_scale, position_depth_scale)
    out = avatar_center + (raw - source_center) * scale
    out.y += wrist_y_offset
    return out


def calibrated_direction(a, b, mirror_x, depth_scale):
    if a is None or b is None:
        return None
    av = source_to_blender_raw(a, mirror_x, depth_scale)
    bv = source_to_blender_raw(b, mirror_x, depth_scale)
    d = bv - av
    if d.length < 1e-8:
        return None
    return d.normalized()


def remove_gestura_constraints(armature: bpy.types.Object) -> None:
    for pbone in armature.pose.bones:
        for con in list(pbone.constraints):
            if con.name.startswith("GESTURA_"):
                pbone.constraints.remove(con)


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


def rotate_pose_bone_toward(armature: bpy.types.Object, bone_name: str, target_dir: Optional[Vector], strength: float) -> bool:
    if target_dir is None or target_dir.length < 1e-8:
        return False
    if not bone_name or bone_name not in armature.pose.bones:
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
    rot = delta.to_matrix().to_4x4()
    around_head = Matrix.Translation(head) @ rot @ Matrix.Translation(-head)
    pbone.matrix = around_head @ pbone.matrix
    bpy.context.view_layer.update()
    return True


def create_empty(name: str) -> bpy.types.Object:
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    obj.empty_display_size = 0.08
    obj.hide_render = True
    return obj


def animate_empty_location(obj: bpy.types.Object, frame: int, armature: bpy.types.Object, loc_armature_space: Vector) -> None:
    obj.location = armature.matrix_world @ loc_armature_space
    obj.keyframe_insert(data_path="location", frame=frame)


def add_ik_constraint(armature, bone_name, target, chain_count, influence):
    if not bone_name or bone_name not in armature.pose.bones:
        return
    pbone = armature.pose.bones[bone_name]
    con = pbone.constraints.new(type="IK")
    con.name = "GESTURA_IK_WRIST"
    con.target = target
    con.chain_count = chain_count
    con.use_rotation = True
    con.influence = influence


def keyframe_bones(armature: bpy.types.Object, bone_names: List[str], frame: int) -> None:
    for bone_name in bone_names:
        if bone_name not in armature.pose.bones:
            continue
        pbone = armature.pose.bones[bone_name]

        # Preserve each bone's current rotation mode.
        # Fingers use XYZ Euler; forcing QUATERNION here can wipe or weaken finger curls.
        if pbone.rotation_mode == "QUATERNION":
            pbone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        else:
            pbone.keyframe_insert(data_path="rotation_euler", frame=frame)

        pbone.keyframe_insert(data_path="location", frame=frame)
        pbone.keyframe_insert(data_path="scale", frame=frame)


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


def angle_between(a: Optional[Vector], b: Optional[Vector]) -> Optional[float]:
    if a is None or b is None:
        return None
    if a.length < 1e-8 or b.length < 1e-8:
        return None
    a = a.normalized()
    b = b.normalized()
    dot = max(-1.0, min(1.0, a.dot(b)))
    return math.acos(dot)


def hand_vec(frame, side, a_name, b_name):
    a = get_hand_point(frame, side, a_name)
    b = get_hand_point(frame, side, b_name)
    if a is None or b is None:
        return None
    return Vector((b[0] - a[0], b[1] - a[1], b[2] - a[2]))


def apply_simple_finger_curl(armature, bone_name, curl, strength=0.75, axis="X"):
    if not bone_name or bone_name not in armature.pose.bones:
        return
    pbone = armature.pose.bones[bone_name]
    pbone.rotation_mode = "XYZ"
    curl = max(0.0, min(curl, 1.6)) * strength
    if axis == "X":
        pbone.rotation_euler.x = curl
    elif axis == "Y":
        pbone.rotation_euler.y = curl
    else:
        pbone.rotation_euler.z = curl
        


def palm_normal_from_landmarks(frame, side):
    wrist = get_hand_point(frame, side, "wrist")
    index = get_hand_point(frame, side, "index_mcp")
    pinky = get_hand_point(frame, side, "pinky_mcp")
    if wrist is None or index is None or pinky is None:
        return None
    w = Vector((wrist[0], wrist[1], wrist[2]))
    i = Vector((index[0], index[1], index[2]))
    p = Vector((pinky[0], pinky[1], pinky[2]))
    a = i - w
    b = p - w
    if a.length < 1e-8 or b.length < 1e-8:
        return None
    if side == "left":
        n = a.cross(b)
    else:
        n = b.cross(a)
    if n.length < 1e-8:
        return None
    return n.normalized()


def apply_simple_palm_twist(armature, bone_name, palm_normal, side, strength=0.0, axis="Y"):
    if not bone_name or bone_name not in armature.pose.bones:
        return
    if palm_normal is None or abs(strength) < 1e-8:
        return

    pbone = armature.pose.bones[bone_name]
    pbone.rotation_mode = "XYZ"

    twist = 1.2 * strength

    # Left/right need opposite directions.
    if side == "left":
        twist = -twist

    axis = axis.upper()
    if axis == "X":
        pbone.rotation_euler.x += twist
    elif axis == "Y":
        pbone.rotation_euler.y += twist
    elif axis == "Z":
        pbone.rotation_euler.z -= twist


def finger_spread_from_landmarks(frame, side, finger_name):
    """Return signed spread of this finger relative to middle finger in image X/Y.

    This is intentionally simple and separate from curl:
    - curl still bends on local X
    - spread only offsets the base _1 bone on another Euler axis
    """
    base = get_hand_point(frame, side, f"{finger_name}_mcp")
    tip = get_hand_point(frame, side, f"{finger_name}_tip")
    mid_base = get_hand_point(frame, side, "middle_mcp")
    mid_tip = get_hand_point(frame, side, "middle_tip")
    if base is None or tip is None or mid_base is None or mid_tip is None:
        return 0.0

    v = Vector((tip[0] - base[0], tip[1] - base[1], 0.0))
    m = Vector((mid_tip[0] - mid_base[0], mid_tip[1] - mid_base[1], 0.0))
    if v.length < 1e-8 or m.length < 1e-8:
        return 0.0
    v.normalize()
    m.normalize()

    # 2D signed angle: positive when finger direction is clockwise/counterclockwise
    # relative to the middle finger in the source image plane.
    cross_z = m.x * v.y - m.y * v.x
    dot = max(-1.0, min(1.0, m.dot(v)))
    angle = math.atan2(cross_z, dot)

    # Mirror side so left/right open outward instead of both leaning the same way.
    if side == "right":
        angle = -angle
    return max(-0.9, min(0.9, angle))


def apply_finger_spread(armature, bone_name, spread, strength=0.35, axis="Y"):
    if not bone_name or bone_name not in armature.pose.bones:
        return
    if abs(spread) < 1e-8 or abs(strength) < 1e-8:
        return
    pbone = armature.pose.bones[bone_name]
    pbone.rotation_mode = "XYZ"
    value = spread * strength
    axis = axis.upper()
    if axis == "X":
        pbone.rotation_euler.x += value
    elif axis == "Z":
        pbone.rotation_euler.z += value
    else:
        pbone.rotation_euler.y += value


def apply_hand_roll_offset(armature, bone_name, side, degrees=0.0, axis="Z", opposite_sides=True):
    """Apply a simple constant hand roll correction on the hand bone only.

    This is intentionally not driven by palm_normal, because the old palm_normal.z
    logic was unstable for 69413 and rotated the hands toward the floor.
    Use this only to calibrate the avatar's neutral hand/knuckle orientation.
    """
    if not bone_name or bone_name not in armature.pose.bones:
        return
    if abs(degrees) < 1e-8:
        return

    pbone = armature.pose.bones[bone_name]
    pbone.rotation_mode = "XYZ"

    angle = math.radians(degrees)
    if opposite_sides and side == "left":
        angle = -angle

    axis = axis.upper()
    if axis == "X":
        pbone.rotation_euler.x += angle
    elif axis == "Y":
        pbone.rotation_euler.y += angle
    else:
        pbone.rotation_euler.z += angle


def animate_fingers_for_frame(armature, bone_map, frame_data=None, frame=None, mirror_x=False, source_scale=1.0, depth_scale=1.0, strength=0.75, palm_twist_strength=0.0, hand_roll_degrees=0.0, hand_roll_axis="Z", hand_roll_same_direction=False, finger_spread_strength=0.0, finger_spread_axis="Y"):
    frame = frame if frame is not None else frame_data
    if frame is None:
        return

    fingers = {
        "thumb": [("thumb_1", "thumb_cmc", "thumb_mcp", "thumb_ip"), ("thumb_2", "thumb_mcp", "thumb_ip", "thumb_tip")],
        "index": [("index_1", "index_mcp", "index_pip", "index_dip"), ("index_2", "index_pip", "index_dip", "index_tip")],
        "middle": [("middle_1", "middle_mcp", "middle_pip", "middle_dip"), ("middle_2", "middle_pip", "middle_dip", "middle_tip")],
        "ring": [("ring_1", "ring_mcp", "ring_pip", "ring_dip"), ("ring_2", "ring_pip", "ring_dip", "ring_tip")],
        "pinky": [("pinky_1", "pinky_mcp", "pinky_pip", "pinky_dip"), ("pinky_2", "pinky_pip", "pinky_dip", "pinky_tip")],
    }

    for side in ("left", "right"):
        for _, joints in fingers.items():
            for bone_suffix, a, b, c in joints:
                v1 = hand_vec(frame, side, b, a)
                v2 = hand_vec(frame, side, b, c)
                ang = angle_between(v1, v2)
                if ang is None:
                    continue
                curl = max(0.0, math.pi - ang)
                bone_name = bone_map.get(f"{side}_{bone_suffix}")
                apply_simple_finger_curl(armature, bone_name, curl, strength=strength, axis="X")

                # Spread only the base joint. This keeps the bend from curl
                # and prevents _2/_3 bones from twisting sideways.
                if bone_suffix.endswith("_1") and finger_spread_strength > 0.0 and not bone_suffix.startswith("thumb"):
                    finger_name = bone_suffix.rsplit("_", 1)[0]
                    spread = finger_spread_from_landmarks(frame, side, finger_name)
                    apply_finger_spread(
                        armature,
                        bone_name,
                        spread,
                        strength=finger_spread_strength,
                        axis=finger_spread_axis,
                    )

        # Old palm twist is disabled by default and no longer touches the forearm.
        # Use --hand_roll_degrees for neutral knuckle/palm calibration.
        if abs(palm_twist_strength) > 1e-8:
            palm_normal = palm_normal_from_landmarks(frame, side)
            apply_simple_palm_twist(
                armature,
                bone_map.get(f"{side}_hand"),
                palm_normal,
                side,
                strength=palm_twist_strength,
                axis=bpy.context.scene.get("gestura_palm_axis", "Y"),
            )

        apply_hand_roll_offset(
            armature,
            bone_map.get(f"{side}_hand"),
            side,
            degrees=hand_roll_degrees,
            axis=hand_roll_axis,
            opposite_sides=not hand_roll_same_direction,
        )


def blend_dirs(a: Optional[Vector], b: Optional[Vector], t: float) -> Optional[Vector]:
    if a is None:
        return b
    if b is None:
        return a
    t = max(0.0, min(1.0, t))
    v = (a.normalized() * (1.0 - t)) + (b.normalized() * t)
    if v.length < 1e-8:
        return a
    return v.normalized()


def source_targets_for_frame(frame, source_center, avatar_center, scale, mirror_x, depth_scale, position_depth_scale, wrist_y_offset, upper_arm_wrist_blend, wrist_height_boost):
    ls = get_body_point(frame, "left_shoulder")
    le = get_body_point(frame, "left_elbow")
    lw = get_body_point(frame, "left_wrist")
    rs = get_body_point(frame, "right_shoulder")
    re = get_body_point(frame, "right_elbow")
    rw = get_body_point(frame, "right_wrist")
    l_mid = get_hand_point(frame, "left", "middle_mcp")
    r_mid = get_hand_point(frame, "right", "middle_mcp")

    left_upper_dir = calibrated_direction(ls, le, mirror_x, depth_scale)
    right_upper_dir = calibrated_direction(rs, re, mirror_x, depth_scale)
    left_shoulder_to_wrist = calibrated_direction(ls, lw, mirror_x, depth_scale)
    right_shoulder_to_wrist = calibrated_direction(rs, rw, mirror_x, depth_scale)
    left_upper_dir = blend_dirs(left_upper_dir, left_shoulder_to_wrist, upper_arm_wrist_blend)
    right_upper_dir = blend_dirs(right_upper_dir, right_shoulder_to_wrist, upper_arm_wrist_blend)

    left_elbow_pos = calibrated_point(le, source_center, avatar_center, scale, mirror_x, depth_scale, position_depth_scale, wrist_y_offset)
    left_wrist_pos = calibrated_point(lw, source_center, avatar_center, scale, mirror_x, depth_scale, position_depth_scale, wrist_y_offset)
    right_elbow_pos = calibrated_point(re, source_center, avatar_center, scale, mirror_x, depth_scale, position_depth_scale, wrist_y_offset)
    right_wrist_pos = calibrated_point(rw, source_center, avatar_center, scale, mirror_x, depth_scale, position_depth_scale, wrist_y_offset)

    if left_elbow_pos is not None:
        left_elbow_pos.z += wrist_height_boost * 0.5
    if left_wrist_pos is not None:
        left_wrist_pos.z += wrist_height_boost
    if right_elbow_pos is not None:
        right_elbow_pos.z += wrist_height_boost * 0.5
    if right_wrist_pos is not None:
        right_wrist_pos.z += wrist_height_boost

    return {
        "left_elbow_pos": left_elbow_pos,
        "left_wrist_pos": left_wrist_pos,
        "right_elbow_pos": right_elbow_pos,
        "right_wrist_pos": right_wrist_pos,
        "left_upper_arm_dir": left_upper_dir,
        "left_forearm_dir": calibrated_direction(le, lw, mirror_x, depth_scale),
        "left_hand_dir": calibrated_direction(lw, l_mid, mirror_x, depth_scale),
        "right_upper_arm_dir": right_upper_dir,
        "right_forearm_dir": calibrated_direction(re, rw, mirror_x, depth_scale),
        "right_hand_dir": calibrated_direction(rw, r_mid, mirror_x, depth_scale),
    }


def animate_avatar(armature, frames, bone_map, args):
    scene = bpy.context.scene
    scene.render.fps = args.fps
    scene.frame_start = args.frame_start
    scene.frame_end = args.frame_start + len(frames) - 1

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    remove_gestura_constraints(armature)
    reset_pose(armature)
    bpy.ops.object.mode_set(mode="OBJECT")

    source_center, avatar_center, pos_scale = make_calibrator(frames, armature, bone_map, args.mirror_x, args.depth_scale, args.position_scale)

    left_wrist_target = create_empty("GESTURA_LEFT_WRIST_TARGET")
    right_wrist_target = create_empty("GESTURA_RIGHT_WRIST_TARGET")
    last_targets: Dict[str, Vector] = {}

    if args.ik_strength > 0.0:
        for i, frame_data in enumerate(frames):
            frame_no = args.frame_start + i
            scene.frame_set(frame_no)
            targets = source_targets_for_frame(frame_data, source_center, avatar_center, pos_scale, args.mirror_x, args.depth_scale, args.position_depth_scale, args.wrist_y_offset, args.upper_arm_wrist_blend, args.wrist_height_boost)
            for key in ("left_wrist_pos", "right_wrist_pos"):
                if targets[key] is not None:
                    last_targets[key] = targets[key]
            left_pos = targets["left_wrist_pos"] or last_targets.get("left_wrist_pos")
            right_pos = targets["right_wrist_pos"] or last_targets.get("right_wrist_pos")
            if left_pos is not None:
                animate_empty_location(left_wrist_target, frame_no, armature, left_pos)
            if right_pos is not None:
                animate_empty_location(right_wrist_target, frame_no, armature, right_pos)

        bpy.context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode="POSE")
        add_ik_constraint(armature, bone_map.get("left_forearm"), left_wrist_target, chain_count=2, influence=args.ik_strength)
        add_ik_constraint(armature, bone_map.get("right_forearm"), right_wrist_target, chain_count=2, influence=args.ik_strength)
    else:
        bpy.context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode="POSE")

    body_bones = [bone_map[name] for name in ("left_upper_arm", "left_forearm", "left_hand", "right_upper_arm", "right_forearm", "right_hand") if name in bone_map]
    finger_bones = finger_bone_names(bone_map)
    all_key_bones = body_bones + finger_bones

    log("Detected main bones:")
    for name in ("left_upper_arm", "left_forearm", "left_hand", "right_upper_arm", "right_forearm", "right_hand"):
        log(f"  {name}: {bone_map.get(name, 'MISSING')}")
    log(f"Detected finger bones: {len(finger_bones)}")

    last_dirs: Dict[str, Vector] = {}

    for i, frame_data in enumerate(frames):
        frame_no = args.frame_start + i
        scene.frame_set(frame_no)

        if args.ik_strength <= 0.0:
            reset_pose(armature)

        bpy.context.view_layer.update()

        targets = source_targets_for_frame(frame_data, source_center, avatar_center, pos_scale, args.mirror_x, args.depth_scale, args.position_depth_scale, args.wrist_y_offset, args.upper_arm_wrist_blend, args.wrist_height_boost)

        for key in ("left_upper_arm_dir", "left_forearm_dir", "left_hand_dir", "right_upper_arm_dir", "right_forearm_dir", "right_hand_dir"):
            if targets[key] is not None:
                last_dirs[key] = targets[key]
            else:
                targets[key] = last_dirs.get(key)

        if args.direction_strength > 0.0:
            rotate_pose_bone_toward(armature, bone_map.get("left_upper_arm", ""), targets["left_upper_arm_dir"], args.direction_strength)
            rotate_pose_bone_toward(armature, bone_map.get("left_forearm", ""), targets["left_forearm_dir"], args.direction_strength)
            rotate_pose_bone_toward(armature, bone_map.get("right_upper_arm", ""), targets["right_upper_arm_dir"], args.direction_strength)
            rotate_pose_bone_toward(armature, bone_map.get("right_forearm", ""), targets["right_forearm_dir"], args.direction_strength)

        rotate_pose_bone_toward(armature, bone_map.get("left_hand", ""), targets["left_hand_dir"], args.hand_strength)
        rotate_pose_bone_toward(armature, bone_map.get("right_hand", ""), targets["right_hand_dir"], args.hand_strength)

        if args.finger_strength > 0.0:
            animate_fingers_for_frame(
                armature=armature,
                bone_map=bone_map,
                frame_data=frame_data,
                mirror_x=args.mirror_x,
                depth_scale=args.depth_scale,
                strength=args.finger_strength,
                palm_twist_strength=args.palm_twist_strength,
                hand_roll_degrees=args.hand_roll_degrees,
                hand_roll_axis=args.hand_roll_axis,
                hand_roll_same_direction=args.hand_roll_same_direction,
                finger_spread_strength=args.finger_spread_strength,
                finger_spread_axis=args.finger_spread_axis,
            )

        keyframe_bones(armature, all_key_bones, frame_no)

    if args.ik_strength > 0.0:
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
    for obj in (left_wrist_target, right_wrist_target):
        if obj and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    return scene.frame_end


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True)
    parser.add_argument("--motion_json")
    parser.add_argument("--output_fbx")
    parser.add_argument("--armature", default=None)
    parser.add_argument("--list_bones", action="store_true")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--frame_start", type=int, default=1)
    parser.add_argument("--mirror_x", action="store_true")
    parser.add_argument("--depth_scale", type=float, default=-1.0)
    parser.add_argument("--position_scale", type=float, default=1.0)
    parser.add_argument("--position_depth_scale", type=float, default=0.0)
    parser.add_argument("--wrist_y_offset", type=float, default=0.0)
    parser.add_argument("--upper_arm_wrist_blend", type=float, default=0.45)
    parser.add_argument("--wrist_height_boost", type=float, default=0.0)
    parser.add_argument("--ik_strength", type=float, default=0.0)
    parser.add_argument("--direction_strength", type=float, default=1.0)
    parser.add_argument("--hand_strength", type=float, default=0.9)
    parser.add_argument("--finger_strength", type=float, default=0.85)
    parser.add_argument("--palm_twist_strength", type=float, default=0.0)
    parser.add_argument("--palm_axis", choices=["X", "Y", "Z"], default="Y")
    parser.add_argument("--hand_roll_degrees", type=float, default=0.0)
    parser.add_argument("--hand_roll_axis", choices=["X", "Y", "Z"], default="Z")
    parser.add_argument("--hand_roll_same_direction", action="store_true")
    parser.add_argument("--finger_spread_strength", type=float, default=0.0)
    parser.add_argument("--finger_spread_axis", choices=["X", "Y", "Z"], default="Y")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    bpy.context.scene["gestura_palm_axis"] = args.palm_axis
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
    frame_end = animate_avatar(armature, frames, bone_map, args)
    bpy.context.scene.frame_start = args.frame_start
    bpy.context.scene.frame_end = frame_end
    export_fbx(args.output_fbx)
    log(f"Exported animated FBX: {args.output_fbx}")


if __name__ == "__main__":
    main()
