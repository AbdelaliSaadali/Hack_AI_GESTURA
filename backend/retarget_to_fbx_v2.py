#!/usr/bin/env python3
"""
retarget_to_fbx_v2.py

Gestura Blender retargeting script: clean skeleton JSON -> Ready Player Me / Wolf3D FBX.

Important difference from old retarget_to_fbx.py:
- This version does NOT use Damped Track constraints.
- It directly rotates the avatar arm bones so they follow source joint directions.
- It starts with arms only: upper arms, forearms, and hands.
- Fingers are intentionally skipped for now. Get arms working first.

Run from backend folder:

"/Applications/Blender.app/Contents/MacOS/Blender" --background --python retarget_to_fbx_v2.py -- \
  --fbx avatar/source/Wolf3D_readyplayerme_male_01.fbx \
  --motion_json data/clean_skeletons/69206_avatar.json \
  --output_fbx data/clean_skeletons/69206_result_v2.fbx

If the arms are mirrored, add:
  --mirror_x

If the arms move too strongly or weirdly, try:
  --rotation_strength 0.6
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
    print(f"[retarget_to_fbx_v2] {msg}")


# ----------------------------------------------------------------------
# Basic helpers
# ----------------------------------------------------------------------

def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def point3(value: Any) -> Optional[List[float]]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    if not isinstance(value[0], (int, float)) or not isinstance(value[1], (int, float)):
        return None
    x = float(value[0])
    y = float(value[1])
    z = float(value[2]) if len(value) >= 3 and isinstance(value[2], (int, float)) else 0.0
    if not all(math.isfinite(v) for v in (x, y, z)):
        return None
    return [x, y, z]


def get_named_point(section: Any, name: str) -> Optional[List[float]]:
    if isinstance(section, dict):
        return point3(section.get(name))
    return None


def get_frame_point(frame: Dict[str, Any], name: str) -> Optional[List[float]]:
    """
    Your clean JSON usually has important body joints in frame['rig'].
    Some files also have frame['pose'].
    This function checks both.
    """
    for section_name in ("rig", "pose"):
        p = get_named_point(frame.get(section_name), name)
        if p is not None:
            return p
    return None


def get_hand_point(frame: Dict[str, Any], side: str, name: str) -> Optional[List[float]]:
    return get_named_point(frame.get(f"{side}_hand"), name)


def vec_from_points(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[Vector]:
    if a is None or b is None:
        return None
    v = Vector((b[0] - a[0], b[1] - a[1], b[2] - a[2]))
    if v.length < 1e-8:
        return None
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


def list_bones(armature: bpy.types.Object) -> None:
    log(f"Armature object: {armature.name}")
    for bone in armature.data.bones:
        print(bone.name)


def load_motion_json(path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    frames = data.get("frames") or data.get("clean_frames")
    if not isinstance(frames, list) or not frames:
        raise RuntimeError("Motion JSON does not contain a non-empty 'frames' list.")

    return data, frames


# ----------------------------------------------------------------------
# Bone detection
# ----------------------------------------------------------------------

BONE_ALIASES = {
    "left_upper_arm": ["LeftArm", "mixamorig:LeftArm", "leftarm", "upperarm_l", "arm_l"],
    "left_forearm": ["LeftForeArm", "mixamorig:LeftForeArm", "leftforearm", "forearm_l", "lowerarm_l"],
    "left_hand": ["LeftHand", "mixamorig:LeftHand", "lefthand", "hand_l"],

    "right_upper_arm": ["RightArm", "mixamorig:RightArm", "rightarm", "upperarm_r", "arm_r"],
    "right_forearm": ["RightForeArm", "mixamorig:RightForeArm", "rightforearm", "forearm_r", "lowerarm_r"],
    "right_hand": ["RightHand", "mixamorig:RightHand", "righthand", "hand_r"],

    "hips": ["Hips", "mixamorig:Hips", "hips", "pelvis"],
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
    result: Dict[str, str] = {}
    for logical_name, aliases in BONE_ALIASES.items():
        found = find_bone(armature, aliases)
        if found:
            result[logical_name] = found
    return result


# ----------------------------------------------------------------------
# Coordinate conversion
# ----------------------------------------------------------------------

def source_to_blender(point: List[float], mirror_x: bool, source_scale: float, depth_scale: float) -> Vector:
    """
    Clean skeleton coordinates are body-centered and Y-up in your visualizer.
    Blender is Z-up.

    Mapping used here:
      source x -> Blender X
      source y -> Blender Z
      source z -> Blender Y, inverted/depth-scaled

    If left/right looks swapped, use --mirror_x.
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
    """
    Current bone direction in armature space.
    """
    head = pbone.head
    tail = pbone.tail
    d = tail - head
    if d.length < 1e-8:
        return None
    return d.normalized()


def rotate_pose_bone_toward(
    armature: bpy.types.Object,
    bone_name: str,
    target_dir: Vector,
    strength: float,
) -> bool:
    """
    Rotates one pose bone so its current direction points closer to target_dir.

    This is intentionally simple:
    - no constraints
    - no helper objects
    - no finger solving yet
    """
    if bone_name not in armature.pose.bones:
        return False

    pbone = armature.pose.bones[bone_name]
    current_dir = pose_bone_direction(pbone)
    if current_dir is None or target_dir.length < 1e-8:
        return False

    target_dir = target_dir.normalized()

    try:
        delta = current_dir.rotation_difference(target_dir)
    except Exception:
        return False

    if strength < 1.0:
        delta = Quaternion().slerp(delta, max(0.0, min(1.0, strength)))

    head = pbone.head.copy()
    rot_mat = delta.to_matrix().to_4x4()
    around_head = Matrix.Translation(head) @ rot_mat @ Matrix.Translation(-head)

    # pbone.matrix is in armature/object space.
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
# Animation
# ----------------------------------------------------------------------

