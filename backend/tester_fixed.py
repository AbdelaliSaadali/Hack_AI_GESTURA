import tkinter as tk
import requests
import threading
import queue
import os
import math

from hand_topology_reconstruction import reconstruct_hand_topology

API_URL = "http://127.0.0.1:8000/translate"
CANVAS_WIDTH = 600
CANVAS_HEIGHT = 600
FRAME_DELAY_MS = 80
HAND_RENDER_MODE = "point_cloud"
HAND_PC_DRAW_LOCAL_EDGES = False
HAND_PC_DRAW_HULL = True
HAND_PC_DRAW_CENTROID = True
HAND_PC_DRAW_BBOX = False
HAND_PC_PRINT_METRICS = True
DEBUG_HAND_SHAPE_NORMALIZATION = True
DEBUG_HAND_SCALE_X = 2.0
DEBUG_HAND_SCALE_Y = 0.8

CANONICAL_LEFT_HAND_CONNECTIONS = [
    (48, 49), (49, 50), (50, 51), (51, 52),
    (48, 53), (53, 54), (54, 55), (55, 56),
    (48, 57), (57, 58), (58, 59), (59, 60),
    (48, 61), (61, 62), (62, 63), (63, 64),
    (48, 65), (65, 66), (66, 67), (67, 68),
    (53, 57), (57, 61), (61, 65),
]


def get_hand_points(points, start_idx=48, end_idx=68):
    hand_points = []
    if not points:
        return hand_points
    upper = min(end_idx, len(points) - 1)
    for idx in range(start_idx, upper + 1):
        if idx >= len(points):
            break
        pt = points[idx]
        if pt[0] != 0.0 or pt[1] != 0.0:
            hand_points.append((idx, float(pt[0]), float(pt[1])))
    return hand_points


def transform_left_hand_points(points, wrist_idx=46, hand_start=48, hand_end=68, hand_anchor_idx=48):
    transformed = {}
    if len(points) <= max(wrist_idx, hand_anchor_idx):
        return transformed

    wrist = points[wrist_idx]
    anchor = points[hand_anchor_idx]
    if (wrist[0] == 0.0 and wrist[1] == 0.0) or (anchor[0] == 0.0 and anchor[1] == 0.0):
        return transformed

    dx = wrist[0] - anchor[0]
    dy = wrist[1] - anchor[1]

    upper = min(hand_end, len(points) - 1)
    for idx in range(hand_start, upper + 1):
        px, py = points[idx][0], points[idx][1]
        if px == 0.0 and py == 0.0:
            continue
        transformed[idx] = [px + dx, py + dy]

    # Debug-only experiment: anisotropic shape normalization around translated anchor.
    if DEBUG_HAND_SHAPE_NORMALIZATION and hand_anchor_idx in transformed:
        anchor_x, anchor_y = transformed[hand_anchor_idx][0], transformed[hand_anchor_idx][1]
        for idx, pt in transformed.items():
            local_dx = pt[0] - anchor_x
            local_dy = pt[1] - anchor_y
            local_dx *= DEBUG_HAND_SCALE_X
            local_dy *= DEBUG_HAND_SCALE_Y
            pt[0] = anchor_x + local_dx
            pt[1] = anchor_y + local_dy

    return transformed


def _distance_xy(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _convex_hull_xy(points_xy):
    unique = sorted(set((float(x), float(y)) for x, y in points_xy))
    if len(unique) <= 2:
        return unique

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]


def draw_hand_point_cloud(canvas, hand_points, to_screen, *, draw_edges=True, draw_hull=True, draw_centroid=True, draw_bbox=True, point_fill="green", edge_fill="#78ff9f", hull_fill="cyan", bbox_fill="#e6ff66", centroid_fill="#ff4fd8"):
    if not hand_points:
        return

    raw_xy = [(x, y) for _, x, y in hand_points]
    screen_points = {idx: to_screen(idx) for idx, _, _ in hand_points}

    if draw_edges and len(hand_points) >= 2:
        # Keep local edge overlay very conservative to avoid fake structure.
        neighbor_threshold = 0.015
        local_edges = []
        nearest = {}

        for idx_a, x_a, y_a in hand_points:
            best_neighbor = None
            best_distance = None
            for idx_b, x_b, y_b in hand_points:
                if idx_a == idx_b:
                    continue
                distance = _distance_xy((x_a, y_a), (x_b, y_b))
                if distance <= neighbor_threshold and (best_distance is None or distance < best_distance):
                    best_distance = distance
                    best_neighbor = idx_b
            if best_neighbor is not None:
                nearest[idx_a] = best_neighbor

        for idx_a, idx_b in nearest.items():
            if nearest.get(idx_b) == idx_a and idx_a < idx_b:
                local_edges.append((idx_a, idx_b))

        for idx_a, idx_b in local_edges:
            p1 = screen_points.get(idx_a)
            p2 = screen_points.get(idx_b)
            if p1 and p2:
                canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=edge_fill, width=1)

    hull_drawn = False
    if draw_hull and len(raw_xy) >= 3:
        hull = _convex_hull_xy(raw_xy)
        if len(hull) >= 3:
            hull_screen = []
            for hx, hy in hull:
                closest_idx = min(hand_points, key=lambda item: _distance_xy((item[1], item[2]), (hx, hy)))[0]
                pt = screen_points.get(closest_idx)
                if pt:
                    hull_screen.extend([pt[0], pt[1]])
            if len(hull_screen) >= 6:
                canvas.create_polygon(*hull_screen, outline=hull_fill, fill="", width=1)
                hull_drawn = True

    if draw_centroid:
        centroid_x = sum(x for x, _ in raw_xy) / len(raw_xy)
        centroid_y = sum(y for _, y in raw_xy) / len(raw_xy)
        centroid_idx = min(hand_points, key=lambda item: _distance_xy((item[1], item[2]), (centroid_x, centroid_y)))[0]
        centroid_pt = screen_points.get(centroid_idx)
        if centroid_pt:
            x, y = centroid_pt
            canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=centroid_fill, outline="white", width=1)

    if draw_bbox and raw_xy and not hull_drawn:
        min_x = min(x for x, _ in raw_xy)
        max_x = max(x for x, _ in raw_xy)
        min_y = min(y for _, y in raw_xy)
        max_y = max(y for _, y in raw_xy)
        corners = [
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
        ]
        screen_corners = []
        for cx, cy in corners:
            nearest_idx = min(hand_points, key=lambda item: _distance_xy((item[1], item[2]), (cx, cy)))[0]
            screen_pt = screen_points.get(nearest_idx)
            if screen_pt:
                screen_corners.append(screen_pt)
        if len(screen_corners) == 4:
            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = screen_corners
            canvas.create_line(x1, y1, x2, y2, fill=bbox_fill, width=1)
            canvas.create_line(x2, y2, x3, y3, fill=bbox_fill, width=1)
            canvas.create_line(x3, y3, x4, y4, fill=bbox_fill, width=1)
            canvas.create_line(x4, y4, x1, y1, fill=bbox_fill, width=1)

    for idx, _, _ in hand_points:
        pt = screen_points.get(idx)
        if pt:
            x, y = pt
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=point_fill, outline=point_fill)

class GesturaTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestura PC Tester")
        self.root.geometry(f"{CANVAS_WIDTH + 40}x{CANVAS_HEIGHT + 140}")

        self.explorer_window = None
        self.explorer_edges = []
        self.explorer_pairs = []
        self.explorer_subgraphs = []
        self.explorer_active_edges = []
        self.explorer_idx = 0
        self.explorer_speed = 1500
        self.explorer_autoplay = False
        self.explorer_after_id = None

        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=10)

        tk.Label(input_frame, text="Enter word(s): ").pack(side=tk.LEFT)

        self.entry = tk.Entry(
            input_frame,
            width=20,
            bg="white",
            fg="black",
            insertbackground="black",
            disabledbackground="#e0e0e0",
            disabledforeground="black",
            highlightthickness=1,
            highlightcolor="blue",
            bd=2,
            selectbackground="lightblue",
            selectforeground="black",
        )
        self.entry.pack(side=tk.LEFT, padx=5, pady=5)
        self.entry.bind("<Return>", lambda e: self.on_translate())
        self.entry.focus_set()

        self.btn = tk.Button(input_frame, text="Translate", command=self.on_translate)
        self.btn.pack(side=tk.LEFT)

        self.debug_var = tk.BooleanVar(value=False)
        tk.Checkbutton(input_frame, text="Debug Indices", variable=self.debug_var).pack(side=tk.LEFT, padx=5)

        self.flip_y_var = tk.BooleanVar(value=False)
        tk.Checkbutton(input_frame, text="Flip Y", variable=self.flip_y_var).pack(side=tk.LEFT, padx=5)

        self.hand_chains_var = tk.BooleanVar(value=True)
        tk.Checkbutton(input_frame, text="Hand Chains", variable=self.hand_chains_var).pack(side=tk.LEFT, padx=5)

        self.chain_idx = 0
        self.test_chains = [
            [(48, 49), (49, 50), (50, 51)],
            [(52, 53), (53, 54), (54, 55)],
            [(56, 57), (57, 58), (58, 59)],
            [(60, 61), (61, 62), (62, 63)],
            [(64, 65), (65, 66), (66, 67)],
        ]
        self.cycle_btn = tk.Button(input_frame, text=f"Test Edge ({self.chain_idx + 1}/5)", command=self.cycle_test)
        self.cycle_btn.pack(side=tk.LEFT, padx=5)

        analytics_frame = tk.Frame(self.root)
        analytics_frame.pack(pady=5)

        self.btn_analyze = tk.Button(analytics_frame, text="Analyze Topology", command=self.analyze_topology)
        self.btn_analyze.pack(side=tk.LEFT, padx=3)

        tk.Label(analytics_frame, text="Top K:").pack(side=tk.LEFT)
        self.top_k_var = tk.StringVar(value="20")
        tk.Entry(analytics_frame, textvariable=self.top_k_var, width=3).pack(side=tk.LEFT)

        self.btn_explorer = tk.Button(analytics_frame, text="Explorer", command=self.open_explorer)
        self.btn_explorer.pack(side=tk.LEFT, padx=3)

        tk.Label(analytics_frame, text="Min D:").pack(side=tk.LEFT)
        self.min_dist_var = tk.StringVar(value="0.02")
        tk.Entry(analytics_frame, textvariable=self.min_dist_var, width=4).pack(side=tk.LEFT)

        tk.Label(analytics_frame, text="Max D:").pack(side=tk.LEFT)
        self.max_dist_var = tk.StringVar(value="0.16")
        tk.Entry(analytics_frame, textvariable=self.max_dist_var, width=4).pack(side=tk.LEFT)

        tk.Label(analytics_frame, text="Max Deg:").pack(side=tk.LEFT)
        self.max_degree_var = tk.StringVar(value="2")
        tk.Entry(analytics_frame, textvariable=self.max_degree_var, width=2).pack(side=tk.LEFT)

        self.show_inferred_var = tk.BooleanVar(value=False)
        tk.Checkbutton(analytics_frame, text="Show Filtered", variable=self.show_inferred_var).pack(side=tk.LEFT, padx=5)

        self.top_k_edges_result = []
        self.raw_frames_cache = []
        self.current_word = "unknown"
        
        self.status_var = tk.StringVar()
        self.status_var.set("Status: Ready")
        self.status_label = tk.Label(self.root, textvariable=self.status_var, fg="blue")
        self.status_label.pack()

        self.canvas = tk.Canvas(self.root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="darkblue")
        self.canvas.pack(pady=10)

        self.is_playing = False
        self.animation_queue = []
        self.current_frame_index = 0

        print("NEW RENDERER LOADED")

        self.result_queue = queue.Queue()
        self.root.after(100, self.poll_queue)

    def open_explorer(self):
        import glob
        import json

        files = glob.glob("topology_filtered_*.json")
        if not files:
            print("No filtered topology files found.")
            return

        latest_file = max(files, key=os.path.getctime)
        with open(latest_file, "r", encoding="utf-8") as f:
            candidates = json.load(f)

        if isinstance(candidates, dict):
            edge_source = candidates.get("edges", [])
            candidates = [{"edge": edge} for edge in edge_source]

        print(f"Loaded {len(candidates)} edges from {latest_file} for exploration.")

        self.explorer_edges = [tuple(c["edge"]) for c in candidates[:30]]
        self.explorer_pairs = [
            [self.explorer_edges[i], self.explorer_edges[i + 1]]
            for i in range(max(0, len(self.explorer_edges) - 1))
        ]
        self.explorer_subgraphs = [
            self.explorer_edges[i:i + 4]
            for i in range(0, max(1, len(self.explorer_edges) - 3), 2)
        ]

        self.explorer_active_edges = []
        self.explorer_idx = 0
        self.explorer_speed = 1500
        self.explorer_autoplay = False
        self.explorer_after_id = None

        if self.explorer_window is not None and self.explorer_window.winfo_exists():
            self.explorer_window.destroy()

        top = tk.Toplevel(self.root)
        top.title(f"Topology Explorer: {latest_file}")
        top.geometry("420x260")
        self.explorer_window = top

        def on_close():
            self.stop_explorer_autoplay()
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(top, text="Exploration Mode:").pack(pady=5)
        mode_frame = tk.Frame(top)
        mode_frame.pack()

        self.mode_var = tk.StringVar(value="C")
        tk.Radiobutton(mode_frame, text="A (Single Edge)", variable=self.mode_var, value="A", command=self.change_explorer_mode).pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="B (Pairs)", variable=self.mode_var, value="B", command=self.change_explorer_mode).pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="C (Subgraphs)", variable=self.mode_var, value="C", command=self.change_explorer_mode).pack(side=tk.LEFT)

        ctrl_frame = tk.Frame(top)
        ctrl_frame.pack(pady=10)

        tk.Button(ctrl_frame, text="< Prev", command=self.explorer_prev).pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_frame, text="Next >", command=self.explorer_next).pack(side=tk.LEFT, padx=5)

        self.play_btn = tk.Button(ctrl_frame, text="Autoplay", command=self.toggle_autoplay)
        self.play_btn.pack(side=tk.LEFT, padx=5)

        speed_frame = tk.Frame(top)
        speed_frame.pack(pady=5)
        tk.Label(speed_frame, text="Speed:").pack(side=tk.LEFT)

        self.speed_var = tk.IntVar(value=1500)
        for s in [1000, 1500, 2000]:
            tk.Radiobutton(speed_frame, text=f"{s}ms", variable=self.speed_var, value=s, command=self.update_speed).pack(side=tk.LEFT)

        self.lbl_edges = tk.Label(top, text="", fg="blue", wraplength=390, justify="left")
        self.lbl_edges.pack(pady=10)

        self.update_explorer()

        if not self.is_playing and self.raw_frames_cache:
            self.is_playing = True
            self.animation_queue = [{"type": "skeleton", "points": p} for p in self.raw_frames_cache]
            self.play_next_frame()

    def get_current_total(self):
        if not hasattr(self, "mode_var"):
            return 0
        mode = self.mode_var.get()
        if mode == "A":
            return len(self.explorer_edges)
        if mode == "B":
            return len(self.explorer_pairs)
        if mode == "C":
            return len(self.explorer_subgraphs)
        return 0

    def get_current_edges(self):
        total = self.get_current_total()
        if total <= 0:
            return []
        mode = self.mode_var.get()
        idx = self.explorer_idx % total
        if mode == "A":
            return [self.explorer_edges[idx]]
        if mode == "B":
            return self.explorer_pairs[idx]
        return self.explorer_subgraphs[idx]

    def update_explorer(self):
        if self.explorer_window is None or not self.explorer_window.winfo_exists():
            return
        total = self.get_current_total()
        if total <= 0:
            self.explorer_active_edges = []
            self.lbl_edges.config(text="No explorer candidates loaded.")
            return
        self.explorer_idx %= total
        self.explorer_active_edges = self.get_current_edges()
        label_text = (
            f"Mode={self.mode_var.get()} | explorer={self.explorer_idx + 1}/{total}\n"
            f"edges={self.explorer_active_edges}"
        )
        self.lbl_edges.config(text=label_text)
        print(label_text)

    def change_explorer_mode(self):
        self.explorer_idx = 0
        print("RESET explorer_idx from change_explorer_mode -> 0")
        self.update_explorer()

    def explorer_prev(self):
        total = self.get_current_total()
        if total > 0:
            self.explorer_idx = (self.explorer_idx - 1) % total
            print(f"Manual Prev -> explorer_idx={self.explorer_idx}")
            self.update_explorer()

    def explorer_next(self):
        total = self.get_current_total()
        if total > 0:
            self.explorer_idx = (self.explorer_idx + 1) % total
            print(f"Manual Next -> explorer_idx={self.explorer_idx}")
            self.update_explorer()

    def update_speed(self):
        self.explorer_speed = int(self.speed_var.get())
        print(f"Explorer speed set to {self.explorer_speed}ms")

    def stop_explorer_autoplay(self):
        self.explorer_autoplay = False
        if self.explorer_after_id is not None:
            try:
                self.root.after_cancel(self.explorer_after_id)
            except Exception:
                pass
            self.explorer_after_id = None
        if hasattr(self, "play_btn"):
            self.play_btn.config(relief=tk.RAISED)

    def toggle_autoplay(self):
        if self.explorer_autoplay:
            print("Autoplay OFF")
            self.stop_explorer_autoplay()
            return
        print("Autoplay ON")
        self.explorer_autoplay = True
        if hasattr(self, "play_btn"):
            self.play_btn.config(relief=tk.SUNKEN)
        self.schedule_explorer_tick()

    def schedule_explorer_tick(self):
        if not self.explorer_autoplay:
            return
        self.explorer_after_id = self.root.after(self.explorer_speed, self.run_autoplay)

    def run_autoplay(self):
        if not self.explorer_autoplay:
            return
        if self.explorer_window is None or not self.explorer_window.winfo_exists():
            print("Autoplay stopping: explorer window no longer exists")
            self.stop_explorer_autoplay()
            return
        total = self.get_current_total()
        print(f"AUTOPLAY tick: idx before={self.explorer_idx}, total={total}")
        if total > 0:
            self.explorer_idx = (self.explorer_idx + 1) % total
            print(f"AUTOPLAY tick: idx after={self.explorer_idx}")
            self.update_explorer()
        else:
            print("AUTOPLAY warning: no candidates available")
        self.schedule_explorer_tick()

    def cycle_test(self):
        self.chain_idx = (self.chain_idx + 1) % len(self.test_chains)
        self.cycle_btn.config(text=f"Test Edge ({self.chain_idx + 1}/5)")
        print(f"--- NOW TESTING EDGES: {self.test_chains[self.chain_idx]} ---")

    def analyze_topology(self):
        if not self.raw_frames_cache:
            print("No frames cached for analysis.")
            return
        print(f"--- RECONSTRUCTING TOPOLOGY ({len(self.raw_frames_cache)} frames) ---")
        result = reconstruct_hand_topology(
            self.raw_frames_cache,
            output_path=f"reconstructed_topology_{(self.current_word or 'unknown').strip().replace(' ', '_').upper()}.json",
        )
        print(f"Reconstructed root: {result.get('root')}")
        print(f"Reconstructed edges: {result.get('edges', [])}")
        print(f"Exported reconstructed topology to reconstructed_topology_{(self.current_word or 'unknown').strip().replace(' ', '_').upper()}.json")

    def poll_queue(self):
        try:
            msg = self.result_queue.get_nowait()
            if msg["type"] == "error":
                self.update_status(msg["text"], "red")
                self.btn.config(state=tk.NORMAL)
            elif msg["type"] == "data":
                self.handle_response(msg["data"])
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)

    def update_status(self, text, color="blue"):
        self.status_var.set(f"Status: {text}")
        self.status_label.config(fg=color)

    def on_translate(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.update_status("Translating...", "orange")
        self.btn.config(state=tk.DISABLED)
        self.canvas.delete("all")
        self.is_playing = False
        self._frame_count = 0
        threading.Thread(target=self.fetch_translation, args=(text,), daemon=True).start()

    def fetch_translation(self, text):
        try:
            resp = requests.post(API_URL, json={"text": text}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self.result_queue.put({"type": "data", "data": data})
        except Exception as e:
            self.result_queue.put({"type": "error", "text": f"Error: {e}"})

    def handle_response(self, data):
        self.btn.config(state=tk.NORMAL)
        if not data.get("success"):
            self.update_status("Backend returned success=False", "red")
            return
        signs = data.get("signs", [])
        if not signs:
            self.update_status("No signs returned in response", "red")
            return
        self.animation_queue = []
        self.raw_frames_cache = []
        for sign in signs:
            gloss = sign.get("gloss", "UNKNOWN")
            self.current_word = gloss
            sign_type = sign.get("type", "skeleton")
            if sign_type == "fingerspell" or not sign.get("found"):
                self.animation_queue.append({"type": "message", "text": f"[{gloss}] - Fingerspelling/Not Found"})
            else:
                frames = sign.get("frames", [])
                if not frames:
                    self.animation_queue.append({"type": "message", "text": f"[{gloss}] - Empty frames"})
                    continue
                for point_cloud in frames:
                    self.animation_queue.append({"type": "skeleton", "points": point_cloud})
                    self.raw_frames_cache.append(point_cloud)
        if self.animation_queue:
            self.update_status("Animating...", "green")
            self.is_playing = True
            self.play_next_frame()

    def play_next_frame(self):
        if not self.is_playing:
            return
        explorer_running = self.explorer_window is not None and self.explorer_window.winfo_exists()
        if not self.animation_queue:
            if explorer_running and self.raw_frames_cache:
                self.animation_queue = [{"type": "skeleton", "points": p} for p in self.raw_frames_cache]
            else:
                self.is_playing = False
                self.update_status("Finished.", "blue")
                return
        frame_data = self.animation_queue.pop(0)
        self.canvas.delete("all")
        if explorer_running:
            self.current_frame_index = len(self.raw_frames_cache) - len(self.animation_queue)
            total = self.get_current_total() if hasattr(self, "mode_var") else 0
            shown_idx = (self.explorer_idx + 1) if total > 0 else 0
            if self.current_frame_index % 5 == 0:
                print(f"Animating frame={self.current_frame_index}, explorer_idx={shown_idx}/{total}")
            self.update_status(f"frame={self.current_frame_index} | explorer={shown_idx}/{total}", "green")
        if frame_data["type"] == "message":
            self.canvas.create_text(CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2, text=frame_data["text"], fill="white", font=("Arial", 20, "bold"))
            self.root.after(1000, self.play_next_frame)
            return
        points = frame_data["points"]
        self.draw_skeleton(points)
        self.root.after(FRAME_DELAY_MS, self.play_next_frame)

    def transform_left_hand(self, points):
        """
        Complete transformation pipeline for left-hand landmarks (48-68):
        1. Scale hand to realistic size relative to body
        2. Rotate hand to align with arm direction
        3. Re-anchor to body wrist (46)
        
        Returns dict: {48: [x,y], 49: [x,y], ..., 68: [x,y]}
        """
        transformed = {}
        
        # Validate
        if len(points) < 69:
            return transformed
        
        # Helper function for distance
        def dist(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])
        
        # STEP 1: Compute body reference using shoulder → wrist
        shoulder = points[42]  # left shoulder
        wrist = points[46]     # left wrist
        
        if shoulder[0] == 0.0 or wrist[0] == 0.0:
            return transformed
        
        body_ref = dist(shoulder, wrist)
        if body_ref < 1e-6:
            return transformed
        
        # STEP 2: Compute hand reference using hand root → index MCP
        hand_base = points[48]    # hand wrist/root
        index_mcp = points[53]    # index middle-carpal
        
        if hand_base[0] == 0.0 or index_mcp[0] == 0.0:
            return transformed
        
        hand_ref = dist(hand_base, index_mcp)
        if hand_ref < 1e-6:
            return transformed
        
        # STEP 3: Compute scale factor
        HAND_SCALE_FACTOR = 0.3  # 30% of arm length
        target_size = body_ref * HAND_SCALE_FACTOR
        scale = target_size / hand_ref
        
        # Clamp scale to reasonable range
        scale = max(0.1, min(3.0, scale))
        
        # Apply smoothing to reduce jitter
        if not hasattr(self, 'smooth_left_hand_scale'):
            self.smooth_left_hand_scale = scale
        
        alpha_scale = 0.15
        self.smooth_left_hand_scale = alpha_scale * scale + (1 - alpha_scale) * self.smooth_left_hand_scale
        scale = self.smooth_left_hand_scale
        
        # STEP 4: Scale all hand points around hand base (48)
        scaled = {}
        base_x, base_y = hand_base[0], hand_base[1]
        
        for i in range(48, 69):
            if i < len(points) and (points[i][0] != 0.0 or points[i][1] != 0.0):
                px, py = points[i][0], points[i][1]
                dx = px - base_x
                dy = py - base_y
                
                dx *= scale
                dy *= scale
                
                scaled[i] = [base_x + dx, base_y + dy]
            else:
                scaled[i] = [0.0, 0.0]
        
        # STEP 5: Compute rotation to align hand with arm
        # Arm direction (elbow → wrist)
        elbow = points[44]
        arm_dx = wrist[0] - elbow[0]
        arm_dy = wrist[1] - elbow[1]
        angle_arm = math.atan2(arm_dy, arm_dx)
        
        # Hand direction (hand base → scaled index MCP)
        if 53 in scaled and scaled[53][0] != 0.0:
            hand_dx = scaled[53][0] - scaled[48][0]
            hand_dy = scaled[53][1] - scaled[48][1]
            angle_hand = math.atan2(hand_dy, hand_dx)
            rotation = angle_arm - angle_hand
        else:
            rotation = 0.0
        
        # Apply smoothing to rotation to reduce jitter
        if not hasattr(self, 'smooth_left_hand_rotation'):
            self.smooth_left_hand_rotation = rotation
        
        alpha_rot = 0.15
        self.smooth_left_hand_rotation = alpha_rot * rotation + (1 - alpha_rot) * self.smooth_left_hand_rotation
        rotation = self.smooth_left_hand_rotation
        
        # STEP 6: Rotate all hand points around hand base (48)
        rotated = {}
        cx, cy = scaled[48][0], scaled[48][1]
        cos_r = math.cos(rotation)
        sin_r = math.sin(rotation)
        
        for i in range(48, 69):
            if i in scaled:
                px, py = scaled[i][0], scaled[i][1]
                dx = px - cx
                dy = py - cy
                
                # Apply 2D rotation matrix
                rx = dx * cos_r - dy * sin_r
                ry = dx * sin_r + dy * cos_r
                
                rotated[i] = [cx + rx, cy + ry]
            else:
                rotated[i] = [0.0, 0.0]
        
        # STEP 7: Re-anchor to body wrist (46)
        if 48 in rotated and rotated[48][0] != 0.0:
            anchor_x = wrist[0] - rotated[48][0]
            anchor_y = wrist[1] - rotated[48][1]
            
            for i in range(48, 69):
                rotated[i][0] += anchor_x
                rotated[i][1] += anchor_y
        
        # Debug print every 10 frames
        if not hasattr(self, '_hand_debug_count'):
            self._hand_debug_count = 0
        
        self._hand_debug_count += 1
        if self._hand_debug_count % 10 == 0:
            rot_deg = math.degrees(rotation)
            print(
                "HAND DEBUG",
                "wrist=", points[46][:2],
                "base=", rotated[48][:2] if 48 in rotated else "N/A",
                "scale=", f"{scale:.3f}",
                "rotation_deg=", f"{rot_deg:.1f}"
            )
        
        return rotated

    def get_transformed_left_hand(self, points):
        """
        Transform left-hand landmarks (48-68) so they are:
        1. Scaled to realistic size relative to body
        2. Anchored to the body wrist (46)
        
        Returns dict: {48: [x,y], 49: [x,y], ..., 68: [x,y]}
        """
        transformed = {}
        
        # Validate
        if len(points) < 69:
            return transformed
        
        # Step 1: Compute body reference (elbow 44 -> wrist 46)
        elbow = points[44]
        wrist = points[46]
        
        if elbow[0] == 0.0 or wrist[0] == 0.0:
            return transformed
        
        body_ref = math.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1])
        if body_ref < 1e-6:
            return transformed
        
        # Step 2: Compute hand reference (base 48 -> index MCP 53)
        hand_base = points[48]
        index_mcp = points[53]
        
        if hand_base[0] == 0.0 or index_mcp[0] == 0.0:
            return transformed
        
        hand_ref = math.hypot(index_mcp[0] - hand_base[0], index_mcp[1] - hand_base[1])
        if hand_ref < 1e-6:
            return transformed
        
        # Step 3: Compute scale factor
        HAND_SCALE_FACTOR = 0.8
        target_size = body_ref * HAND_SCALE_FACTOR
        scale = target_size / hand_ref
        
        # Clamp to reasonable range
        scale = max(0.5, min(3.0, scale))
        
        # Apply smoothing to reduce jitter
        if not hasattr(self, 'smooth_left_hand_scale'):
            self.smooth_left_hand_scale = scale
        
        alpha = 0.15
        self.smooth_left_hand_scale = alpha * scale + (1 - alpha) * self.smooth_left_hand_scale
        scale = self.smooth_left_hand_scale
        
        # Step 4: Scale all hand points around base 48
        base_x, base_y = hand_base[0], hand_base[1]
        
        for i in range(48, 69):
            if i < len(points) and (points[i][0] != 0.0 or points[i][1] != 0.0):
                px, py = points[i][0], points[i][1]
                dx = px - base_x
                dy = py - base_y
                
                dx *= scale
                dy *= scale
                
                transformed[i] = [base_x + dx, base_y + dy]
            else:
                # Keep zero points as zero
                if i < len(points):
                    transformed[i] = [0.0, 0.0]
        
        # Step 5: Re-anchor to body wrist 46
        # After scaling, attach transformed hand base (48) to body wrist (46)
        if 48 in transformed and transformed[48][0] != 0.0:
            anchor_x = wrist[0] - transformed[48][0]
            anchor_y = wrist[1] - transformed[48][1]
            
            for i in range(48, 69):
                if i in transformed:
                    transformed[i][0] += anchor_x
                    transformed[i][1] += anchor_y
        
        # Debug print every 10 frames
        if not hasattr(self, '_hand_debug_count'):
            self._hand_debug_count = 0
        
        self._hand_debug_count += 1
        if self._hand_debug_count % 10 == 0:
            print("HAND DEBUG",
                  "body_wrist=", points[46][:2],
                  "raw_hand_base=", points[48][:2],
                  "transformed_hand_base=", transformed[48][:2] if 48 in transformed else "N/A",
                  "scale=", scale)
        
        return transformed

    def scale_hand_to_body_proportion(self, points, hand_start_idx, hand_end_idx, wrist_idx, elbow_idx, hand_scale_factor=0.8):
        """
        Scale hand landmarks to realistic size relative to body.
        
        Hand landmarks are already in global space and aligned to wrist,
        but are compressed at a small scale. This function:
        1. Computes body reference size (elbow → wrist)
        2. Defines target hand size (hand_scale_factor × body_ref)
        3. Computes hand reference size (base → index)
        4. Computes uniform scale factor
        5. Scales all hand points around the hand base
        
        Args:
            points: full landmark array
            hand_start_idx: first hand landmark index (e.g., 48 for left)
            hand_end_idx: last hand landmark index (e.g., 68 for left, inclusive)
            wrist_idx: body wrist index (46 for left, 47 for right)
            elbow_idx: body elbow index (44 for left, 45 for right)
            hand_scale_factor: multiplier for target hand size (0.8 = 80% of arm length)
        """
        # Validate indices
        if wrist_idx >= len(points) or elbow_idx >= len(points):
            return
        
        # Step 1: Compute body reference size (elbow → wrist)
        elbow = points[elbow_idx]
        wrist = points[wrist_idx]
        
        if elbow[0] == 0.0 or wrist[0] == 0.0:
            return  # Invalid body reference
        
        body_ref = math.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1])
        if body_ref < 1e-6:
            return  # Degenerate body segment
        
        # Step 2: Define target hand size
        target_size = body_ref * hand_scale_factor
        
        # Step 3: Compute hand reference size (hand base → index MCP)
        hand_base_idx = hand_start_idx
        index_mcp_idx = hand_start_idx + 5  # Index MCP is typically 5 points after base in hand
        
        if index_mcp_idx >= len(points):
            return
        
        hand_base = points[hand_base_idx]
        index_mcp = points[index_mcp_idx]
        
        if index_mcp[0] == 0.0:
            return  # Invalid hand reference
        
        hand_ref = math.hypot(index_mcp[0] - hand_base[0], index_mcp[1] - hand_base[1])
        if hand_ref < 1e-6:
            return  # Degenerate hand segment
        
        # Step 4: Compute scale factor
        scale = target_size / hand_ref
        
        # Clamp scale to reasonable range to avoid extreme distortions
        scale = max(0.5, min(3.0, scale))
        
        # Apply smoothing to reduce jitter over time
        smooth_attr = f'smooth_hand_scale_{hand_start_idx}'
        if not hasattr(self, smooth_attr):
            setattr(self, smooth_attr, scale)
        
        alpha_smooth = 0.15
        smoothed_scale = alpha_smooth * scale + (1 - alpha_smooth) * getattr(self, smooth_attr)
        setattr(self, smooth_attr, smoothed_scale)
        scale = smoothed_scale
        
        # Step 5: Scale all hand points around the hand base
        base_x, base_y = hand_base[0], hand_base[1]
        
        for i in range(hand_start_idx, hand_end_idx + 1):
            if i < len(points) and (points[i][0] != 0.0 or points[i][1] != 0.0):
                dx = points[i][0] - base_x
                dy = points[i][1] - base_y
                
                dx *= scale
                dy *= scale
                
                points[i][0] = base_x + dx
                points[i][1] = base_y + dy

    def draw_skeleton(self, points):
        if len(points) < 75:
            return
        
        LS, RS, LE, RE, LW, RW = 42, 43, 44, 45, 46, 47
        if points[LS][0] == 0.0 or points[RS][0] == 0.0:
            return
        flip_x = points[LS][0] > points[RS][0]

        def correct_x(val):
            return -val if flip_x else val

        ls_x = correct_x(points[LS][0])
        rs_x = correct_x(points[RS][0])
        ls_y = points[LS][1]
        rs_y = points[RS][1]
        cur_cx = (ls_x + rs_x) / 2.0
        cur_cy = (ls_y + rs_y) / 2.0
        shoulder_width = abs(ls_x - rs_x)
        if shoulder_width < 0.001:
            shoulder_width = 0.001
        target_width = CANVAS_WIDTH * 0.35
        cur_scale = target_width / shoulder_width
        if not hasattr(self, "_frame_count") or self._frame_count == 0:
            self._frame_count = 0
            self.smooth_cx = cur_cx
            self.smooth_cy = cur_cy
            self.smooth_scale = cur_scale
            self.smooth_hands = {}
            print("--- RENDERER ASSIGNMENT ---")
            print(f"Left Shoulder: {LS}, Right Shoulder: {RS}")
            print(f"Left Elbow: {LE}, Right Elbow: {RE}")
            print(f"Left Wrist: {LW}, Right Wrist: {RW}")
        alpha = 0.4
        self.smooth_cx = alpha * cur_cx + (1 - alpha) * self.smooth_cx
        self.smooth_cy = alpha * cur_cy + (1 - alpha) * self.smooth_cy
        self.smooth_scale = alpha * cur_scale + (1 - alpha) * self.smooth_scale
        is_flipped = bool(self.flip_y_var.get())

        translated_left_hand = {}
        if HAND_RENDER_MODE == "point_cloud":
            translated_left_hand = transform_left_hand_points(points, wrist_idx=46, hand_start=48, hand_end=68, hand_anchor_idx=48)

        def get_pt(idx, use_delta=True):
            if idx >= len(points):
                return None

            if idx in translated_left_hand:
                pt = list(translated_left_hand[idx])
            else:
                pt = list(points[idx])
            if pt[0] == 0.0 and pt[1] == 0.0:
                return None
            
            x = correct_x(pt[0])
            y = pt[1]
            
            if idx in (LS, RS):
                y = cur_cy
            
            if idx >= 48:
                if idx not in self.smooth_hands:
                    self.smooth_hands[idx] = (x, y)
                else:
                    prev_x, prev_y = self.smooth_hands[idx]
                    alpha_h = 0.5
                    x = alpha_h * x + (1 - alpha_h) * prev_x
                    y = alpha_h * y + (1 - alpha_h) * prev_y
                    self.smooth_hands[idx] = (x, y)
            
            screen_x = CANVAS_WIDTH / 2.0 + (x - self.smooth_cx) * self.smooth_scale
            screen_y = CANVAS_HEIGHT * 0.3 + (y - self.smooth_cy) * self.smooth_scale
            
            if is_flipped:
                screen_y = CANVAS_HEIGHT - screen_y
            
            return (int(screen_x), int(screen_y))

        upper_body_connections = [(LS, RS), (LS, LE), (LE, LW), (RS, RE), (RE, RW)]
        self._frame_count += 1
        if self._frame_count % 10 == 0:
            print(f"Frame {self._frame_count} - hand_mode={HAND_RENDER_MODE} - L Wrist: {points[LW][:2]}")
            if HAND_RENDER_MODE == "point_cloud":
                print(
                    "POINT CLOUD DEBUG",
                    "body_wrist=", points[46][:2],
                    "raw_hand_anchor=", points[48][:2] if len(points) > 48 else None,
                    "translated_hand_anchor=", translated_left_hand.get(48),
                )
            lh_nodes = [i for i in range(48, min(len(points), 69)) if points[i][0] != 0.0]
            if lh_nodes:
                print(f"  Left Hand Non-Zero Indices: {lh_nodes}")
            rh_nodes = [i for i in range(69, min(len(points), 90)) if points[i][0] != 0.0]
            if rh_nodes:
                print(f"  Right Hand Non-Zero Indices: {rh_nodes}")
        for u, v in upper_body_connections:
            p1 = get_pt(u)
            p2 = get_pt(v)
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="red", width=3)

        if self.hand_chains_var.get():
            if HAND_RENDER_MODE == "point_cloud":
                hand_points = [
                    (idx, float(pt[0]), float(pt[1]))
                    for idx, pt in sorted(translated_left_hand.items())
                    if pt[0] != 0.0 or pt[1] != 0.0
                ]
            else:
                hand_points = get_hand_points(points, 48, 68)

            if HAND_RENDER_MODE == "canonical_hand":
                for u, v in CANONICAL_LEFT_HAND_CONNECTIONS:
                    p1 = get_pt(u, use_delta=True)
                    p2 = get_pt(v, use_delta=True)
                    if p1 and p2:
                        self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="green", width=2)
                for idx in range(69, min(len(points), 90)):
                    pt = get_pt(idx, use_delta=True)
                    if pt:
                        self.canvas.create_oval(pt[0] - 2, pt[1] - 2, pt[0] + 2, pt[1] + 2, fill="orange", outline="orange")
            else:
                draw_hand_point_cloud(
                    self.canvas,
                    hand_points,
                    lambda idx: get_pt(idx, use_delta=True),
                    draw_edges=HAND_PC_DRAW_LOCAL_EDGES,
                    draw_hull=HAND_PC_DRAW_HULL,
                    draw_centroid=HAND_PC_DRAW_CENTROID,
                    draw_bbox=HAND_PC_DRAW_BBOX,
                    point_fill="#72ff8f",
                    edge_fill="#2e8b57",
                    hull_fill="#6ad6ff",
                    bbox_fill="#e6ff66",
                    centroid_fill="#ff4fd8",
                )

                if self.debug_var.get() and hand_points:
                    cx = sum(x for _, x, _ in hand_points) / len(hand_points)
                    cy = sum(y for _, y, _ in hand_points) / len(hand_points)
                    centroid_idx = min(hand_points, key=lambda item: _distance_xy((item[1], item[2]), (cx, cy)))[0]
                    centroid_pt = get_pt(centroid_idx, use_delta=True)
                    if centroid_pt:
                        self.canvas.create_text(
                            centroid_pt[0] + 28,
                            centroid_pt[1] - 14,
                            text="LH cloud",
                            fill="#ffd166",
                            font=("Arial", 10, "bold"),
                        )

                if HAND_PC_PRINT_METRICS and hand_points and self._frame_count % 10 == 0:
                    xs = [x for _, x, _ in hand_points]
                    ys = [y for _, _, y in hand_points]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    cx = sum(xs) / len(xs)
                    cy = sum(ys) / len(ys)
                    wrist_pt = points[46]
                    centroid_to_wrist = math.hypot(cx - wrist_pt[0], cy - wrist_pt[1])
                    print(
                        "HAND CLOUD",
                        "centroid=", (round(cx, 4), round(cy, 4)),
                        "bbox=", (round(min_x, 4), round(min_y, 4), round(max_x, 4), round(max_y, 4)),
                        "spread_w=", round(max_x - min_x, 4),
                        "spread_h=", round(max_y - min_y, 4),
                        "centroid_to_wrist=", round(centroid_to_wrist, 4),
                    )

                for idx in range(69, min(len(points), 90)):
                    pt = get_pt(idx, use_delta=True)
                    if pt:
                        self.canvas.create_oval(pt[0] - 2, pt[1] - 2, pt[0] + 2, pt[1] + 2, fill="orange", outline="orange")
        else:
            # Points-only mode for quick debugging.
            for idx in range(48, min(len(points), 90)):
                pt = get_pt(idx, use_delta=True)
                if pt:
                    color = "green" if idx <= 68 else "orange"
                    self.canvas.create_oval(pt[0] - 2, pt[1] - 2, pt[0] + 2, pt[1] + 2, fill=color, outline=color)

        if self.debug_var.get():
            for idx in range(48, min(len(points), 69)):
                pt = get_pt(idx, use_delta=True)
                if pt:
                    self.canvas.create_text(pt[0] + 12, pt[1] - 12, text=str(idx), fill="white", font=("Arial", 10))

        explorer_active = self.explorer_window is not None and self.explorer_window.winfo_exists()
        if explorer_active and self.explorer_active_edges:
            for u, v in self.explorer_active_edges:
                p1 = get_pt(u, use_delta=True)
                p2 = get_pt(v, use_delta=True)
                if p1 and p2:
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="cyan", width=3)
        elif self.show_inferred_var.get() and self.top_k_edges_result:
            for u, v in self.top_k_edges_result:
                p1 = get_pt(u, use_delta=True)
                p2 = get_pt(v, use_delta=True)
                if p1 and p2:
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="magenta", width=2)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Tester CLI test mode: Syntax and imports successful. Exiting.")
        sys.exit(0)
    root = tk.Tk()
    app = GesturaTesterApp(root)
    root.mainloop()
