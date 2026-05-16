import tkinter as tk
from tkinter import messagebox
import requests
import threading
import queue
import os
import glob
import json
import math

# Configuration
API_URL = "http://127.0.0.1:8000/translate"
CANVAS_WIDTH = 600
CANVAS_HEIGHT = 600
FRAME_DELAY_MS = 80  # ~12.5 fps

# Connections for drawing skeletons (Based on explicit backend tracking)
# The data is exclusively 33 MediaPipe pose landmarks offset by exactly 42.
# 53/54 = Shoulders
# 55/56 = Elbows
# 57/58 = Wrists
# 65/66 = Hips
# 67/68 = Knees
# 69/70 = Ankles

BODY_CONNECTIONS = [
    (53, 54),           # Shoulders (Left 53 -> Right 54)
    (65, 66),           # Hips (Left 65 -> Right 66)
    (53, 65), (54, 66), # Torso sides (Shoulder -> Hip)
    (53, 55), (55, 57), # Left Arm (Shoulder -> Elbow -> Wrist)
    (54, 56), (56, 58), # Right Arm (Shoulder -> Elbow -> Wrist)
    (65, 67), (67, 69), # Left Leg (Hip -> Knee -> Ankle)
    (66, 68), (68, 70), # Right Leg (Hip -> Knee -> Ankle)
]

# There are no full 21-point hands in this format, only the 3 Pose hand stubs per side
LEFT_HAND_CONNECTIONS = [
    (57, 59), # Left Wrist (57) -> Left Pinky (59)
    (57, 61), # Left Wrist (57) -> Left Index (61)
    (57, 63), # Left Wrist (57) -> Left Thumb (63)
    (59, 61)  # Left Pinky (59) -> Left Index (61)
]

RIGHT_HAND_CONNECTIONS = [
    (58, 60), # Right Wrist (58) -> Right Pinky (60)
    (58, 62), # Right Wrist (58) -> Right Index (62)
    (58, 64), # Right Wrist (58) -> Right Thumb (64)
    (60, 62)  # Right Pinky (60) -> Right Index (62)
]

BODY_TO_HAND_CONNECTIONS = []

def map_coord(normalized_val, max_pixel):
    """Map [0.0, 1.0] to [0, max_pixel]. Clamps to avoid out of bounds drawing."""
    val = max(0.0, min(1.0, normalized_val))
    return int(val * max_pixel)

class GesturaTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestura PC Tester")
        self.root.geometry(f"{CANVAS_WIDTH + 40}x{CANVAS_HEIGHT + 140}")
        
        # User Intput
        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=10)
        
        tk.Label(input_frame, text="Enter word(s): ").pack(side=tk.LEFT)
        
        # Styled entry field for macOS visibility
        self.entry = tk.Entry(
            input_frame, width=20,
            bg="white", fg="black", insertbackground="black",
            disabledbackground="#e0e0e0", disabledforeground="black",
            highlightthickness=1, highlightcolor="blue", bd=2,
            selectbackground="lightblue", selectforeground="black"
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
            [(64, 65), (65, 66), (66, 67)]
        ]
        self.cycle_btn = tk.Button(input_frame, text=f"Test Edge ({self.chain_idx+1}/5)", command=self.cycle_test)
        self.cycle_btn.pack(side=tk.LEFT, padx=5)
        
        # Analytics UI
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
        
        self.top_k_edges_result = [] # Will store output from analytics
        self.raw_frames_cache = []
        self.current_word = "unknown"
        
        # Status Label
        self.status_var = tk.StringVar()
        self.status_var.set("Status: Ready")
        self.status_label = tk.Label(self.root, textvariable=self.status_var, fg="blue")
        self.status_label.pack()
        
        # Canvas
        self.canvas = tk.Canvas(self.root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="darkblue")
        self.canvas.pack(pady=10)
        
        # Animation state
        self.is_playing = False
        self.animation_queue = [] # Queue of frames across multiple signs
        
        print("NEW RENDERER LOADED")
        
        # Thread safety
        self.result_queue = queue.Queue()
        self.root.after(100, self.poll_queue)
    
    def open_explorer(self):
        files = glob.glob("topology_filtered_*.json")
        if not files:
            print("No filtered topology files found.")
            return

        latest_file = max(files, key=os.path.getctime)
        with open(latest_file, "r") as f:
            candidates = json.load(f)

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

        if hasattr(self, "explorer_window") and self.explorer_window.winfo_exists():
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
        tk.Radiobutton(mode_frame, text="A (Single Edge)", variable=self.mode_var, value="A",
                       command=self.change_explorer_mode).pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="B (Pairs)", variable=self.mode_var, value="B",
                       command=self.change_explorer_mode).pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="C (Subgraphs)", variable=self.mode_var, value="C",
                       command=self.change_explorer_mode).pack(side=tk.LEFT)

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
            tk.Radiobutton(speed_frame, text=f"{s}ms", variable=self.speed_var, value=s,
                           command=self.update_speed).pack(side=tk.LEFT)

        self.lbl_edges = tk.Label(top, text="", fg="blue", wraplength=390, justify="left")
        self.lbl_edges.pack(pady=10)

        self.update_explorer()

        if not self.is_playing and getattr(self, "raw_frames_cache", None):
            self.is_playing = True
            self.play_next_frame()

    def get_current_total(self):
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
        if not hasattr(self, "explorer_window") or not self.explorer_window.winfo_exists():
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
        print(f"RESET explorer_idx from change_explorer_mode -> 0")
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
        if getattr(self, "explorer_after_id", None):
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
        self.play_btn.config(relief=tk.SUNKEN)
        self.schedule_explorer_tick()

    def schedule_explorer_tick(self):
        if not self.explorer_autoplay:
            return
        self.explorer_after_id = self.root.after(self.explorer_speed, self.run_autoplay)

    def run_autoplay(self):
        if not self.explorer_autoplay:
            return

        if not hasattr(self, "explorer_window") or not self.explorer_window.winfo_exists():
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
        self.cycle_btn.config(text=f"Test Edge ({self.chain_idx+1}/5)")
        print(f"--- NOW TESTING EDGES: {self.test_chains[self.chain_idx]} ---")

    def analyze_topology(self):
        if not hasattr(self, 'raw_frames_cache') or not self.raw_frames_cache:
            print("No frames cached for analysis.")
            return

        print(f"--- ANALYZING TOPOLOGY ({len(self.raw_frames_cache)} frames) ---")
        history = {}
        for frames in self.raw_frames_cache:
            if len(frames) <= 68: continue
            
            # Reconstruct translation logic
            lw_raw = frames[46]
            lh_base = frames[48]
            if lw_raw[0] == 0.0 or lh_base[0] == 0.0: continue
            
            dx = lw_raw[0] - lh_base[0]
            dy = lw_raw[1] - lh_base[1]
            
            # Apply delta to temporal points
            pts = []
            for i in range(48, 69):
                raw = frames[i]
                if raw[0] != 0.0:
                    pts.append((i, raw[0] + dx, raw[1] + dy))
                else:
                    pts.append((i, None, None))
            
            # Calculate all pairs
            for u_idx, (u, ux, uy) in enumerate(pts):
                if ux is None: continue
                for v_idx in range(u_idx + 1, len(pts)):
                    v, vx, vy = pts[v_idx]
                    if vx is None: continue
                    dist = math.hypot(ux - vx, uy - vy)
                    
                    pair = (u, v)
                    if pair not in history: history[pair] = []
                    history[pair].append(dist)
                    
        # UI limits
        try:
            top_k = int(self.top_k_var.get())
            min_dist = float(self.min_dist_var.get())
            max_dist = float(self.max_dist_var.get())
            max_degree = int(self.max_degree_var.get())
        except:
            top_k, min_dist, max_dist, max_degree = 20, 0.02, 0.16, 2

        # Compute metrics
        results = []
        for pair, dists in history.items():
            if len(dists) < 2: continue
            mean = sum(dists) / len(dists)
            variance = sum((d - mean)**2 for d in dists) / len(dists)
            score = variance * mean  # Low variance + low distance = rigid localized bones
            results.append({"edge": pair, "mean": mean, "variance": variance, "score": score, "samples": len(dists)})
            
        # 1. & 2. Apply explicit Distance Filters
        filtered_candidates = [r for r in results if min_dist <= r['mean'] <= max_dist]
        
        # 3. Sort purely valid candidates by score
        filtered_candidates.sort(key=lambda x: x["score"])

        # 4. & 5. Node Degree Constraints & Progressive Re-ranking Build
        degree_count = {i: 0 for i in range(48, 69)}
        accepted_edges = []
        
        for cand in filtered_candidates:
            u, v = cand["edge"]
            if degree_count[u] < max_degree and degree_count[v] < max_degree:
                accepted_edges.append(cand)
                degree_count[u] += 1
                degree_count[v] += 1
                if len(accepted_edges) >= top_k:
                    break
        
        # 6. Print top filtered list
        print(f"Top {top_k} Filtered progressive Candidate Edges:")
        for i, r in enumerate(accepted_edges):
            print(f"Rank {i+1}: {r['edge']} | Mean: {r['mean']:.4f} | Var: {r['variance']:.6f} | Score: {r['score']:.6f}")
            
        # 7. Export JSONs
        filename = f"topology_{self.current_word}.json"
        with open(filename, "w") as f:
            json.dump(results, f, indent=2)
            
        filtered_filename = f"topology_filtered_{self.current_word}.json"
        with open(filtered_filename, "w") as f:
            json.dump(accepted_edges, f, indent=2)
            
        print(f"Exported raw to {filename} and filtered to {filtered_filename}")
        
        self.top_k_edges_result = [r["edge"] for r in accepted_edges]

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
        self.is_playing = False # Cancel any ongoing playback
        self._frame_count = 0 # Reset renderer sequence counter
        
        # Run network call in thread
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
                # Append a special marker for fingerspelling
                self.animation_queue.append({"type": "message", "text": f"[{gloss}] - Fingerspelling/Not Found"})
            else:
                frames = sign.get("frames", [])
                if not frames:
                    self.animation_queue.append({"type": "message", "text": f"[{gloss}] - Empty frames"})
                    continue
                
                # Append frames
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
            
        explorer_running = hasattr(self, 'explorer_window') and self.explorer_window.winfo_exists()
        
        if not self.animation_queue:
            if explorer_running and hasattr(self, 'raw_frames_cache') and self.raw_frames_cache:
                for point_cloud in self.raw_frames_cache:
                    self.animation_queue.append({"type": "skeleton", "points": point_cloud})
            else:
                self.is_playing = False
                self.update_status("Finished.", "blue")
                return
                
        frame_data = self.animation_queue.pop(0)
        self.canvas.delete("all")
        
        if explorer_running:
            self.current_frame_index = len(self.raw_frames_cache) - len(self.animation_queue)
            # Use a slightly less noisy log for regular frames, but include indices
            if self.current_frame_index % 5 == 0:
                print(f"Animating frame={self.current_frame_index}, explorer_idx={self.explorer_idx}")
            self.update_status(f"frame={self.current_frame_index} | explorer={self.explorer_idx}", "green")
            
        if frame_data["type"] == "message":
            self.canvas.create_text(
                CANVAS_WIDTH//2, CANVAS_HEIGHT//2, 
                text=frame_data["text"], fill="white", font=("Arial", 20, "bold")
            )
            self.root.after(1000, self.play_next_frame)
            return
            
        points = frame_data["points"]
        self.draw_skeleton(points)
        self.root.after(FRAME_DELAY_MS, self.play_next_frame)

    def draw_skeleton(self, points):
        if len(points) < 75:
            return
            
        # Dynamically scale points so they fit the canvas regardless of bounds
        # Explicit Upper Body Mapping
        LS = 42 # Left Shoulder
        RS = 43 # Right Shoulder
        LE = 44 # Left Elbow
        RE = 45 # Right Elbow
        LW = 46 # Left Wrist
        RW = 47 # Right Wrist

        if points[LS][0] == 0.0 or points[RS][0] == 0.0:
            return

        # 3. Ensure left/right are not flipped
        # "left shoulder must always be visually on the left side"
        # So we ensure LS.x < RS.x visually. If inverted, correct it.
        flip_x = points[LS][0] > points[RS][0]
        def correct_x(val):
            return -val if flip_x else val

        ls_x = correct_x(points[LS][0])
        rs_x = correct_x(points[RS][0])
        ls_y = points[LS][1]
        rs_y = points[RS][1]

        # 1. Use shoulders as reference frame
        cur_cx = (ls_x + rs_x) / 2.0
        
        # 4. Lock vertical alignment by averaging their y
        cur_cy = (ls_y + rs_y) / 2.0

        # 2. Normalize scale using shoulder width
        shoulder_width = abs(ls_x - rs_x)
        if shoulder_width < 0.001: shoulder_width = 0.001
        
        TARGET_WIDTH = CANVAS_WIDTH * 0.35
        cur_scale = TARGET_WIDTH / shoulder_width

        # Reset smoothing if this is the start of a sequence
        if not hasattr(self, '_frame_count') or self._frame_count == 0:
            self._frame_count = 0
            self.smooth_cx = cur_cx
            self.smooth_cy = cur_cy
            self.smooth_scale = cur_scale
            self.smooth_hands = {}
            # Print exact chosen mapping for debug requirement
            print(f"--- RENDERER ASSIGNMENT ---")
            print(f"Left Shoulder: {LS}, Right Shoulder: {RS}")
            print(f"Left Elbow: {LE}, Right Elbow: {RE}")
            print(f"Left Wrist: {LW}, Right Wrist: {RW}")

        # 5. Apply smoothing (temporal smoothing)
        alpha = 0.4
        self.smooth_cx = alpha * cur_cx + (1 - alpha) * self.smooth_cx
        self.smooth_cy = alpha * cur_cy + (1 - alpha) * self.smooth_cy
        self.smooth_scale = alpha * cur_scale + (1 - alpha) * self.smooth_scale

        is_flipped = bool(self.flip_y_var.get())

        # --- Compute Deltas for Hand Translation ---
        # 46 is left wrist (raw)
        # 48 is left hand base (raw)
        l_delta_x, l_delta_y = 0.0, 0.0
        r_delta_x, r_delta_y = 0.0, 0.0

        if len(points) > 48 and points[LW][0] != 0.0 and points[48][0] != 0.0:
            l_delta_x = points[LW][0] - points[48][0]
            l_delta_y = points[LW][1] - points[48][1]

        if len(points) > 69 and points[RW][0] != 0.0 and points[69][0] != 0.0:
            r_delta_x = points[RW][0] - points[69][0]
            r_delta_y = points[RW][1] - points[69][1]

        def get_pt(idx, use_delta=True):
            if idx >= len(points): return None
            pt = list(points[idx])
            if pt[0] == 0.0 and pt[1] == 0.0: return None
            
            # Apply cluster translation
            if use_delta:
                if 48 <= idx <= 68:
                    pt[0] += l_delta_x
                    pt[1] += l_delta_y
                elif idx >= 69:
                    pt[0] += r_delta_x
                    pt[1] += r_delta_y

            x = correct_x(pt[0])
            y = pt[1]
            
            # Align shoulders horizontally for visualization
            if idx == LS or idx == RS:
                y = cur_cy
                
            # Apply temporal smoothing to hand points
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

        is_debug = self.debug_var.get()

        UPPER_BODY_CONNECTIONS = [
            (LS, RS),            # Left Shoulder to Right Shoulder
            (LS, LE), (LE, LW),  # Left Arm
            (RS, RE), (RE, RW),  # Right Arm
        ]

        self._frame_count += 1
        
        if self._frame_count % 10 == 0:
            print(f"Frame {self._frame_count} - L Wrist: {points[LW][:2]}, Raw L Hand Base: {points[48][:2] if len(points)>48 else None}, Distance dX={l_delta_x:.3f} dY={l_delta_y:.3f}")
            # print all non-zero left-hand indices
            lh_nodes = [i for i in range(48, min(len(points), 69)) if points[i][0] != 0.0]
            if lh_nodes:
                print(f"  Left Hand Non-Zero Indices: {lh_nodes}")
            # 4. Inspect right hand ranges natively
            rh_nodes = [i for i in range(69, min(len(points), 90)) if points[i][0] != 0.0]
            if rh_nodes:
                print(f"  Right Hand Non-Zero Indices: {rh_nodes}")

        # 1. Draw fixed explicit connections (Torso only as requested)
        for u, v in UPPER_BODY_CONNECTIONS:
            p1 = get_pt(u)
            p2 = get_pt(v)
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="red", width=3)
                
        draw_chains = self.hand_chains_var.get()
        
        if draw_chains:
            # Minimal hand edges for debugging internal hand topography
            MINIMAL_HAND_EDGES = self.test_chains[self.chain_idx]
            
            for u, v in MINIMAL_HAND_EDGES:
                p1 = get_pt(u, use_delta=True)
                p2 = get_pt(v, use_delta=True)
                if p1 and p2:
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="green", width=2)
                    
            # Keep Right Hand omitted completely aside from points debug
            for idx in range(69, min(len(points), 90)):
                pt = get_pt(idx, use_delta=True)
                if pt:
                    self.canvas.create_oval(pt[0]-2, pt[1]-2, pt[0]+2, pt[1]+2, fill="orange", outline="orange")
        else:
            # Points-only hands mode
            for idx in range(48, min(len(points), 90)):
                pt = get_pt(idx, use_delta=True)
                if pt:
                    color = "green" if idx <= 68 else "orange"
                    self.canvas.create_oval(pt[0]-2, pt[1]-2, pt[0]+2, pt[1]+2, fill=color, outline=color)

        # 3. Add explicit debug text for tracing internal arrays manually
        if is_debug:
            for idx in range(48, min(len(points), 69)):
                pt = get_pt(idx, use_delta=True)
                if pt:
                    self.canvas.create_text(pt[0]+12, pt[1]-12, text=str(idx), fill="white", font=("Arial", 10))
                    
        # 4. Topology Overlay Mode
        explorer_active = hasattr(self, 'explorer_window') and self.explorer_window.winfo_exists()
        
        if explorer_active and hasattr(self, 'explorer_active_edges'):
            for u, v in self.explorer_active_edges:
                p1 = get_pt(u, use_delta=True)
                p2 = get_pt(v, use_delta=True)
                if p1 and p2:
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="cyan", width=3)
        elif self.show_inferred_var.get() and getattr(self, 'top_k_edges_result', None):
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
