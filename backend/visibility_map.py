"""Instantaneous, sampled LOLA line-of-sight map (south polar stereographic)."""
from functools import lru_cache
from threading import Lock
from base64 import b64encode

import numpy as np
import rasterio

from backend.horizon import DEM, RADIUS
from backend.visibility_kernel import NUMBA_AVAILABLE, accelerated_trace

MAP_LOCK = Lock()
MAP_RADIUS = 2 * RADIUS * np.tan(np.radians(10) / 2)


@lru_cache(maxsize=1)
def terrain():
    if not DEM.exists():
        raise ValueError("LOLA 75S 240 m DEM unavailable.")
    with rasterio.open(DEM) as src:
        return src.read(1, masked=True).filled(np.nan), src.transform


def sample(points):
    heights, transform = terrain()
    radius = np.linalg.norm(points, axis=-1)
    x = 2*RADIUS*points[:, 1]/(radius-points[:, 2])
    y = 2*RADIUS*points[:, 0]/(radius-points[:, 2])
    col = np.floor((x-transform.c)/transform.a).astype(int)
    row = np.floor((y-transform.f)/transform.e).astype(int)
    inside = (row >= 0) & (row < heights.shape[0]) & (col >= 0) & (col < heights.shape[1])
    values = np.full(len(points), np.nan)
    values[inside] = heights[row[inside], col[inside]]
    return values


@lru_cache(maxsize=3)
def observers(size):
    coords = ((np.arange(size)+.5)/size*2-1)*MAP_RADIUS
    x, y = np.meshgrid(coords, -coords)
    valid = x*x+y*y <= MAP_RADIUS**2
    rho = np.hypot(x[valid], y[valid])
    lat = 2*np.arctan(rho/(2*RADIUS))-np.pi/2
    lon = np.arctan2(x[valid], y[valid])
    normals = np.stack([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)], axis=-1)
    heights = sample(normals*RADIUS)
    return valid, normals*(RADIUS+heights[:, None]), heights


def trace(observers_m, target_km):
    """Trace the target direction through terrain, with curvature and parallax.

    240 m ray steps resolve the DEM. Rays stop once beyond the DEM's maximum
    radius and moving outward; the rest cannot intersect the terrain sphere.
    Missing terrain is excluded, never treated as a visible surface.
    """
    target = np.array(target_km)*1000
    direction = target-observers_m
    direction /= np.linalg.norm(direction, axis=1)[:, None]
    visible = np.isfinite(observers_m).all(axis=1)
    active = np.flatnonzero(visible)
    ceiling = RADIUS + float(np.nanmax(terrain()[0])) + 1
    for distance in np.arange(240., 1_200_001., 240.):
        if not len(active):
            break
        points = observers_m[active]+distance*direction[active]
        radius = np.linalg.norm(points, axis=1)
        height = sample(points)
        escaped = (radius > ceiling) & (np.sum(points*direction[active], axis=1) > 0)
        blocked = ~escaped & (~np.isfinite(height) | (radius < RADIUS+height))
        visible[active[blocked]] = False
        active = active[~(blocked | escaped)]
    # Unresolved rays are unavailable rather than falsely marked visible.
    visible[active] = False
    return visible


def trace_optimized(points, target):
    if not NUMBA_AVAILABLE:
        return trace(points, target)
    dem, transform = terrain()
    return accelerated_trace(points, target, dem, transform, RADIUS)


@lru_cache(maxsize=8)
def body_map(size, target):
    return trace_optimized(observers(size)[1], target)


@lru_cache(maxsize=3)
def visibility_map(size, sun, earth, encoding="array"):
    with MAP_LOCK:
        valid, points, heights = observers(size)
        matching = np.isfinite(heights)
        for target in (sun, earth):
            if target is not None:
                matching &= body_map(size, target)
        mask = np.zeros((size, size), dtype=np.uint8)
        mask[valid] = matching
        result = dict(size=size, radiusM=MAP_RADIUS, resolutionM=2*MAP_RADIUS/size)
        if encoding == "bitset":
            result.update(encoding="bitset-msb", visiblePacked=b64encode(np.packbits(mask).tobytes()).decode("ascii"))
        else:
            result["visible"] = mask.ravel().tolist()
        return result
