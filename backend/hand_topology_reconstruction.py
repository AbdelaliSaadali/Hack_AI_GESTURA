import heapq
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean

START_IDX = 48
END_IDX = 68
DEFAULT_MAX_EDGE_DISTANCE = 0.20
DEFAULT_MAX_ROOT_DEGREE = 5
DEFAULT_MAX_NODE_DEGREE = 2
DEFAULT_MAX_DEPTH = 4
DEFAULT_SCORE_ALPHA = 1.0
DEFAULT_INWARD_TOLERANCE = 0.015
DEFAULT_ROOT_NEIGHBOR_COUNT = 4
DEFAULT_ROOT_Y_WEIGHT = 0.0


def _is_non_zero(point):
    return point is not None and (point[0] != 0.0 or point[1] != 0.0)


def _frame_points(frame, start_idx=START_IDX, end_idx=END_IDX):
    points = {}
    if len(frame) <= start_idx:
        return points
    upper = min(end_idx, len(frame) - 1)
    for idx in range(start_idx, upper + 1):
        point = frame[idx]
        if _is_non_zero(point):
            points[idx] = (float(point[0]), float(point[1]))
    return points


def _pair_key(u, v):
    return (u, v) if u < v else (v, u)


def _build_pair_statistics(frames, start_idx=START_IDX, end_idx=END_IDX):
    pair_dists = defaultdict(list)
    node_positions = defaultdict(list)

    for frame in frames:
        pts = _frame_points(frame, start_idx=start_idx, end_idx=end_idx)
        for idx, point in pts.items():
            node_positions[idx].append(point)

        indices = sorted(pts)
        for i, u in enumerate(indices):
            ux, uy = pts[u]
            for v in indices[i + 1 :]:
                vx, vy = pts[v]
                pair_dists[_pair_key(u, v)].append(math.hypot(ux - vx, uy - vy))

    pair_stats = []
    for edge, distances in pair_dists.items():
        if len(distances) < 2:
            continue
        edge_mean = sum(distances) / len(distances)
        edge_variance = sum((distance - edge_mean) ** 2 for distance in distances) / len(distances)
        pair_stats.append(
            {
                "edge": list(edge),
                "mean": edge_mean,
                "variance": edge_variance,
                "score": edge_mean + DEFAULT_SCORE_ALPHA * edge_variance,
                "samples": len(distances),
            }
        )

    centroids = {
        idx: (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
        for idx, points in node_positions.items()
        if points
    }

    return pair_stats, centroids


def _choose_root(centroids, pair_stats, prefer_high_y=False):
    if not centroids:
        return None

    edge_lookup = defaultdict(list)
    for stat in pair_stats:
        u, v = stat["edge"]
        edge_lookup[u].append(stat)
        edge_lookup[v].append(stat)

    y_values = [point[1] for point in centroids.values()]
    y_min = min(y_values)
    y_max = max(y_values)
    y_span = max(y_max - y_min, 1e-6)

    best_node = None
    best_score = None

    for node, centroid in centroids.items():
        distances = []
        for other, other_point in centroids.items():
            if other == node:
                continue
            distances.append(math.hypot(centroid[0] - other_point[0], centroid[1] - other_point[1]))
        if not distances:
            continue

        distances.sort()
        neighborhood = distances[: min(DEFAULT_ROOT_NEIGHBOR_COUNT, len(distances))]
        local_mean = sum(neighborhood) / len(neighborhood)
        support = sum(1 for distance in distances if distance <= neighborhood[-1])
        incident = edge_lookup.get(node, [])
        incident_mean = sum(stat["mean"] for stat in incident[: min(3, len(incident))]) / max(1, min(3, len(incident)))

        y_norm = (centroid[1] - y_min) / y_span
        y_bonus = y_norm if prefer_high_y else 0.0
        root_score = local_mean + 0.25 * incident_mean - 0.05 * support - DEFAULT_ROOT_Y_WEIGHT * y_bonus

        if best_score is None or root_score < best_score:
            best_score = root_score
            best_node = node

    return best_node


def _build_tree(pair_stats, centroids, root, max_edge_distance=DEFAULT_MAX_EDGE_DISTANCE, max_root_degree=DEFAULT_MAX_ROOT_DEGREE, max_node_degree=DEFAULT_MAX_NODE_DEGREE, max_depth=DEFAULT_MAX_DEPTH, inward_tolerance=DEFAULT_INWARD_TOLERANCE):
    if root is None or root not in centroids:
        return [], {}

    incident = defaultdict(list)
    for stat in pair_stats:
        if stat["mean"] > max_edge_distance:
            continue
        u, v = stat["edge"]
        incident[u].append(stat)
        incident[v].append(stat)

    for node in incident:
        incident[node].sort(key=lambda item: (item["score"], item["mean"], item["variance"]))

    root_radius = {
        node: math.hypot(point[0] - centroids[root][0], point[1] - centroids[root][1])
        for node, point in centroids.items()
    }

    visited = {root}
    depth = {root: 0}
    degree = defaultdict(int)
    tree_edges = []
    frontier = []

    def push_node_edges(node):
        for stat in incident.get(node, []):
            u, v = stat["edge"]
            other = v if u == node else u
            if other in visited:
                continue
            priority = (
                stat["score"],
                abs(root_radius.get(other, 0.0) - root_radius.get(node, 0.0)),
                stat["mean"],
            )
            heapq.heappush(frontier, (priority, node, other, stat))

    push_node_edges(root)

    while frontier and len(visited) < len(centroids):
        _, parent, child, stat = heapq.heappop(frontier)
        if child in visited:
            continue

        parent_limit = max_root_degree if parent == root else max_node_degree
        if degree[parent] >= parent_limit:
            continue
        if degree[child] >= max_node_degree:
            continue

        parent_depth = depth.get(parent, 0)
        if parent_depth + 1 > max_depth:
            continue

        if root_radius.get(child, 0.0) + inward_tolerance < root_radius.get(parent, 0.0):
            continue

        visited.add(child)
        depth[child] = parent_depth + 1
        degree[parent] += 1
        degree[child] += 1
        tree_edges.append([parent, child])
        push_node_edges(child)

    if len(visited) < len(centroids):
        relaxed_edges = sorted(
            pair_stats,
            key=lambda item: (item["score"], item["mean"], item["variance"]),
        )
        for stat in relaxed_edges:
            u, v = stat["edge"]
            if u in visited and v in visited:
                continue
            if u not in visited and v not in visited:
                continue

            parent, child = (u, v) if u in visited else (v, u)
            parent_limit = max_root_degree if parent == root else max_node_degree
            if degree[parent] >= parent_limit or degree[child] >= max_node_degree:
                continue

            parent_depth = depth.get(parent, 0)
            if parent_depth + 1 > max_depth:
                continue

            if root_radius.get(child, 0.0) + inward_tolerance < root_radius.get(parent, 0.0):
                continue

            visited.add(child)
            depth[child] = parent_depth + 1
            degree[parent] += 1
            degree[child] += 1
            tree_edges.append([parent, child])
            if len(visited) == len(centroids):
                break

    return tree_edges, depth


def _extract_branches(tree_edges, root):
    adjacency = defaultdict(list)
    for u, v in tree_edges:
        adjacency[u].append(v)
        adjacency[v].append(u)

    branches = []
    for child in sorted(adjacency.get(root, [])):
        branch = [root, child]
        previous = root
        current = child

        while True:
            neighbors = [node for node in adjacency[current] if node != previous]
            if not neighbors:
                break
            if len(neighbors) > 1:
                neighbors.sort()
            next_node = neighbors[0]
            branch.append(next_node)
            previous, current = current, next_node
            if len(branch) >= 6:
                break

        branches.append(branch)

    return branches


def reconstruct_hand_topology(
    frames,
    start_idx=START_IDX,
    end_idx=END_IDX,
    output_path=None,
    prefer_high_y=False,
    max_edge_distance=DEFAULT_MAX_EDGE_DISTANCE,
    max_root_degree=DEFAULT_MAX_ROOT_DEGREE,
    max_node_degree=DEFAULT_MAX_NODE_DEGREE,
    max_depth=DEFAULT_MAX_DEPTH,
    inward_tolerance=DEFAULT_INWARD_TOLERANCE,
):
    """
    Reconstruct a hand skeleton from unordered points in the index range.

    The result is a constrained tree: one inferred root, up to five branches,
    no cycles, and low degree for non-root nodes.
    """
    pair_stats, centroids = _build_pair_statistics(frames, start_idx=start_idx, end_idx=end_idx)
    root = _choose_root(centroids, pair_stats, prefer_high_y=prefer_high_y)
    tree_edges, depth = _build_tree(
        pair_stats,
        centroids,
        root,
        max_edge_distance=max_edge_distance,
        max_root_degree=max_root_degree,
        max_node_degree=max_node_degree,
        max_depth=max_depth,
        inward_tolerance=inward_tolerance,
    )
    branches = _extract_branches(tree_edges, root) if root is not None else []

    result = {
        "start_idx": start_idx,
        "end_idx": end_idx,
        "root": root,
        "edges": tree_edges,
        "branches": branches,
        "node_depths": depth,
        "pair_stats": sorted(pair_stats, key=lambda item: (item["score"], item["mean"], item["variance"])),
    }

    if output_path:
        output_path = Path(output_path)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def load_reconstructed_topology(path):
    path = Path(path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"edges": data, "branches": [], "root": None}
    if isinstance(data, dict):
        return data
    return None


def draw_reconstructed_hand(canvas, points, edges, get_point, color="green", width=2):
    if not edges:
        return
    for edge in edges:
        if not edge or len(edge) < 2:
            continue
        u, v = edge[0], edge[1]
        p1 = get_point(u)
        p2 = get_point(v)
        if p1 and p2:
            canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=color, width=width)


