"""
Final spatial analysis: figure out which points are HEAD, TORSO, ARMS, LEGS
by looking at actual coordinate positions, ignoring misleading names.

Y goes: 0.0 (bottom/feet) -> 1.3 (top... off-screen, but largest Y values)
The data is Y-up (inverted from screen coordinates).
"""

import requests

resp = requests.post("http://127.0.0.1:8000/translate", json={"text": "coffee"}, timeout=5)
frame = resp.json()["signs"][0]["frames"][0]

# All non-zero points with their coordinates
pts = []
for i in range(75):
    pt = frame[i]
    if pt[0] != 0.0 or pt[1] != 0.0:
        pts.append((i, pt[0], pt[1], pt[2]))

# Sort by Y descending (highest Y = top of person)
pts.sort(key=lambda x: -x[2])  # by Y, highest first

print("=== Points sorted by Y (highest = top of body) ===")
print(f"{'Idx':>4s}  {'X':>7s}  {'Y':>7s}  {'Z':>7s}  Likely")
for idx, x, y, z in pts:
    # Categorize by Y value
    if y > 1.0:
        cat = "HEAD (top)"
    elif y > 0.5:
        cat = "UPPER BODY"
    elif y > 0.25:
        cat = "MID BODY"  
    elif y > 0.15:
        cat = "LOWER/HANDS"
    else:
        cat = "FEET/BOTTOM"
    print(f"  {idx:2d}   {x:+.3f}   {y:+.3f}   {z:+.3f}   {cat}")

# Now let's look at LEFT vs RIGHT by X
print("\n=== Left side (small X) vs Right side (large X) ===")
pts_by_x = sorted(pts, key=lambda x: x[1])
for idx, x, y, z in pts_by_x:
    side = "LEFT" if x < 0.45 else ("CENTER" if x < 0.5 else "RIGHT")
    print(f"  {idx:2d}   x={x:+.3f}  y={y:+.3f}  {side}")

# KEY INSIGHT: Let's check a word that uses both hands
print("\n\n=== TESTING 'hello' for comparison ===")
resp2 = requests.post("http://127.0.0.1:8000/translate", json={"text": "hello"}, timeout=5)
data2 = resp2.json()
if data2["signs"] and data2["signs"][0]["found"]:
    f2 = data2["signs"][0]["frames"][0]
    nz2 = [(i, f2[i]) for i in range(len(f2)) if f2[i][0] != 0 or f2[i][1] != 0]
    print(f"Non-zero count: {len(nz2)}")
    print(f"Non-zero indices: {[x[0] for x in nz2]}")
else:
    print("hello not found")

# And check another word
for word in ["thank", "you", "help", "water", "sorry"]:
    resp3 = requests.post("http://127.0.0.1:8000/translate", json={"text": word}, timeout=5)
    d = resp3.json()
    if d["signs"] and d["signs"][0]["found"]:
        f3 = d["signs"][0]["frames"][0]
        nz3 = [i for i in range(len(f3)) if f3[i][0] != 0 or f3[i][1] != 0]
        print(f"'{word}': {len(nz3)} non-zero, indices: {nz3}")
    else:
        print(f"'{word}': not found")
