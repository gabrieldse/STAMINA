"""Download buffered LOLA crops for a requested lunar region."""

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import rasterio

from Filters.Sunlight.dem_geometry import MOON_RADIUS_M
from lola_2d.lola_hillshade import LOLA_URL, METERS_PER_DEGREE, download_crop


def validate_bounds(bounds):
    """Return finite east-positive (west, south, east, north) degrees."""
    try:
        west, south, east, north = bounds
        west, south, east, north = (float(value) for value in (west, south, east, north))
    except (TypeError, ValueError):
        raise ValueError("Bounds must contain four numbers: west, south, east, north") from None
    if (not all(math.isfinite(value) for value in (west, south, east, north))
            or not -180 <= west <= 180 or not -180 <= east <= 180
            or not -90 <= south < north <= 90
            or west == east or (west == 180 and east == -180)):
        raise ValueError("Bounds must define a nonempty lunar region in longitude -180..180 and latitude -90..90")
    return west, south, east, north


def buffered_download_bounds(bounds, distance_m):
    """Return non-wrapping geographic rectangles containing the buffered region."""
    west, south, east, north = validate_bounds(bounds)
    if not math.isfinite(distance_m) or distance_m <= 0:
        raise ValueError("Buffer distance must be finite and positive")
    # Leave additional room for source pixel rounding and resampling.
    angular = min(math.pi, (distance_m + 500) / MOON_RADIUS_M)
    degrees = math.degrees(angular)
    south_buffered = max(-90.0, south - degrees)
    north_buffered = min(90.0, north + degrees)
    max_lat = max(abs(south), abs(north))
    if angular >= math.pi / 2 or max_lat + degrees >= 90:
        return [(-180.0, south_buffered, 180.0, north_buffered)]
    longitude_margin = math.degrees(math.asin(min(1.0, math.sin(angular) / math.cos(math.radians(max_lat)))))
    width = (east - west) % 360
    if west == -180 and east == 180:
        width = 360
    if width + 2 * longitude_margin >= 360:
        return [(-180.0, south_buffered, 180.0, north_buffered)]
    start = ((west - longitude_margin + 180) % 360) - 180
    end = start + width + 2 * longitude_margin
    if end <= 180:
        return [(start, south_buffered, end, north_buffered)]
    return [(start, south_buffered, 180.0, north_buffered),
            (-180.0, south_buffered, end - 360, north_buffered)]


def download_buffered_dem(bounds, distance_m, cache_dir):
    """Download each required crop once, without overwriting existing files."""
    windows = buffered_download_bounds(bounds, distance_m)
    # download_crop reads and converts the full native-resolution crop in memory.
    # Account for raw pixels, scaled heights, and temporary arrays before download.
    estimated_pixels = 0
    for west, south, east, north in windows:
        width = math.ceil((east - west) * METERS_PER_DEGREE / 118) + 2
        height = math.ceil((north - south) * METERS_PER_DEGREE / 118) + 2
        estimated_pixels += width * height
    if estimated_pixels * 10 > 1024**3:
        raise ValueError(
            "The buffered LOLA crop may require more than 1 GiB of working memory; "
            "use smaller bounds or a shorter search distance"
        )
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for window in windows:
        key = json.dumps([LOLA_URL, *window], separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        destination = cache_dir / f"lola-{digest}.tif"
        if not destination.exists():
            print(f"Downloading buffered LOLA terrain for {window}...")
            with tempfile.TemporaryDirectory(prefix="lola-download-", dir=cache_dir) as tmp:
                temporary = Path(tmp) / "crop.tif"
                download_crop(window, temporary)
                _validate_crop(temporary, window)
                if not destination.exists():
                    os.rename(temporary, destination)
        _validate_crop(destination, window)
        paths.append(destination)
    return paths


def _validate_crop(path, window):
    """Detect incomplete cached crops before using them as terrain."""
    with rasterio.open(path) as source:
        if source.crs is None or source.count != 1 or source.width == 0 or source.height == 0:
            raise ValueError(f"Invalid cached LOLA DEM: {path}")
        left, bottom, right, top = (value * METERS_PER_DEGREE for value in window)
        tolerance = max(abs(source.res[0]), abs(source.res[1])) * 2
        if (source.bounds.left > left + tolerance or source.bounds.bottom > bottom + tolerance
                or source.bounds.right < right - tolerance or source.bounds.top < top - tolerance):
            raise ValueError(f"Cached LOLA DEM does not cover its requested bounds: {path}")
