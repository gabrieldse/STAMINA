"""Cached regional windows from NASA Moon Trek's global LOLA elevation service."""
from functools import lru_cache
from math import cos, radians
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import rasterio
from rasterio.io import MemoryFile

from backend.horizon import RADIUS, basis, sector_angles

SERVICE = (
    "https://trek.nasa.gov/moon/trekarcgis/rest/services/"
    "LRO_LOLA_DEM_Global_256ppd_v06/ImageServer/exportImage"
)
PATCH_DEGREES = 18.0
TARGET_CELL_M = 400.0
HORIZON_DISTANCE_M = 400_000.0
MAX_SIDE = 4096
TIMEOUT_SECONDS = 120


def _wrapped_longitude(longitude):
    return ((longitude + 180.0) % 360.0) - 180.0


@lru_cache(maxsize=2)
def _regional_dem(latitude_key, longitude_key):
    """Fetch and cache a ~400 m LOLA region, allowing longitude wrap at ±180°."""
    latitude, longitude = latitude_key, longitude_key
    lat_min = max(-90.0, latitude - PATCH_DEGREES)
    lat_max = min(90.0, latitude + PATCH_DEGREES)
    cosine = max(0.05, cos(radians(latitude)))
    lon_half = min(180.0, PATCH_DEGREES / cosine)
    if lon_half >= 180.0:
        lon_min, lon_max, patch_longitude = -180.0, 180.0, 0.0
    else:
        lon_min, lon_max, patch_longitude = longitude - lon_half, longitude + lon_half, longitude

    # Keep the pixel size close to the map's ~400 m cells. Clamp to the
    # ImageServer's 4,100-pixel side limit for polar and high-latitude windows.
    farthest_latitude = min(89.9, max(0.0, abs(latitude) - PATCH_DEGREES))
    width_m = 2.0 * RADIUS * radians(lon_half) * cos(radians(farthest_latitude))
    height_m = RADIUS * radians(lat_max - lat_min)
    width = min(MAX_SIDE, max(256, int(np.ceil(width_m / TARGET_CELL_M))))
    height = min(MAX_SIDE, max(256, int(np.ceil(height_m / TARGET_CELL_M))))
    params = urlencode({
        "bbox": f"{lon_min:.8f},{lat_min:.8f},{lon_max:.8f},{lat_max:.8f}",
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "F32",
        "noData": "-9999",
        "compression": "LZ77",
        "f": "image",
    })
    try:
        with urlopen(f"{SERVICE}?{params}", timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            payload = response.read()
        if "tiff" not in content_type.lower() and "octet-stream" not in content_type.lower():
            raise ValueError("NASA LOLA service returned an error instead of a terrain raster.")
        with MemoryFile(payload) as memory_file:
            with memory_file.open() as dataset:
                heights = dataset.read(1, masked=True).filled(np.nan).astype(np.float32)
                transform = dataset.transform
                if heights.size == 0 or not np.isfinite(heights).any():
                    raise ValueError("NASA LOLA terrain window contains no elevation data.")
    except Exception as cause:
        raise ValueError(f"Global LOLA terrain unavailable: {cause}") from cause
    return heights, transform, patch_longitude


def regional_dem(center):
    latitude, longitude = center
    # Two-degree cache cells let nearby sites reuse the same NASA export.
    latitude_key = float(np.clip(round(latitude / 2.0) * 2.0, -90.0, 90.0))
    longitude_key = float(_wrapped_longitude(round(longitude / 2.0) * 2.0))
    return _regional_dem(latitude_key, longitude_key)


def sample_global(points, center):
    heights, transform, patch_longitude = regional_dem(center)
    radius = np.linalg.norm(points, axis=-1)
    latitude = np.degrees(np.arcsin(np.clip(points[:, 2] / radius, -1.0, 1.0)))
    longitude = np.degrees(np.arctan2(points[:, 1], points[:, 0]))
    delta = (longitude - patch_longitude + 180.0) % 360.0 - 180.0
    unwrapped_longitude = patch_longitude + delta
    col = np.floor((unwrapped_longitude - transform.c) / transform.a).astype(int)
    row = np.floor((latitude - transform.f) / transform.e).astype(int)
    inside = (row >= 0) & (row < heights.shape[0]) & (col >= 0) & (col < heights.shape[1])
    values = np.full(len(points), np.nan, dtype=np.float32)
    values[inside] = heights[row[inside], col[inside]]
    return values


@lru_cache(maxsize=128)
def global_profile(latitude, longitude):
    """Return a 0.5-degree LOLA skyline from a global DEM window."""
    up, east, north = basis(latitude, longitude)
    observer_height = sample_global((RADIUS * up)[None, :], (latitude, longitude))[0]
    if not np.isfinite(observer_height):
        raise ValueError("No global LOLA elevation at this site.")
    observer = (RADIUS + observer_height) * up

    # The Moon's curvature hides terrain beyond this radius even for the
    # highest regional relief; the larger regional patch keeps map-edge rays covered.
    distances = np.arange(TARGET_CELL_M, HORIZON_DISTANCE_M + 1.0, TARGET_CELL_M)
    azimuths = np.arange(720) * (2 * np.pi / 720)
    distance_grid, azimuth_grid = np.meshgrid(distances, azimuths)
    x = distance_grid.ravel() * np.sin(azimuth_grid.ravel())
    y = distance_grid.ravel() * np.cos(azimuth_grid.ravel())
    q = (x*x + y*y) / (4 * RADIUS * RADIUS)
    lat0, lon0 = np.radians([latitude, longitude])
    center = np.array([np.cos(lat0)*np.cos(lon0), np.cos(lat0)*np.sin(lon0), np.sin(lat0)])
    local_east = np.array([-np.sin(lon0), np.cos(lon0), 0.0])
    local_north = np.cross(center, local_east)
    normals = ((1-q)[:, None]*center + (x/RADIUS)[:, None]*local_east + (y/RADIUS)[:, None]*local_north)/(1+q)[:, None]
    heights = sample_global(RADIUS * normals, (latitude, longitude))
    radii = RADIUS + heights
    points = radii[:, None] * normals
    delta = points - observer
    valid = np.isfinite(heights) & (np.linalg.norm(delta, axis=1) > 120.0)
    sectors, angles = sector_angles(delta[valid], up, east, north)
    skyline = np.full(720, -np.pi/2)
    np.maximum.at(skyline, sectors, angles)
    if np.any(skyline == -np.pi/2):
        raise ValueError("Incomplete global LOLA horizon coverage at this site.")
    return observer, skyline
