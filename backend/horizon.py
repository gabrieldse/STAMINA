"""LOLA terrain skyline, following Mazarico et al. (2011), doi:10.1016/j.icarus.2010.10.030.

Conservative 0.5-degree azimuth sectors over the complete 75S, 240 m DEM.
Body-center visibility, surface observer, no refraction or scattered light.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

RADIUS = 1737400.0
DEM = Path(__file__).resolve().parents[1] / "lola_2d/data/ldem_75s_240m_dem.tif"


def basis(latitude, longitude):
    lat, lon = np.radians([latitude, longitude])
    up = np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])
    east = np.array([-np.sin(lon), np.cos(lon), 0])
    return up, east, np.cross(up, east)


def sector_angles(vectors, up, east, north):
    e, n, u = vectors @ east, vectors @ north, vectors @ up
    azimuth = np.mod(np.arctan2(e, n), 2*np.pi)
    return np.minimum((azimuth * 720/(2*np.pi)).astype(int), 719), np.arctan2(u, np.hypot(e, n))


@lru_cache(maxsize=128)
def profile(latitude, longitude):
    if latitude > -80:
        from backend.global_lola import global_profile
        return global_profile(float(latitude), float(longitude))
    if not DEM.exists():
        raise ValueError("LOLA 75S 240 m DEM unavailable. Generate it with lola_2d/south_pole.py.")
    up, east, north = basis(latitude, longitude)
    rho = 2*RADIUS*np.tan(np.radians(90+latitude)/2)
    lon = np.radians(longitude)
    with rasterio.open(DEM) as src:
        row, col = src.index(rho*np.sin(lon), rho*np.cos(lon))
        height = src.read(1, window=Window(col, row, 1, 1), masked=True)
        if height.size != 1 or np.ma.is_masked(height) or not np.isfinite(height.item()):
            raise ValueError("No LOLA elevation at this site.")
        observer = (RADIUS + float(height.item())) * up
        skyline = np.full(720, -np.pi/2)
        for start in range(0, src.height, 128):
            heights = src.read(1, window=Window(0, start, src.width, min(128, src.height-start)), masked=True)
            rows, cols = np.indices(heights.shape)
            x, y = rasterio.transform.xy(src.transform, rows+start, cols)
            x, y = np.asarray(x).reshape(heights.shape), np.asarray(y).reshape(heights.shape)
            radial = np.hypot(x, y)
            lat = 2*np.arctan(radial/(2*RADIUS))-np.pi/2
            lon = np.arctan2(x, y)
            radius = RADIUS + heights.filled(np.nan)
            points = np.stack([radius*np.cos(lat)*np.cos(lon), radius*np.cos(lat)*np.sin(lon), radius*np.sin(lat)], axis=-1)
            delta = points-observer
            valid = np.isfinite(radius) & (np.linalg.norm(delta, axis=-1) > 120)
            sectors, angles = sector_angles(delta[valid], up, east, north)
            np.maximum.at(skyline, sectors, angles)
    if np.any(skyline == -np.pi/2):
        raise ValueError("Incomplete LOLA horizon coverage at this site.")
    return observer, skyline


def body_visibility(positions_km, latitude, longitude):
    observer, skyline = profile(latitude, longitude)
    sectors, angles = sector_angles(np.asarray(positions_km).reshape(-1, 3)*1000-observer, *basis(latitude, longitude))
    return angles > skyline[sectors]
