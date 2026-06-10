#!/usr/bin/env python3
"""
Event-triggered dynamic replanning on top of static global planning.

Core idea:
- Start from a static global sparse path.
- At each time step, inject dynamic obstacles into a temporary occupancy map.
- If remaining path is blocked by new obstacles, trigger replanning from current robot position.
- Add anti-jitter protections: block confirmation + replan cooldown.

Input obstacle JSON example:
{
  "frames": [
    {"t": 0.0, "obstacles": [{"x": 0.5, "y": 1.2, "r": 0.4}]},
    {"t": 0.5, "obstacles": [{"x": 0.6, "y": 1.2, "r": 0.4}]}
  ]
}
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class DynObstacle:
    x: float
    y: float
    r: float


def world_to_grid(x: float, y: float, origin: np.ndarray, res: float) -> tuple[int, int]:
    gx = int(math.floor((x - origin[0]) / res))
    gy = int(math.floor((y - origin[1]) / res))
    return gx, gy


def grid_to_world(gx: int, gy: int, origin: np.ndarray, res: float) -> tuple[float, float]:
    x = origin[0] + (gx + 0.5) * res
    y = origin[1] + (gy + 0.5) * res
    return x, y


def in_bounds(gx: int, gy: int, w: int, h: int) -> bool:
    return 0 <= gx < w and 0 <= gy < h


def line_is_free(occ: np.ndarray, a: tuple[int, int], b: tuple[int, int]) -> bool:
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    h, w = occ.shape
    x, y = x0, y0
    while True:
        if not in_bounds(x, y, w, h) or occ[y, x] != 0:
            return False
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return True


def astar(occ: np.ndarray, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    h, w = occ.shape
    if not in_bounds(start[0], start[1], w, h) or not in_bounds(goal[0], goal[1], w, h):
        raise ValueError("Start or goal out of map bounds")
    if occ[start[1], start[0]] != 0:
        raise ValueError("Start in obstacle")
    if occ[goal[1], goal[0]] != 0:
        raise ValueError("Goal in obstacle")

    neigh = [
        (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
        (-1, -1, math.sqrt(2.0)), (-1, 1, math.sqrt(2.0)),
        (1, -1, math.sqrt(2.0)), (1, 1, math.sqrt(2.0)),
    ]

    def heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    g_cost: dict[tuple[int, int], float] = {start: 0.0}
    parent: dict[tuple[int, int], tuple[int, int]] = {}
    open_heap: list[tuple[float, tuple[int, int]]] = [(heuristic(start, goal), start)]
    closed: set[tuple[int, int]] = set()

    while open_heap:
        _, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        closed.add(cur)

        if cur == goal:
            path = [cur]
            while cur in parent:
                cur = parent[cur]
                path.append(cur)
            path.reverse()
            return path

        cx, cy = cur
        for dx, dy, step in neigh:
            nx, ny = cx + dx, cy + dy
            nxt = (nx, ny)
            if not in_bounds(nx, ny, w, h) or occ[ny, nx] != 0:
                continue
            if dx != 0 and dy != 0 and (occ[cy, nx] != 0 or occ[ny, cx] != 0):
                continue

            ng = g_cost[cur] + step
            if ng < g_cost.get(nxt, float("inf")):
                g_cost[nxt] = ng
                parent[nxt] = cur
                heapq.heappush(open_heap, (ng + heuristic(nxt, goal), nxt))

    raise RuntimeError("No path found")


def sparsify_path(occ: np.ndarray, path: list[tuple[int, int]], res: float, max_segment_m: float) -> list[tuple[int, int]]:
    if len(path) <= 2:
        return path
    max_cells = int(math.floor(max_segment_m / res))
    out = [path[0]]
    i = 0
    while i < len(path) - 1:
        best = i + 1
        for j in range(i + 1, len(path)):
            if math.hypot(path[j][0] - path[i][0], path[j][1] - path[i][1]) > max_cells:
                break
            if line_is_free(occ, path[i], path[j]):
                best = j
            else:
                break
        out.append(path[best])
        i = best
    return out


def yaw_quat_from_to(a_xy: tuple[float, float], b_xy: tuple[float, float]) -> tuple[float, float, float, float]:
    yaw = math.atan2(b_xy[1] - a_xy[1], b_xy[0] - a_xy[0])
    return 0.0, 0.0, math.sin(yaw * 0.5), math.cos(yaw * 0.5)


def inflate_dynamic_obstacles(
    static_occ: np.ndarray,
    origin: np.ndarray,
    res: float,
    obstacles: list[DynObstacle],
    extra_margin: float,
) -> np.ndarray:
    occ = static_occ.copy()
    h, w = occ.shape
    for obs in obstacles:
        cells = int(math.ceil((obs.r + extra_margin) / res))
        cx, cy = world_to_grid(obs.x, obs.y, origin, res)
        y0, y1 = max(0, cy - cells), min(h - 1, cy + cells)
        x0, x1 = max(0, cx - cells), min(w - 1, cx + cells)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= cells * cells:
                    occ[yy, xx] = 1
    return occ


def remaining_path_blocked(occ: np.ndarray, path: list[tuple[int, int]], from_idx: int) -> bool:
    if from_idx >= len(path) - 1:
        return False
    for i in range(from_idx, len(path) - 1):
        if not line_is_free(occ, path[i], path[i + 1]):
            return True
    return False


def nearest_path_index(path: list[tuple[int, int]], cur: tuple[int, int]) -> int:
    best_i = 0
    best_d = float("inf")
    for i, p in enumerate(path):
        d = (p[0] - cur[0]) ** 2 + (p[1] - cur[1]) ** 2
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def compose_waypoint_json(
    map_path: str,
    start_xy: tuple[float, float],
    goal_xy: tuple[float, float],
    goal_yaw: float,
    max_segment: float,
    sparse_grid: list[tuple[int, int]],
    origin: np.ndarray,
    res: float,
    replan_events: list[dict],
) -> dict:
    world_pts = [grid_to_world(px, py, origin, res) for px, py in sparse_grid]
    waypoints = []
    for i, (x, y) in enumerate(world_pts):
        if i < len(world_pts) - 1:
            qx, qy, qz, qw = yaw_quat_from_to((x, y), world_pts[i + 1])
        else:
            qx, qy, qz, qw = 0.0, 0.0, math.sin(goal_yaw * 0.5), math.cos(goal_yaw * 0.5)
        waypoints.append({
            "index": i,
            "x": x,
            "y": y,
            "z": 0.0,
            "qx": qx,
            "qy": qy,
            "qz": qz,
            "qw": qw,
        })

    return {
        "map": str(Path(map_path).resolve()),
        "start": {"x": start_xy[0], "y": start_xy[1]},
        "goal": {"x": goal_xy[0], "y": goal_xy[1], "yaw": goal_yaw},
        "max_segment": max_segment,
        "num_waypoints": len(waypoints),
        "num_replans": len(replan_events),
        "replan_events": replan_events,
        "waypoints": waypoints,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dynamic event-triggered replan")
    parser.add_argument("--map", required=True, help="Input .npz map")
    parser.add_argument("--start", nargs=2, type=float, required=True, metavar=("X", "Y"))
    parser.add_argument("--goal", nargs=2, type=float, required=True, metavar=("X", "Y"))
    parser.add_argument("--goal-yaw", type=float, default=0.0)
    parser.add_argument("--max-segment", type=float, default=10.0)
    parser.add_argument("--obstacles-json", required=True, help="Dynamic obstacles frames JSON")
    parser.add_argument("--dyn-margin", type=float, default=0.10, help="Extra dynamic obstacle safety margin (m)")
    parser.add_argument("--cooldown", type=float, default=1.0, help="Min time between replans (s)")
    parser.add_argument("--confirm-frames", type=int, default=3, help="Consecutive blocked frames before replan")
    parser.add_argument("--output", required=True, help="Output JSON")
    args = parser.parse_args()

    data = np.load(args.map)
    static_occ = data["occupancy"].astype(np.uint8)
    origin = data["origin"].astype(np.float64)
    res = float(data["resolution"][0])

    start = world_to_grid(args.start[0], args.start[1], origin, res)
    goal = world_to_grid(args.goal[0], args.goal[1], origin, res)

    dense = astar(static_occ, start, goal)
    sparse = sparsify_path(static_occ, dense, res, args.max_segment)

    obs_obj = json.loads(Path(args.obstacles_json).read_text(encoding="utf-8"))
    frames = obs_obj.get("frames", [])

    blocked_count = 0
    last_replan_t = -1e9
    replan_events: list[dict] = []

    # Simulated progression: robot follows sparse path index over time.
    cur_idx = 0

    for frame in frames:
        t = float(frame.get("t", 0.0))
        obstacles = [DynObstacle(float(o["x"]), float(o["y"]), float(o.get("r", 0.3))) for o in frame.get("obstacles", [])]

        dyn_occ = inflate_dynamic_obstacles(static_occ, origin, res, obstacles, args.dyn_margin)

        # Update nearest progress index to avoid replanning from stale index.
        cur_idx = min(cur_idx, len(sparse) - 1)
        cur_idx = nearest_path_index(sparse, sparse[cur_idx])

        blocked = remaining_path_blocked(dyn_occ, sparse, cur_idx)
        blocked_count = blocked_count + 1 if blocked else 0

        should_replan = (
            blocked_count >= args.confirm_frames
            and (t - last_replan_t) >= args.cooldown
            and cur_idx < len(sparse) - 1
        )

        if should_replan:
            repl_start = sparse[cur_idx]
            dense_new = astar(dyn_occ, repl_start, goal)
            sparse_new = sparsify_path(dyn_occ, dense_new, res, args.max_segment)

            # splice: keep traveled prefix, replace remaining path
            prefix = sparse[:cur_idx]
            if not prefix or prefix[-1] != sparse_new[0]:
                sparse = prefix + sparse_new
            else:
                sparse = prefix + sparse_new[1:]

            replan_events.append({
                "t": t,
                "trigger_idx": cur_idx,
                "remaining_waypoints_after_replan": len(sparse) - cur_idx,
                "num_dyn_obstacles": len(obstacles),
            })
            last_replan_t = t
            blocked_count = 0

        # simple simulated movement: advance one waypoint if line is free
        if cur_idx < len(sparse) - 1 and line_is_free(dyn_occ, sparse[cur_idx], sparse[cur_idx + 1]):
            cur_idx += 1

    result = compose_waypoint_json(
        map_path=args.map,
        start_xy=(args.start[0], args.start[1]),
        goal_xy=(args.goal[0], args.goal[1]),
        goal_yaw=args.goal_yaw,
        max_segment=args.max_segment,
        sparse_grid=sparse,
        origin=origin,
        res=res,
        replan_events=replan_events,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Dynamic planning finished:", out)
    print("Final waypoints:", result["num_waypoints"], "Replans:", result["num_replans"])


if __name__ == "__main__":
    main()
