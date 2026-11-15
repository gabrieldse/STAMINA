"""Instantaneous, sampled LOLA line-of-sight maps in local stereographic views."""
from functools import lru_cache
from threading import Lock
from base64 import b64encode

import numpy as np
import rasterio

from backend.horizon import DEM, RADIUS
from backend.global_lola import regional_dem, sample_global
from backend.visibility_kernel import NUMBA_AVAILABLE, accelerated_trace, accelerated_trace_global

MAP_LOCK = Lock()
MAP_RADIUS = 2 * RADIUS * np.tan(np.radians(10) / 2)


@lru_cache(maxsize=1)
def terrain():
    if not DEM.exists():
        raise ValueError("LOLA 75S 240 m DEM unavailable.")
    with rasterio.open(DEM) as src:
        return src.read(1, masked=True).filled(np.nan), src.transform


def sample(points, center=(-90.0, 0.0)):
    if center != (-90.0, 0.0):
        return sample_global(points, center)
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


@lru_cache(maxsize=2)
def observers(size, center=(-90.0, 0.0)):
    coords = ((np.arange(size)+.5)/size*2-1)*MAP_RADIUS
    x, y = np.meshgrid(coords, -coords)
    valid = x*x+y*y <= MAP_RADIUS**2
    latitude, longitude = np.radians(center)
    up = np.array([np.cos(latitude)*np.cos(longitude), np.cos(latitude)*np.sin(longitude), np.sin(latitude)])
    east = np.array([-np.sin(longitude), np.cos(longitude), 0.0])
    north = np.cross(up, east)
    px, py = x[valid], y[valid]
    q = (px*px+py*py)/(4*RADIUS*RADIUS)
    normals = ((1-q)[:, None]*up + (px/RADIUS)[:, None]*east + (py/RADIUS)[:, None]*north)/(1+q)[:, None]
    heights = sample(normals*RADIUS, center)
    return valid, normals*(RADIUS+heights[:, None]), heights


def trace(observers_m, target_km, center=(-90.0, 0.0)):
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
    if center == (-90.0, 0.0):
        heights, _ = terrain()
        ceiling = RADIUS + float(np.nanmax(heights)) + 1
    else:
        dem, _, _ = regional_dem(center)
        ceiling = RADIUS + float(np.nanmax(dem)) + 1
    for distance in np.arange(240., 1_200_001., 240.):
        if not len(active):
            break
        points = observers_m[active]+distance*direction[active]
        radius = np.linalg.norm(points, axis=1)
        height = sample(points) if center == (-90.0, 0.0) else sample(points, center)
        escaped = (radius > ceiling) & (np.sum(points*direction[active], axis=1) > 0)
        blocked = ~escaped & (~np.isfinite(height) | (radius < RADIUS+height))
        visible[active[blocked]] = False
        active = active[~(blocked | escaped)]
    # Unresolved rays are unavailable rather than falsely marked visible.
    visible[active] = False
    return visible


def trace_optimized(points, target, center=(-90.0, 0.0)):
    if not NUMBA_AVAILABLE:
        return trace(points, target, center)
    if center == (-90.0, 0.0):
        dem, transform = terrain()
        return accelerated_trace(points, target, dem, transform, RADIUS)
    dem, transform, patch_longitude = regional_dem(center)
    return accelerated_trace_global(points, target, dem, transform, RADIUS, patch_longitude)


@lru_cache(maxsize=24)
def body_map(size, target, center=(-90.0, 0.0)):
    return trace_optimized(observers(size, center)[1], target, center)


@lru_cache(maxsize=3)
def visibility_map(size, sun, earth, encoding="array", center=(-90.0, 0.0)):
    with MAP_LOCK:
        valid, points, heights = observers(size, center)
        matching = np.isfinite(heights)
        coverage = matching.copy()
        for target in (sun, earth):
            if target is not None:
                matching &= (body_map(size, target) if center == (-90.0, 0.0)
                             else body_map(size, target, center))
        mask = np.zeros((size, size), dtype=np.uint8)
        mask[valid] = matching
        result = dict(size=size, radiusM=MAP_RADIUS, resolutionM=2*MAP_RADIUS/size,
                      coveragePct=round(100*float(coverage.mean()), 2))
        if encoding == "bitset":
            coverage_mask = np.zeros((size, size), dtype=np.uint8)
            coverage_mask[valid] = coverage
            result.update(encoding="bitset-msb", visiblePacked=b64encode(np.packbits(mask).tobytes()).decode("ascii"),
                          coveragePacked=b64encode(np.packbits(coverage_mask).tobytes()).decode("ascii"))
        else:
            result["visible"] = mask.ravel().tolist()
        return result
