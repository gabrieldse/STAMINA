"""Experimental, flat-terrain Solshade preview for the lunar south pole."""

import argparse
import math
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import rasterio
import rioxarray
import spiceypy as sp
import xarray as xr
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from scipy.ndimage import map_coordinates
from solshade.terrain import compute_horizon_map

from Filters.Sunlight.illumination import MOON_RADIUS_KM, sme


RADIUS_M = MOON_RADIUS_KM * 1000
POLAR_CRS = CRS.from_proj4(
    "+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m +no_defs"
)


def load_polar_terrain(source_path, resolution_m, search_distance_m):
    """Reproject the LOLA 75S FLOAT product, in kilometers, to a buffered grid."""
    cap_radius = 2 * RADIUS_M * math.tan(math.radians(10) / 2)
    cap_pixels = math.ceil(cap_radius / resolution_m)
    buffer_pixels = math.ceil(search_distance_m / resolution_m)
    half_size = cap_pixels + buffer_pixels
    size = 2 * half_size
    transform = from_origin(-half_size * resolution_m, half_size * resolution_m,
                            resolution_m, resolution_m)
    terrain = np.full((size, size), np.nan, dtype=np.float32)
    with rasterio.open(source_path) as source:
        if source.crs is None:
            raise ValueError("The polar DEM must have a coordinate reference system")
        reproject(
            source=rasterio.band(source, 1), destination=terrain,
            src_transform=source.transform, src_crs=source.crs,
            src_nodata=source.nodata, dst_transform=transform,
            dst_crs=POLAR_CRS, dst_nodata=np.nan, resampling=Resampling.average,
        )
    terrain *= 1000  # The LOLA FLOAT product stores elevations in kilometers.
    x = transform.c + (np.arange(size) + 0.5) * resolution_m
    y = transform.f - (np.arange(size) + 0.5) * resolution_m
    dem = xr.DataArray(terrain, dims=("y", "x"), coords={"y": y, "x": x})
    dem.rio.write_crs(POLAR_CRS, inplace=True)
    dem.rio.write_transform(transform, inplace=True)
    return dem, cap_pixels, buffer_pixels


def polar_sun_angles(dem, sun_km):
    """Return local solar elevation and Solshade grid angle for every pixel."""
    x, y = np.meshgrid(dem.x.values, dem.y.values)
    lon = np.arctan2(x, y)
    lat = -np.pi / 2 + 2 * np.arctan(np.hypot(x, y) / (2 * RADIUS_M))
    cos_lat, sin_lat = np.cos(lat), np.sin(lat)
    cos_lon, sin_lon = np.cos(lon), np.sin(lon)
    radius_km = (RADIUS_M + dem.values) / 1000
    sx = sun_km[0] - radius_km * cos_lat * cos_lon
    sy = sun_km[1] - radius_km * cos_lat * sin_lon
    sz = sun_km[2] - radius_km * sin_lat
    east = -sx * sin_lon + sy * cos_lon
    north = -sx * sin_lat * cos_lon - sy * sin_lat * sin_lon + sz * cos_lat
    up = sx * cos_lat * cos_lon + sy * cos_lat * sin_lon + sz * sin_lat
    elevation = np.degrees(np.arctan2(up, np.hypot(east, north)))
    # Solshade's horizon samples use 0 = grid east, 90 = grid north.
    grid_east = east * cos_lon + north * sin_lon
    grid_north = -east * sin_lon + north * cos_lon
    angle = np.degrees(np.arctan2(grid_north, grid_east)) % 360
    return elevation, angle


def complete_ray_coverage(terrain, direction_index, directions, step_pixels, steps):
    """Find pixels whose selected sampled ray stays in valid terrain."""
    rows, cols = np.indices(terrain.shape)
    angle = np.radians(direction_index * (360 / directions))
    valid = np.isfinite(terrain)
    valid_samples = valid.astype(np.float32)
    complete = valid.copy()
    for step in range(1, steps + 1):
        distance = step * step_pixels
        sample_rows = rows - np.sin(angle) * distance
        sample_cols = cols + np.cos(angle) * distance
        coverage = map_coordinates(
            valid_samples, [sample_rows, sample_cols],
            order=1, mode="constant", cval=0,
        )
        complete &= coverage >= 1 - 1e-6
    return complete


