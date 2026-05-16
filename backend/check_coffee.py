import requests
import json

API_URL = "http://127.0.0.1:8000/translate"

resp = requests.post(API_URL, json={"text": "coffee"}, timeout=10)
data = resp.json()

frames = data['signs'][0]['frames']
print(f"Total frames: {len(frames)}")

f = frames[0]
print("Frame 0 All Non-Zero Points:")
for idx, pt in enumerate(f):
    if pt[0] != 0.0 or pt[1] != 0.0 or pt[2] != 0.0:
        print(f"Index {idx}: x={pt[0]:.3f}, y={pt[1]:.3f}, z={pt[2]:.3f}")
