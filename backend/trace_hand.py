import requests
import math

resp = requests.post("http://127.0.0.1:8000/translate", json={"text": "coffee"}, timeout=5)
frame = resp.json()["signs"][0]["frames"][0]

non_zero = {i: pt for i, pt in enumerate(frame) if pt[0] != 0 or pt[1] != 0}
hands = [i for i in non_zero if non_zero[i][1] < 0.4]
hands.sort()

def d(i, j):
    if i not in non_zero or j not in non_zero: return 999
    p1, p2 = non_zero[i], non_zero[j]
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

print("Sequential distances:")
for i in range(len(hands)-1):
    dist = d(hands[i], hands[i+1])
    mark = "<--- JUMP" if dist > 0.05 else ""
    print(f"{hands[i]} -> {hands[i+1]}: {dist:.4f} {mark}")

print("\nDistance from Wrist candidate (55):")
for h in hands:
    print(f"55 -> {h}: {d(55, h):.4f}")
