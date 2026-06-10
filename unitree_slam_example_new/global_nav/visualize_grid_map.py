#!/usr/bin/env python3
"""
Visualize occupancy grid map (from .npz or cpp .txt format) and optional waypoint path.

Examples:
  python3 visualize_grid_map.py \
    --map /mnt/disk1/unitree_slam_example/global_nav/map_data_cpp.txt

  python3 visualize_grid_map.py \
    --map /mnt/disk1/unitree_slam_example/global_nav/map_data.npz \
    --path /mnt/disk1/unitree_slam_example/global_nav/path_waypoints.json \
    --save /mnt/disk1/unitree_slam_example/global_nav/map_with_path.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch


def load_npz_map(map_path: Path) -> tuple[np.ndarray, np.ndarray, float]:
    data = np.load(map_path)
    occ = data["occupancy"].astype(np.uint8)
    origin = data["origin"].astype(np.float64)
    resolution = float(data["resolution"][0])
    return occ, origin, resolution


def load_cpp_txt_map(map_path: Path) -> tuple[np.ndarray, np.ndarray, float]:
    lines = map_path.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < 3:
        raise ValueError("Invalid map txt file")

    width, height = map(int, lines[0].split())
    origin_x, origin_y, resolution = map(float, lines[1].split())

    grid_lines = lines[2:]
    if len(grid_lines) != height:
        raise ValueError(f"Row count mismatch: expected {height}, got {len(grid_lines)}")

    occ = np.zeros((height, width), dtype=np.uint8)
    for y, row in enumerate(grid_lines):
        if len(row.strip()) != width:
            raise ValueError(f"Column count mismatch at row {y}")
        occ[y, :] = np.fromiter((1 if c == "1" else 0 for c in row.strip()), dtype=np.uint8, count=width)

    return occ, np.array([origin_x, origin_y], dtype=np.float64), resolution


def load_waypoints(path_file: Path) -> np.ndarray:
    obj = json.loads(path_file.read_text(encoding="utf-8"))
    if "waypoints" not in obj:
        raise ValueError("Invalid waypoint json: missing 'waypoints'")
    xy = [(float(w["x"]), float(w["y"])) for w in obj["waypoints"]]
    return np.asarray(xy, dtype=np.float64)


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize occupancy grid and optional path")
    parser.add_argument("--map", required=True, help="Input map (.npz or cpp .txt)")
    parser.add_argument("--path", default="", help="Optional waypoint json path")
    parser.add_argument("--save", default="", help="Optional output png path")
    parser.add_argument("--coord-step", type=int, default=0, help="Annotate every Nth waypoint with (x,y). 0 disables")
    args = parser.parse_args()

    map_path = Path(args.map)
    suffix = map_path.suffix.lower()

    if suffix == ".npz":
        occ, origin, res = load_npz_map(map_path)
    elif suffix == ".txt":
        occ, origin, res = load_cpp_txt_map(map_path)
    else:
        raise ValueError("Unsupported map format, use .npz or .txt")

    h, w = occ.shape
    extent = [origin[0], origin[0] + w * res, origin[1], origin[1] + h * res]

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.imshow(occ, cmap="gray_r", origin="lower", extent=extent, interpolation="nearest")

    # Draw map origin and coordinate grid for easy coordinate reading.
    ax.scatter(origin[0], origin[1], c="yellow", s=80, marker="x", linewidths=2, label="map origin")
    ax.text(origin[0], origin[1], f"  map_origin=({origin[0]:.2f}, {origin[1]:.2f})", color="yellow", fontsize=9)

    # Add world origin marker (0,0).
    ax.scatter(0.0, 0.0, c="magenta", s=70, marker="+", linewidths=2, label="world origin (0,0)")
    ax.text(0.0, 0.0, "  world_origin=(0.00, 0.00)", color="magenta", fontsize=9)

    # Draw world coordinate triad (X, Y in-plane; Z as out-of-plane marker).
    axis_len = max((extent[1] - extent[0]), (extent[3] - extent[2])) * 0.12
    x_arrow = FancyArrowPatch((0.0, 0.0), (axis_len, 0.0), arrowstyle="->", mutation_scale=14, linewidth=2.2, color="#ff3b30")
    y_arrow = FancyArrowPatch((0.0, 0.0), (0.0, axis_len), arrowstyle="->", mutation_scale=14, linewidth=2.2, color="#34c759")
    ax.add_patch(x_arrow)
    ax.add_patch(y_arrow)
    ax.text(axis_len, 0.0, "  X", color="#ff3b30", fontsize=11, fontweight="bold", va="center")
    ax.text(0.0, axis_len, "  Y", color="#34c759", fontsize=11, fontweight="bold", va="bottom")

    # Z axis is perpendicular to map plane; show with circled dot symbol.
    zx, zy = axis_len * 0.10, axis_len * 0.10
    ax.scatter(zx, zy, s=90, facecolors="none", edgecolors="#0a84ff", linewidths=2.0, zorder=5)
    ax.scatter(zx, zy, s=18, c="#0a84ff", zorder=6)
    ax.text(zx, zy, "  Z", color="#0a84ff", fontsize=11, fontweight="bold", va="center")

    major = max(1.0, round((w * res) / 10.0, 1))
    ax.set_xticks(np.arange(extent[0], extent[1] + 1e-6, major))
    ax.set_yticks(np.arange(extent[2], extent[3] + 1e-6, major))
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)

    if args.path:
        pts = load_waypoints(Path(args.path))
        if len(pts) > 0:
            ax.plot(pts[:, 0], pts[:, 1], "-o", color="tab:red", linewidth=2, markersize=4, label="planned path")
            ax.scatter(pts[0, 0], pts[0, 1], c="tab:green", s=60, label="start")
            ax.scatter(pts[-1, 0], pts[-1, 1], c="tab:blue", s=60, label="goal")

            if args.coord_step > 0:
                for i, (x, y) in enumerate(pts):
                    if i % args.coord_step == 0 or i == len(pts) - 1:
                        ax.text(x, y, f"({x:.2f}, {y:.2f})", fontsize=8, color="cyan")

    ax.legend(loc="best")

    ax.set_title("2D Occupancy Grid")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_aspect("equal")

    if args.save:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=180, bbox_inches="tight")
        print(f"Saved figure: {out}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