def reconstruct_from_candidate_stats(candidate_stats, output_path=None, prefer_high_y=False, max_root_degree=DEFAULT_MAX_ROOT_DEGREE, max_node_degree=DEFAULT_MAX_NODE_DEGREE, max_depth=DEFAULT_MAX_DEPTH, inward_tolerance=DEFAULT_INWARD_TOLERANCE):
    """
    Reconstruct a topology from precomputed pair statistics.

    candidate_stats should be a list of dicts with keys:
    edge, mean, variance, score, samples.
    """
    pair_stats = []
    nodes = set()
    for item in candidate_stats:
        if "edge" not in item:
            continue
        u, v = item["edge"]
        nodes.add(u)
        nodes.add(v)
        pair_stats.append(
            {
                "edge": [u, v],
                "mean": float(item.get("mean", 0.0)),
                "variance": float(item.get("variance", 0.0)),
                "score": float(item.get("score", float(item.get("mean", 0.0)) + float(item.get("variance", 0.0)))),
                "samples": int(item.get("samples", 0)),
            }
        )

    if not nodes:
        result = {"root": None, "edges": [], "branches": [], "pair_stats": []}
        if output_path:
            Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    # When only candidate stats are available, approximate centroids using a simple
    # pseudo-geometry inferred from edge support. Nodes with many low-score links
    # are treated as more central.
    node_support = defaultdict(list)
    for stat in pair_stats:
        u, v = stat["edge"]
        node_support[u].append(stat)
        node_support[v].append(stat)

    pseudo_centroids = {}
    for node in nodes:
        support = node_support.get(node, [])
        if support:
            strength = sum(stat["score"] for stat in support) / len(support)
            pseudo_centroids[node] = (strength, -len(support))
        else:
            pseudo_centroids[node] = (float(node), 0.0)

    root = _choose_root(pseudo_centroids, pair_stats, prefer_high_y=prefer_high_y)
    tree_edges, depth = _build_tree(
        pair_stats,
        pseudo_centroids,
        root,
        max_edge_distance=float("inf"),
        max_root_degree=max_root_degree,
        max_node_degree=max_node_degree,
        max_depth=max_depth,
        inward_tolerance=inward_tolerance,
    )
    branches = _extract_branches(tree_edges, root) if root is not None else []
    result = {
        "root": root,
        "edges": tree_edges,
        "branches": branches,
        "node_depths": depth,
        "pair_stats": sorted(pair_stats, key=lambda item: (item["score"], item["mean"], item["variance"])),
    }
    if output_path:
        Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
