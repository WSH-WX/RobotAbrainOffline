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
import logging
from pathlib import Path

import numpy as np

try:
    import open3d as o3d
except Exception as exc:  # pragma: no cover
    o3d = None
    OPEN3D_IMPORT_ERROR = exc
else:
    OPEN3D_IMPORT_ERROR = None


LOGGER = logging.getLogger("build_grid_map")
GROUND_CELL_SIZE_M = 0.20
GROUND_MIN_CELL_POINTS = 2
GROUND_HIST_BIN_SIZE_M = 0.05


def _pcd_numpy_dtype(type_name: str, size: int) -> str:
    if type_name == "F":
        return {4: "<f4", 8: "<f8"}[size]
    if type_name == "I":
        return {1: "<i1", 2: "<i2", 4: "<i4", 8: "<i8"}[size]
    if type_name == "U":
        return {1: "<u1", 2: "<u2", 4: "<u4", 8: "<u8"}[size]
    raise ValueError(f"Unsupported PCD field type: {type_name}{size}")


def _read_pcd_header(file_obj) -> dict[str, object]:
    header: dict[str, object] = {}
    while True:
        raw_line = file_obj.readline()
        if not raw_line:
            raise ValueError("Invalid PCD file: missing DATA header")
        line = raw_line.decode("ascii", errors="strict").strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        key = parts[0].upper()
        values = parts[1:]
        if key == "FIELDS":
            header["fields"] = values
        elif key == "SIZE":
            header["sizes"] = [int(v) for v in values]
        elif key == "TYPE":
            header["types"] = values
        elif key == "COUNT":
            header["counts"] = [int(v) for v in values]
        elif key == "WIDTH":
            header["width"] = int(values[0])
        elif key == "HEIGHT":
            header["height"] = int(values[0])
        elif key == "POINTS":
            header["points"] = int(values[0])
        elif key == "DATA":
            header["data"] = values[0].lower()
            return header


def load_pcd_points(file_path: Path) -> np.ndarray:
    with file_path.open("rb") as file_obj:
        header = _read_pcd_header(file_obj)

        fields = header.get("fields")
        sizes = header.get("sizes")
        types = header.get("types")
        if not isinstance(fields, list) or not isinstance(sizes, list) or not isinstance(types, list):
            raise ValueError(f"Invalid PCD header in: {file_path}")
        counts = header.get("counts")
        if not isinstance(counts, list):
            counts = [1] * len(fields)
        points = int(header.get("points") or int(header.get("width", 0)) * int(header.get("height", 1)))
        data_type = str(header.get("data", ""))

        if points <= 0:
            raise ValueError(f"No points declared in PCD: {file_path}")
        if not {"x", "y", "z"}.issubset(fields):
            raise ValueError(f"PCD must contain x/y/z fields: {file_path}")

        LOGGER.info("Loading PCD file path=%s points=%s data=%s", file_path, points, data_type)
        if data_type == "binary":
            dtype_fields = []
            offsets = []
            offset = 0
            for name, size, type_name, count in zip(fields, sizes, types, counts):
                dtype = _pcd_numpy_dtype(type_name, size)
                dtype_fields.append((name, dtype) if count == 1 else (name, dtype, (count,)))
                offsets.append(offset)
                offset += size * count
            dtype = np.dtype({"names": [item[0] for item in dtype_fields],
                              "formats": [item[1:] if len(item) > 2 else item[1] for item in dtype_fields],
                              "offsets": offsets,
                              "itemsize": offset})
            data = np.fromfile(file_obj, dtype=dtype, count=points)
            if data.shape[0] != points:
                raise ValueError(f"Unexpected EOF while reading PCD: {file_path}")
            return np.column_stack([data["x"], data["y"], data["z"]]).astype(np.float64)

        if data_type == "ascii":
            data = np.loadtxt(file_obj, dtype=np.float64, max_rows=points)
            if data.ndim == 1:
                data = data.reshape(1, -1)
            field_index = {name: idx for idx, name in enumerate(fields)}
            return data[:, [field_index["x"], field_index["y"], field_index["z"]]]

        raise ValueError(f"Unsupported PCD DATA type: {data_type}")


def load_points(file_path: Path) -> np.ndarray:
    if file_path.suffix.lower() == ".pcd":
        return load_pcd_points(file_path)

    if o3d is None:
        raise RuntimeError(
            "open3d is required for non-PCD point clouds. Install with: pip install open3d"
        ) from OPEN3D_IMPORT_ERROR

    LOGGER.info("Loading point cloud with open3d path=%s", file_path)
    pcd = o3d.io.read_point_cloud(str(file_path))
    pts = np.asarray(pcd.points, dtype=np.float64)
    if pts.size == 0:
        raise ValueError(f"No points loaded from: {file_path}")
    return pts


