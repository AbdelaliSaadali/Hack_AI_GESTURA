import cv2
import mediapipe as mp
import json
import argparse
from pathlib import Path
import math

mp_pose = mp.solutions.pose
mp_hands = mp.solutions.hands

LEFT_WRIST_IDX = 15
RIGHT_WRIST_IDX = 16


def create_pose():
    return mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def create_hands():
    return mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def landmark_to_list(lm):
    return [float(lm.x), float(lm.y), float(lm.z)]


def empty_frame_data():
    return {
        "pose": [],
        "left_hand": [],
        "right_hand": []
    }


def dist2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def assign_hand_side_by_pose(hand_points, pose_points):
    if not pose_points or len(pose_points) <= RIGHT_WRIST_IDX:
        return None

    if not hand_points or len(hand_points) == 0:
        return None

    hand_wrist = hand_points[0]
    left_wrist = pose_points[LEFT_WRIST_IDX]
    right_wrist = pose_points[RIGHT_WRIST_IDX]

    dl = dist2(hand_wrist, left_wrist)
    dr = dist2(hand_wrist, right_wrist)

    return "left" if dl < dr else "right"


def extract_video(video_path: str):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    frames = []
    frame_count = 0

    with create_pose() as pose, create_hands() as hands:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False

            pose_res = pose.process(rgb)
            hands_res = hands.process(rgb)

            frame_data = empty_frame_data()

            pose_points = []
            if pose_res.pose_landmarks:
                pose_points = [landmark_to_list(lm) for lm in pose_res.pose_landmarks.landmark]
                frame_data["pose"] = pose_points

            if hands_res.multi_hand_landmarks:
                assigned = {"left": None, "right": None}

                for hand_lm in hands_res.multi_hand_landmarks:
                    points = [landmark_to_list(lm) for lm in hand_lm.landmark]

                    side = assign_hand_side_by_pose(points, pose_points)

                    if side is None:
                        continue

                    if assigned[side] is None:
                        assigned[side] = points
                    else:
                        # If two candidates fight for same side, keep closer one
                        hand_wrist = points[0]
                        side_wrist = pose_points[LEFT_WRIST_IDX] if side == "left" else pose_points[RIGHT_WRIST_IDX]

                        old_wrist = assigned[side][0]
                        if dist2(hand_wrist, side_wrist) < dist2(old_wrist, side_wrist):
                            assigned[side] = points

                if assigned["left"] is not None:
                    frame_data["left_hand"] = assigned["left"]
                if assigned["right"] is not None:
                    frame_data["right_hand"] = assigned["right"]

            frames.append(frame_data)

    cap.release()

    return {
        "video_path": video_path,
        "frame_count": frame_count,
        "frames": frames,
    }

def save_json(data, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data = extract_video(args.video)

    save_json(data, args.output)

    print(f"[OK] Saved: {args.output}")

if __name__ == "__main__":
    main()