def create_preview(source_path, et, output_dir, *, resolution_m=2000,
                   search_distance_m=120000, directions=36):
    """Save an approximate polar-cap overlay and matching elevation base image.

    source_path: LOLA LDEM_75S_240M_FLOAT label or image, elevations in km.
    et: SPICE ephemeris time; output_dir: directory for generated PNGs.
    resolution_m: output pixel spacing in meters; search_distance_m: how far
        each horizon ray searches; directions: number of horizon directions.

    Results are approximate and limited to the search distance. This uses a
    flat projected grid, ignores lunar curvature and does not model the Sun's
    disk. Missing or incomplete terrain is gray-blue, not classified as clear.
    """
    if (not math.isfinite(resolution_m) or not math.isfinite(search_distance_m)
            or resolution_m <= 0 or search_distance_m <= 0 or directions < 4):
        raise ValueError("Resolution and search distance must be finite and positive; use at least 4 directions")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dem, cap_pixels, buffer_pixels = load_polar_terrain(
        source_path, resolution_m, search_distance_m,
    )
    steps = math.ceil(search_distance_m / resolution_m)
    effective_distance = steps * resolution_m
    print(f"Calculating {directions} horizons on a {dem.shape[1]} x {dem.shape[0]} grid...")
    horizons = compute_horizon_map(
        dem, n_directions=directions, max_distance=effective_distance,
        step=resolution_m, chunk_size=8, n_jobs=1, progress=True,
    )
    sun_km, _ = sme.get_sun_vec(et)
    elevation, angle = polar_sun_angles(dem, sun_km)
    direction_index = np.zeros(dem.shape, dtype=np.int64)
    finite_angle = np.isfinite(angle)
    direction_index[finite_angle] = (
        np.floor(angle[finite_angle] / (360 / directions) + 0.5).astype(np.int64)
        % directions
    )
    rows, cols = np.indices(dem.shape)
    selected_horizon = horizons.values[direction_index, rows, cols]
    complete = complete_ray_coverage(dem.values, direction_index, directions, 1, steps)

    selection = slice(buffer_pixels, buffer_pixels + 2 * cap_pixels)
    x, y = np.meshgrid(dem.x.values[selection], dem.y.values[selection])
    in_cap = np.hypot(x, y) <= 2 * RADIUS_M * math.tan(math.radians(10) / 2)
    terrain = dem.values[selection, selection]
    elevation = elevation[selection, selection]
    selected_horizon = selected_horizon[selection, selection]
    complete = complete[selection, selection]
    known = in_cap & complete & np.isfinite(elevation) & np.isfinite(selected_horizon)
    visible = known & (elevation >= selected_horizon)
    unknown = in_cap & ~known

    overlay = np.zeros((*terrain.shape, 4), dtype=np.uint8)
    overlay[visible] = (255, 220, 0, 160)
    overlay[unknown] = (100, 130, 160, 160)
    base = np.zeros((*terrain.shape, 4), dtype=np.uint8)
    valid = in_cap & np.isfinite(terrain)
    if not np.any(valid):
        raise ValueError("The source DEM has no valid data in the south-polar cap")
    low, high = np.percentile(terrain[valid], (2, 98))
    if high <= low:
        high = low + 1
    shade = np.zeros(terrain.shape, dtype=np.uint8)
    shade[valid] = (np.clip((terrain[valid] - low) / (high - low), 0, 1) * 255).astype(np.uint8)
    base[valid, :3] = shade[valid, None]
    base[valid, 3] = 255
    base_path = output_dir / "polar_base.png"
    overlay_path = output_dir / "polar_illumination.png"
    preview_path = output_dir / "polar_preview.png"
    mpimg.imsave(base_path, base)
    mpimg.imsave(overlay_path, overlay)
    # Compose a preview while preserving the separately reusable overlay.
    preview = overlay.copy()
    alpha = overlay[valid, 3:4].astype(np.float32) / 255
    preview[valid, :3] = (
        overlay[valid, :3] * alpha + base[valid, :3] * (1 - alpha)
    ).astype(np.uint8)
    preview[valid, 3] = 255
    mpimg.imsave(preview_path, preview)
    print(f"Approximate visible: {np.count_nonzero(visible)}; "
          f"blocked: {np.count_nonzero(known & ~visible)}; "
          f"unknown: {np.count_nonzero(unknown)}")
    print(f"Base: {base_path}\nOverlay: {overlay_path}\nPreview: {preview_path}")
    return base_path, overlay_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="LOLA LDEM_75S_240M_FLOAT .LBL path")
    parser.add_argument("output_dir", help="Directory for base and overlay PNGs")
    parser.add_argument("--utc", default="2026-11-14T12:00:00",
                        help="UTC time, e.g. 2026-11-14T12:00:00")
    parser.add_argument("--resolution-m", type=float, default=2000)
    parser.add_argument("--search-distance-m", type=float, default=120000)
    parser.add_argument("--directions", type=int, default=36)
    args = parser.parse_args()
    create_preview(args.source, sp.str2et(args.utc), args.output_dir,
                   resolution_m=args.resolution_m,
                   search_distance_m=args.search_distance_m,
                   directions=args.directions)


if __name__ == "__main__":
    main()
