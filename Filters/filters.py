from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import Filters.Sunlight.illumination as illum
import lola_2d.lola_hillshade as lola_hs


def run_illumination_filter(et, bounds, dem_path, *, download=False, max_terrain_height_m=None):
    """Return an iterator of (longitude, latitude, visibility) for the chosen DEM.

    et: SPICE ephemeris time.
    bounds: (lon_min, lat_min, lon_max, lat_max) in degrees, or None to
        evaluate the entire existing DEM.
    dem_path: GeoTIFF path to use; existing files are not overwritten.
    download: If True, download bounds when the DEM file does not exist.
    max_terrain_height_m: Optional independently justified global height bound.

    A downloaded crop contains only the requested bounds, so terrain shadows
    near its edges may be unknown. Supply a larger DEM for surrounding terrain.
    """
    path = Path(dem_path)
    # Reuse an existing file; downloading is only done when explicitly requested.
    if not path.exists():
        if not download:
            raise FileNotFoundError(f"DEM does not exist: {path}")
        if bounds is None:
            raise ValueError("Bounds are required when downloading a DEM")
        if len(bounds) != 4:
            raise ValueError("Bounds must contain four coordinates")
        lon_min, lat_min, lon_max, lat_max = bounds
        if not (-180 <= lon_min < lon_max <= 180 and -90 < lat_min < lat_max < 90):
            raise ValueError("Invalid bounds; use (lon_min, lat_min, lon_max, lat_max)")
        lola_hs.download_crop(bounds, path)
    # IlluminationFilter yields results as it iterates; it does not build a map here.
    return illum.IlluminationFilter(et, bounds, path,
                                    max_terrain_height_m=max_terrain_height_m)
