#!/usr/bin/env python3
"""
Build a 2D occupancy grid from a .pcd/.ply point cloud map.

Usage:
  python3 build_grid_map.py \
    --input /mnt/disk1/unitree_slam_example/global_maps/global_map_20260330_155423.pcd \
    --output /mnt/disk1/unitree_slam_example/global_nav/map_data.npz
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

try:
    import open3d as o3d
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "open3d is required. Install with: pip install open3d"
    ) from exc


def load_points(file_path: Path) -> np.ndarray:
    pcd = o3d.io.read_point_cloud(str(file_path))
    pts = np.asarray(pcd.points, dtype=np.float64)
    if pts.size == 0:
        raise ValueError(f"No points loaded from: {file_path}")
    return pts


def build_occupancy(
    points_xyz: np.ndarray,
    resolution: float,
    z_min: float,
    z_max: float,
    inflation_radius: float,
) -> tuple[np.ndarray, float, float, float]:
    # Height filter for near-ground obstacles / structure points.
    mask = (points_xyz[:, 2] >= z_min) & (points_xyz[:, 2] <= z_max)
    pts = points_xyz[mask]
    if pts.size == 0:
        raise ValueError(
            "No points left after z filtering. Relax --z-min/--z-max."
        )

    min_x = float(np.min(pts[:, 0]))
    max_x = float(np.max(pts[:, 0]))
    min_y = float(np.min(pts[:, 1]))
    max_y = float(np.max(pts[:, 1]))

    width = int(np.ceil((max_x - min_x) / resolution)) + 1
    height = int(np.ceil((max_y - min_y) / resolution)) + 1

    occ = np.zeros((height, width), dtype=np.uint8)

    gx = np.floor((pts[:, 0] - min_x) / resolution).astype(np.int32)
    gy = np.floor((pts[:, 1] - min_y) / resolution).astype(np.int32)

    valid = (gx >= 0) & (gx < width) & (gy >= 0) & (gy < height)
    gx = gx[valid]
    gy = gy[valid]
    occ[gy, gx] = 1

    # Inflate obstacles by robot radius + safety margin.
    inflate_cells = int(np.ceil(inflation_radius / resolution))
    if inflate_cells > 0:
        inflated = occ.copy()
        occupied_y, occupied_x = np.where(occ == 1)
        for cy, cx in zip(occupied_y, occupied_x):
            y0 = max(0, cy - inflate_cells)
            y1 = min(height, cy + inflate_cells + 1)
            x0 = max(0, cx - inflate_cells)
            x1 = min(width, cx + inflate_cells + 1)

            yy, xx = np.ogrid[y0:y1, x0:x1]
            circle = (yy - cy) ** 2 + (xx - cx) ** 2 <= inflate_cells**2
            inflated[y0:y1, x0:x1][circle] = 1
        occ = inflated

    return occ, min_x, min_y, resolution


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 2D occupancy grid from point cloud")
    parser.add_argument("--input", required=True, help="Input .pcd/.ply map")
    parser.add_argument("--output", required=True, help="Output .npz map file")
    parser.add_argument("--resolution", type=float, default=0.10, help="Grid resolution in meters")
    parser.add_argument("--z-min", type=float, default=-0.20, help="Min z for obstacle extraction")
    parser.add_argument("--z-max", type=float, default=1.50, help="Max z for obstacle extraction")
    parser.add_argument(
        "--inflation-radius",
        type=float,
        default=0.45,
        help="Obstacle inflation radius in meters (G1 recommended: 0.45)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    points = load_points(input_path)
    occ, origin_x, origin_y, resolution = build_occupancy(
        points,
        resolution=args.resolution,
        z_min=args.z_min,
        z_max=args.z_max,
        inflation_radius=args.inflation_radius,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        occupancy=occ,
        origin=np.array([origin_x, origin_y], dtype=np.float64),
        resolution=np.array([resolution], dtype=np.float64),
    )

    # Also dump a quick debug image (0=free, 255=occupied).
    try:
        from PIL import Image

        img = (occ * 255).astype(np.uint8)
        Image.fromarray(np.flipud(img), mode="L").save(output_path.with_suffix(".png"))
    except Exception:
        pass

    print("Map saved:", output_path)
    print("Grid shape (h, w):", occ.shape)
    print("Origin (x, y):", (origin_x, origin_y))
    print("Resolution:", resolution)


if __name__ == "__main__":
    main()
