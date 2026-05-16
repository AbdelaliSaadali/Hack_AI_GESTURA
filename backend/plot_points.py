import requests
import json

resp = requests.post("http://127.0.0.1:8000/translate", json={"text": "coffee"}, timeout=5)
data = resp.json()
frame = data["signs"][0]["frames"][0]

non_zero = {}
for i, pt in enumerate(frame):
    if pt[0] != 0.0 or pt[1] != 0.0:
        non_zero[i] = pt[:2]

min_x = min(p[0] for p in non_zero.values())
max_x = max(p[0] for p in non_zero.values())
min_y = min(p[1] for p in non_zero.values())
max_y = max(p[1] for p in non_zero.values())

W, H = 80, 40
grid = [[" " for _ in range(W)] for _ in range(H)]

for i, (x, y) in non_zero.items():
    gx = int((x - min_x) / (max_x - min_x + 0.001) * (W - 4))
    gy = int((y - min_y) / (max_y - min_y + 0.001) * (H - 2))
    # Write the index at gx, gy
    s = str(i)
    for c_idx, c in enumerate(s):
        if gx+c_idx < W:
            grid[gy][gx+c_idx] = c

for row in grid:
    print("".join(row))
    
