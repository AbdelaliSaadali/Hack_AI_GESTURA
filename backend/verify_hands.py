import json, pathlib

db = json.loads(pathlib.Path("asl_landmarks.json").read_text())
f = db["COFFEE"][0]

hand_names = {
    0: "WRIST", 1: "THUMB_CMC", 2: "THUMB_MCP", 3: "THUMB_IP", 4: "THUMB_TIP",
    5: "INDEX_MCP", 6: "INDEX_PIP", 7: "INDEX_DIP", 8: "INDEX_TIP",
    9: "MIDDLE_MCP", 10: "MIDDLE_PIP", 11: "MIDDLE_DIP", 12: "MIDDLE_TIP",
    13: "RING_MCP", 14: "RING_PIP", 15: "RING_DIP", 16: "RING_TIP",
    17: "PINKY_MCP", 18: "PINKY_PIP", 19: "PINKY_DIP", 20: "PINKY_TIP",
}

print("=== If 48-68 = left hand (21 landmarks) ===")
for h_idx in range(21):
    real_idx = 48 + h_idx
    pt = f[real_idx]
    name = hand_names[h_idx]
    print(f"  [{real_idx}] hand[{h_idx:2d}] {name:15s} ({pt[0]:+.3f}, {pt[1]:+.3f})")

print()
print("=== If 69-74 = right hand (first 6 of 21, truncated by [:75]) ===")
for h_idx in range(6):
    real_idx = 69 + h_idx
    pt = f[real_idx]
    name = hand_names[h_idx]
    print(f"  [{real_idx}] hand[{h_idx:2d}] {name:15s} ({pt[0]:+.3f}, {pt[1]:+.3f})")

print()
print("=== Body 42-47 sorted by Y descending ===")
for i in range(42, 48):
    print(f"  [{i}] x={f[i][0]:.3f} y={f[i][1]:.3f}")