def estimate_ground_z(points_xyz: np.ndarray) -> float:
    finite = np.all(np.isfinite(points_xyz), axis=1)
    pts = points_xyz[finite]
    if pts.size == 0:
        raise ValueError("Cannot estimate ground height from empty point cloud")

    min_x = float(np.min(pts[:, 0]))
    min_y = float(np.min(pts[:, 1]))
    gx = np.floor((pts[:, 0] - min_x) / GROUND_CELL_SIZE_M).astype(np.int64)
    gy = np.floor((pts[:, 1] - min_y) / GROUND_CELL_SIZE_M).astype(np.int64)
    key = gx + (int(np.max(gx)) + 1) * gy

    order = np.argsort(key, kind="mergesort")
    sorted_key = key[order]
    sorted_z = pts[:, 2][order]
    starts = np.r_[0, np.flatnonzero(sorted_key[1:] != sorted_key[:-1]) + 1]
    counts = np.diff(np.r_[starts, len(sorted_key)])
    cell_min_z = np.minimum.reduceat(sorted_z, starts)
    candidates = cell_min_z[counts >= GROUND_MIN_CELL_POINTS]
    if candidates.size == 0:
        candidates = cell_min_z
        LOGGER.info("Ground estimation fallback: using all lower-envelope cells")

    lo, hi = np.percentile(candidates, [1, 99])
    trimmed = candidates[(candidates >= lo) & (candidates <= hi)]
    if trimmed.size == 0:
        trimmed = candidates

    bin_start = np.floor(float(np.min(trimmed)) / GROUND_HIST_BIN_SIZE_M) * GROUND_HIST_BIN_SIZE_M
    bin_stop = np.ceil(float(np.max(trimmed)) / GROUND_HIST_BIN_SIZE_M) * GROUND_HIST_BIN_SIZE_M
    bins = np.arange(bin_start, bin_stop + GROUND_HIST_BIN_SIZE_M * 2, GROUND_HIST_BIN_SIZE_M)
    hist, edges = np.histogram(trimmed, bins=bins)
    if hist.size == 0 or int(np.max(hist)) == 0:
        ground_z = float(np.median(trimmed))
        LOGGER.info("Ground estimation fallback: using median lower-envelope z=%s", ground_z)
        return ground_z

    best = int(np.argmax(hist))
    in_mode = trimmed[(trimmed >= edges[best]) & (trimmed < edges[best + 1])]
    ground_z = float(np.median(in_mode if in_mode.size else trimmed))
    LOGGER.info(
        "Estimated ground_z=%.4f from lower envelope cells=%s candidates=%s mode_bin=[%.2f, %.2f)",
        ground_z,
        cell_min_z.size,
        candidates.size,
        edges[best],
        edges[best + 1],
    )
    return ground_z


def build_occupancy(
    points_xyz: np.ndarray,
    resolution: float,
    z_min: float,
    z_max: float,
    inflation_radius: float,
) -> tuple[np.ndarray, float, float, float, float, float, float]:
    ground_z = estimate_ground_z(points_xyz)
    abs_z_min = ground_z + z_min
    abs_z_max = ground_z + z_max
    LOGGER.info(
        "Applying ground-relative height filter ground_z=%.4f relative_z=[%.3f, %.3f] absolute_z=[%.4f, %.4f]",
        ground_z,
        z_min,
        z_max,
        abs_z_min,
        abs_z_max,
    )

    mask = (points_xyz[:, 2] >= abs_z_min) & (points_xyz[:, 2] <= abs_z_max)
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

    return occ, min_x, min_y, resolution, ground_z, abs_z_min, abs_z_max


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build 2D occupancy grid from point cloud")
    parser.add_argument("--input", required=True, help="Input .pcd/.ply map")
    parser.add_argument("--output", required=True, help="Output .npz map file")
    parser.add_argument("--resolution", type=float, default=0.10, help="Grid resolution in meters")
    parser.add_argument("--z-min", type=float, default=-0.20, help="Min height above estimated ground for obstacle extraction")
    parser.add_argument("--z-max", type=float, default=1.50, help="Max height above estimated ground for obstacle extraction")
    parser.add_argument(
        "--inflation-radius",
        type=float,
        default=0.45,
        help="Obstacle inflation radius in meters (G1 recommended: 0.45)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    LOGGER.info(
        "Build occupancy map input=%s output=%s resolution=%s relative_z_min=%s relative_z_max=%s inflation_radius=%s",
        input_path,
        output_path,
        args.resolution,
        args.z_min,
        args.z_max,
        args.inflation_radius,
    )

    points = load_points(input_path)
    occ, origin_x, origin_y, resolution, ground_z, abs_z_min, abs_z_max = build_occupancy(
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
        ground_z=np.array([ground_z], dtype=np.float64),
        z_filter_absolute=np.array([abs_z_min, abs_z_max], dtype=np.float64),
        z_filter_relative=np.array([args.z_min, args.z_max], dtype=np.float64),
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
    print("Estimated ground z:", ground_z)
    print("Absolute z filter:", (abs_z_min, abs_z_max))


if __name__ == "__main__":
    main()