def frame_targets(
    frame_data: Dict[str, Any],
    mirror_x: bool,
    source_scale: float,
    depth_scale: float,
) -> Dict[str, Optional[Vector]]:
    left_shoulder = get_frame_point(frame_data, "left_shoulder")
    left_elbow = get_frame_point(frame_data, "left_elbow")
    left_wrist = get_frame_point(frame_data, "left_wrist")

    right_shoulder = get_frame_point(frame_data, "right_shoulder")
    right_elbow = get_frame_point(frame_data, "right_elbow")
    right_wrist = get_frame_point(frame_data, "right_wrist")

    left_middle_mcp = get_hand_point(frame_data, "left", "middle_mcp")
    right_middle_mcp = get_hand_point(frame_data, "right", "middle_mcp")

    return {
        "left_upper_arm": converted_direction(left_shoulder, left_elbow, mirror_x, source_scale, depth_scale),
        "left_forearm": converted_direction(left_elbow, left_wrist, mirror_x, source_scale, depth_scale),
        "left_hand": converted_direction(left_wrist, left_middle_mcp, mirror_x, source_scale, depth_scale),

        "right_upper_arm": converted_direction(right_shoulder, right_elbow, mirror_x, source_scale, depth_scale),
        "right_forearm": converted_direction(right_elbow, right_wrist, mirror_x, source_scale, depth_scale),
        "right_hand": converted_direction(right_wrist, right_middle_mcp, mirror_x, source_scale, depth_scale),
    }


def animate_arms(
    armature: bpy.types.Object,
    frames: List[Dict[str, Any]],
    bone_map: Dict[str, str],
    frame_start: int,
    fps: int,
    mirror_x: bool,
    source_scale: float,
    depth_scale: float,
    rotation_strength: float,
) -> int:
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.frame_start = frame_start
    scene.frame_end = frame_start + len(frames) - 1

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")

    # Order matters: upper arm first, then forearm, then hand.
    solve_order = [
        "left_upper_arm",
        "left_forearm",
        "left_hand",
        "right_upper_arm",
        "right_forearm",
        "right_hand",
    ]

    real_bones = [bone_map[name] for name in solve_order if name in bone_map]
    log("Animating bones:")
    for name in solve_order:
        if name in bone_map:
            log(f"  {name} -> {bone_map[name]}")
        else:
            log(f"  {name} -> MISSING")

    last_valid_targets: Dict[str, Vector] = {}

    for i, frame_data in enumerate(frames):
        current_frame = frame_start + i
        scene.frame_set(current_frame)

        reset_pose(armature)
        bpy.context.view_layer.update()

        targets = frame_targets(
            frame_data=frame_data,
            mirror_x=mirror_x,
            source_scale=source_scale,
            depth_scale=depth_scale,
        )

        # Reuse the previous good direction if one frame is missing a hand/arm point.
        for logical_name, target in list(targets.items()):
            if target is not None:
                last_valid_targets[logical_name] = target
            else:
                targets[logical_name] = last_valid_targets.get(logical_name)

        for logical_name in solve_order:
            bone_name = bone_map.get(logical_name)
            target_dir = targets.get(logical_name)
            if bone_name is None or target_dir is None:
                continue
            rotate_pose_bone_toward(
                armature=armature,
                bone_name=bone_name,
                target_dir=target_dir,
                strength=rotation_strength,
            )

        keyframe_pose_bones(armature, real_bones, current_frame)

    bpy.ops.object.mode_set(mode="OBJECT")
    return scene.frame_end


# ----------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------

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
    parser.add_argument("--motion_json", help="Clean Gestura motion JSON")
    parser.add_argument("--output_fbx", help="Output animated FBX")
    parser.add_argument("--armature", default=None, help="Optional armature object name")
    parser.add_argument("--list_bones", action="store_true", help="List FBX bones and exit")

    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--frame_start", type=int, default=1)
    parser.add_argument("--mirror_x", action="store_true", help="Mirror left/right motion")
    parser.add_argument("--source_scale", type=float, default=1.0)
    parser.add_argument("--depth_scale", type=float, default=1.0)
    parser.add_argument("--rotation_strength", type=float, default=1.0)

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
        log("WARNING: Some expected arm bones were not detected:")
        for name in missing:
            log(f"  missing: {name}")
        log("Run with --list_bones if you need to check exact bone names.")

    frame_end = animate_arms(
        armature=armature,
        frames=frames,
        bone_map=bone_map,
        frame_start=args.frame_start,
        fps=args.fps,
        mirror_x=args.mirror_x,
        source_scale=args.source_scale,
        depth_scale=args.depth_scale,
        rotation_strength=args.rotation_strength,
    )

    bpy.context.scene.frame_start = args.frame_start
    bpy.context.scene.frame_end = frame_end

    export_fbx(args.output_fbx)
    log(f"Exported animated FBX: {args.output_fbx}")


if __name__ == "__main__":
    main()
