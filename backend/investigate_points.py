import requests
import json
import math

resp = requests.post("http://127.0.0.1:8000/translate", json={"text": "coffee"}, timeout=5)
data = resp.json()

# Grab the first sign's first frame
frame = data["signs"][0]["frames"][0]

non_zero = {}
for i, pt in enumerate(frame):
    if pt[0] != 0.0 or pt[1] != 0.0:
        non_zero[i] = pt[:2]

print("Non-zero indices:", list(non_zero.keys()))

# Spatial grouping logic (very naive distance based)
def dist(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

print("\n--- Point Coordinates ---")
for idx, (x, y) in sorted(non_zero.items()):
    print(f"{idx:2d}: ({x:.3f}, {y:.3f})")

