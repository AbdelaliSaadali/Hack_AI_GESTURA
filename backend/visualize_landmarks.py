import cv2
import json

video_path = "data/raw_videos/69206.mp4"
json_path = "data/landmarks/69206.json"

with open(json_path, "r") as f:
    data = json.load(f)

frames_data = data["frames"]

cap = cv2.VideoCapture(video_path)

def draw_points(frame, landmarks, color):
    if not landmarks:
        return
    h, w, _ = frame.shape
    for lm in landmarks:
        x = int(lm[0] * w)
        y = int(lm[1] * h)
        cv2.circle(frame, (x, y), 3, color, -1)

frame_idx = 0

while True:
    ret, frame = cap.read()
    if not ret or frame_idx >= len(frames_data):
        break

    frame_data = frames_data[frame_idx]

    draw_points(frame, frame_data.get("pose", []), (0, 255, 0))
    draw_points(frame, frame_data.get("left_hand", []), (255, 0, 0))
    draw_points(frame, frame_data.get("right_hand", []), (0, 0, 255))

    cv2.putText(
        frame,
        f"Frame: {frame_idx}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )

    cv2.imshow("Landmarks", frame)

    if cv2.waitKey(30) & 0xFF == 27:
        break

    frame_idx += 1

cap.release()
cv2.destroyAllWindows()