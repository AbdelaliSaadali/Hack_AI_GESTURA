import json
import sys
from pathlib import Path
import subprocess
import tempfile

MAPPING_FILE = Path("data/video_id_to_word.json")
AVATAR_DIR = Path("data/animated_fbx/upper_body_trimmed")
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"

with open(MAPPING_FILE, "r", encoding="utf-8") as f:
    mapping = json.load(f)

word_to_video = {
    info["word"].lower(): video_id
    for video_id, info in mapping.items()
}

phrase = " ".join(sys.argv[1:]).lower().strip()

if not phrase:
    print('Usage: python3 test_phrase_avatar.py "now here you"')
    sys.exit(1)

for word in phrase.split():
    video_id = word_to_video.get(word)

    if not video_id:
        print(f"Missing word: {word}")
        continue

    fbx = AVATAR_DIR / f"{video_id}_upper_trimmed.fbx"

    if not fbx.exists():
        print(f"FBX missing for {word}: {fbx}")
        continue

    print(f"Playing {word} -> {fbx}")

    blender_code = f"""
import bpy

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.import_scene.fbx(filepath=r'{fbx.resolve()}')

scene = bpy.context.scene
scene.frame_start = 1

if bpy.data.actions:
    max_frame = 1
    for action in bpy.data.actions:
        for fc in action.fcurves:
            for kp in fc.keyframe_points:
                max_frame = max(max_frame, int(kp.co.x))
    scene.frame_end = max_frame

bpy.ops.screen.animation_play()
"""

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write(blender_code)
        tmp_path = tmp.name

    subprocess.run([BLENDER, "--python", tmp_path])