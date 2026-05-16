#!/usr/bin/env python3
"""
postprocess_avatar_fbx.py

Use this AFTER retargeting.
It imports an animated FBX, trims the animation frame range, hides/removes lower-body geometry,
and exports a smaller upper-body FBX.

Run from backend:

"/Applications/Blender.app/Contents/MacOS/Blender" --background --python postprocess_avatar_fbx.py -- \
  --input_fbx data/animated_fbx/69213_v3.fbx \
  --output_fbx data/animated_fbx/69213_upper_trimmed.fbx \
  --start_frame 8 \
  --end_frame 78 \
  --cut_below_z 1.05

Notes:
- start_frame/end_frame remove resting animation frames from the exported FBX.
- cut_below_z removes vertices below a Blender Z height.
- If too much body disappears, lower cut_below_z.
- If legs remain, increase cut_below_z.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import bmesh


def log(msg: str) -> None:
    print(f"[postprocess_avatar_fbx] {msg}")


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser()
    parser.add_argument("--input_fbx", required=True)
    parser.add_argument("--output_fbx", required=True)
    parser.add_argument("--start_frame", type=int, required=True)
    parser.add_argument("--end_frame", type=int, required=True)
    parser.add_argument("--cut_below_z", type=float, default=1.05)
    parser.add_argument("--keep_original_timeline", action="store_true")
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_fbx(path: str) -> None:
    bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)


def trim_scene_timeline(start_frame: int, end_frame: int) -> None:
    scene = bpy.context.scene
    scene.frame_start = start_frame
    scene.frame_end = end_frame

    # Also trim action keyframes outside the range.
    # Important: remove keyframes by index from the end to avoid Blender's
    # "Keyframe not in F-Curve" error while mutating the list.
    for action in bpy.data.actions:
        for fc in action.fcurves:
            points = fc.keyframe_points
            remove_indices = [
                i for i, kp in enumerate(points)
                if kp.co.x < start_frame or kp.co.x > end_frame
            ]
            for i in reversed(remove_indices):
                points.remove(points[i], fast=True)
            points.update()


def shift_animation_to_frame_1(start_frame: int) -> None:
    offset = 1 - start_frame
    if offset == 0:
        return

    for action in bpy.data.actions:
        for fc in action.fcurves:
            for kp in fc.keyframe_points:
                kp.co.x += offset
                kp.handle_left.x += offset
                kp.handle_right.x += offset
            fc.keyframe_points.update()

    scene = bpy.context.scene
    old_len = scene.frame_end - scene.frame_start
    scene.frame_start = 1
    scene.frame_end = 1 + old_len


def vertex_should_be_kept_by_group(obj: bpy.types.Object, vertex_index: int) -> bool:
    """
    Keep arms/hands even if they move below the cut height.
    Without this, the hand mesh gets deleted when the signer lowers the hand.
    """
    keep_words = (
        "arm", "forearm", "hand", "wrist",
        "thumb", "index", "middle", "ring", "pinky", "finger",
        "shoulder", "clavicle",
        "head", "neck", "spine", "chest",
    )
    v = obj.data.vertices[vertex_index]
    for g in v.groups:
        if g.group < 0 or g.group >= len(obj.vertex_groups):
            continue
        name = obj.vertex_groups[g.group].name.lower()
        if any(word in name for word in keep_words):
            return True
    return False


def cut_mesh_below_z(obj: bpy.types.Object, z_cut: float) -> None:
    if obj.type != "MESH":
        return

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    to_delete = []

    for v in bm.verts:
        world_pos = obj.matrix_world @ v.co
        if world_pos.z < z_cut:
            # Delete lower-body geometry, but keep hands/arms/head/torso groups.
            if not vertex_should_be_kept_by_group(obj, v.index):
                to_delete.append(v)

    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context="VERTS")
        bmesh.update_edit_mesh(obj.data)

    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)


def delete_empty_meshes() -> None:
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and len(obj.data.vertices) == 0:
            bpy.data.objects.remove(obj, do_unlink=True)


def export_fbx(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        bake_anim=True,
        add_leaf_bones=False,
        object_types={"ARMATURE", "MESH"},
        path_mode="AUTO",
    )


def main() -> None:
    args = parse_args()

    if args.end_frame <= args.start_frame:
        raise RuntimeError("--end_frame must be greater than --start_frame")

    clear_scene()
    import_fbx(args.input_fbx)
    log(f"Imported {args.input_fbx}")

    trim_scene_timeline(args.start_frame, args.end_frame)
    if not args.keep_original_timeline:
        shift_animation_to_frame_1(args.start_frame)

    for obj in list(bpy.data.objects):
        if obj.type == "MESH":
            cut_mesh_below_z(obj, args.cut_below_z)

    delete_empty_meshes()
    export_fbx(args.output_fbx)
    log(f"Exported {args.output_fbx}")


if __name__ == "__main__":
    main()
