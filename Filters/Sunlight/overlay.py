from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
import sys
sys.path.insert(0, str(ROOT))
import matplotlib.image as mpimg
import numpy as np
import rasterio

from Filters.filters import run_illumination_filter
from Filters.Sunlight.illumination_funcs import meters_per_degree


def save_illumination_overlay(et, bounds, dem_path, output_path, *,
                              max_terrain_height_m=None):
    """Save illuminated and unknown DEM pixels as a transparent PNG overlay.

    et: SPICE ephemeris time.
    bounds: (lon_min, lat_min, lon_max, lat_max) in degrees, or None for
        the entire supplied DEM. Outside the bounds the PNG is transparent.
    dem_path: Path to the lunar simple-cylindrical elevation GeoTIFF.
    output_path: Destination PNG path. An existing file is overwritten.
    max_terrain_height_m: Optional independently justified global height
        bound in meters, passed to the illumination calculation.

    The PNG covers the entire DEM grid, even when bounds selects a smaller
    area. It aligns with a base image rendered from that same grid and extent,
    without axes or margins. Illuminated pixels are yellow, unknown pixels
    are gray-blue, and blocked pixels are transparent.
    """
    path = Path(output_path)
    if path.suffix.lower() != ".png":
        raise ValueError("The illumination overlay must be saved as a PNG")

    with rasterio.open(dem_path) as dem:
        # RGBA stores red, green, blue and opacity for every DEM pixel.
        overlay = np.zeros((dem.height, dem.width, 4), dtype=np.uint8)
        results = run_illumination_filter(
            et, bounds, dem_path, max_terrain_height_m=max_terrain_height_m,
        )
        for lon, lat, visible in results:
            row, col = dem.index(lon * meters_per_degree, lat * meters_per_degree)
            if not (0 <= row < dem.height and 0 <= col < dem.width):
                raise ValueError("Illumination result is outside the DEM grid")
            if visible is True:
                overlay[row, col] = (255, 220, 0, 160)
            elif visible is None:
                overlay[row, col] = (100, 130, 160, 160)
            elif visible is not False:
                raise ValueError("Illumination result must be True, False or None")

    # Saving the array directly avoids the margins and axes of a plotted figure.
    mpimg.imsave(path, overlay, format="png")
    return path


if __name__ == "__main__":
    DEM_path = ROOT / "lola_2d" / "data" / "tycho_1_1_1_3.tif"
    # Example usage (replace with actual values as needed):
    path = save_illumination_overlay(et=0, bounds=None, dem_path=DEM_path, output_path="overlay.png")