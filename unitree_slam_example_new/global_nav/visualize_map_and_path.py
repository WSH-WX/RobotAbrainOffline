#!/usr/bin/env python3
"""
Visualize occupancy map (.npz) and optional planned path (.json).

Usage:
  python3 visualize_map_and_path.py \
    --map /mnt/disk1/unitree_slam_example/global_nav/map_data.npz \
    --path /mnt/disk1/unitree_slam_example/global_nav/path_waypoints.json \
    --output /mnt/disk1/unitree_slam_example/global_nav/map_with_path.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def world_to_grid(x: float, y: float, origin: np.ndarray, res: float) -> tuple[float, float]:
    gx = (x - origin[0]) / res
    gy = (y - origin[1]) / res
    return gx, gy


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize occupancy map and optional path")
    parser.add_argument("--map", required=True, help="Input map .npz from build_grid_map.py")
    parser.add_argument("--path", default="", help="Optional path_waypoints.json")
    parser.add_argument("--output", default="", help="Optional output image path")
    parser.add_argument("--show", action="store_true", help="Show interactive window")
    args = parser.parse_args()

    data = np.load(args.map)
    occ = data["occupancy"].astype(np.uint8)
    origin = data["origin"].astype(np.float64)
    res = float(data["resolution"][0])

    fig, ax = plt.subplots(figsize=(10, 8))

    # Show map in grid coordinates. origin='lower' to keep y-up.
    ax.imshow(occ, cmap="gray_r", origin="lower")
    ax.set_title("Occupancy Grid (white=free, black=occupied)")
    ax.set_xlabel("Grid X")
    ax.set_ylabel("Grid Y")

    # Overlay path if provided.
    if args.path:
        path_obj = json.loads(Path(args.path).read_text(encoding="utf-8"))
        waypoints = path_obj.get("waypoints", [])
        if waypoints:
            xs, ys = [], []
            for wp in waypoints:
                gx, gy = world_to_grid(float(wp["x"]), float(wp["y"]), origin, res)
                xs.append(gx)
                ys.append(gy)

            ax.plot(xs, ys, "-o", color="deepskyblue", linewidth=2, markersize=4, label="planned path")
            ax.scatter(xs[0], ys[0], c="lime", s=80, marker="o", label="start")
            ax.scatter(xs[-1], ys[-1], c="red", s=80, marker="x", label="goal")

            # draw heading arrow for each waypoint
            for wp in waypoints:
                qz = float(wp.get("qz", 0.0))
                qw = float(wp.get("qw", 1.0))
                yaw = 2.0 * np.arctan2(qz, qw)
                gx, gy = world_to_grid(float(wp["x"]), float(wp["y"]), origin, res)
                ax.arrow(
                    gx,
                    gy,
                    0.8 * np.cos(yaw),
                    0.8 * np.sin(yaw),
                    head_width=0.4,
                    head_length=0.5,
                    fc="orange",
                    ec="orange",
                    alpha=0.8,
                    length_includes_head=True,
                )

            ax.legend(loc="upper right")

    ax.grid(alpha=0.2)
    fig.tight_layout()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200)
        print("Saved visualization:", output_path)

    if args.show or not args.output:
        plt.show()


if __name__ == "__main__":
    main()
