# Reference radius of the spherical Moon model, in kilometers.
MOON_RADIUS_KM = 1737.4

# Direct script execution starts Python's import search in the Sunlight folder.
if __package__ in (None, ""):
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import rasterio
import spiceypy as sp
from SMEData import kernel_loaders as kl
from SMEData import SME_data_getter as sme
from SurfaceData.moon_surface_getter import open_dem
from numba import njit

import math
from dataclasses import dataclass
from pathlib import Path

# rioxarray adds the .rio accessor used to attach map information to xarray data.
import matplotlib.image as mpimg
import rasterio
import rioxarray
import xarray as xr
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from scipy.ndimage import map_coordinates
from solshade.terrain import compute_horizon_map
from Filters.Sunlight.dem_geometry import load_bounded_terrain, load_regional_terrain, regional_sun_angles
from Filters.Sunlight.lola_download import validate_bounds

# Solshade's projected distances and the DEM elevations are handled in meters.
RADIUS_M = MOON_RADIUS_KM * 1000
# A south-polar stereographic map places the south pole at (0, 0).
# Its projection uses a spherical Moon and projected coordinates in meters.
POLAR_CRS = CRS.from_proj4(
    "+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m +no_defs"
)

# Map coordinates use meters; this is the reference-sphere arc length per degree.
meters_per_degree = MOON_RADIUS_KM * 1000 * np.pi / 180

# Load SPICE data needed by calls that calculate Sun positions or convert time.
kl.load_kernels()

#solshade can skip missing samples and still determine a horizon angle
#this function ensures that we only have reliable horizon coverage for each pixel.
def complete_ray_coverage(terrain, direction_index, directions, step_pixels, steps):
    #terrain: 2D array of elevation values
    #direction_index: index of the direction to sample
    #directions: total number of directions
    #step_pixels: number of pixels to step along the ray
    #steps: number of steps to check along the ray
    """Find pixels whose selected sampled ray stays in valid terrain."""
    # Each element of rows/cols contains that pixel's own row or column index.
    rows, cols = np.indices(terrain.shape)
    # Convert each selected direction index into the angle used to sample the grid.
    angle = np.radians(direction_index * (360 / directions))
    # Use 1 for valid elevations and 0 for missing elevations during interpolation.
    valid = np.isfinite(terrain)
    valid_samples = valid.astype(np.float32)
    complete = valid.copy()
    # Check each sample along the selected direction for every starting pixel.
    for step in range(1, steps + 1):
        distance = step * step_pixels
        # Array rows increase downward, so a northward displacement subtracts rows.
        sample_rows = rows - np.sin(angle) * distance
        sample_cols = cols + np.cos(angle) * distance
        # Interpolation returns 0 outside the grid; missing neighbors reduce coverage.
        coverage = map_coordinates(
            valid_samples, [sample_rows, sample_cols],
            order=1, mode="constant", cval=0,
        )
        # A pixel stays complete only if every sampled location has valid data.
        # The small tolerance accounts for floating-point interpolation rounding.
        complete &= coverage >= 1 - 1e-6
    return complete

@dataclass(frozen=True) # Immutable data class for storing prepared terrain information
class PreparedTerrain:
    """Terrain and horizon data shared by calculations at different times."""

    dem: xr.DataArray
    footprint: np.ndarray
    horizons: xr.DataArray
    steps: int
    directions: int
    bounds: tuple | None


def prepare_terrain(dem_path, pixel_size_m=1000, search_dist_m=500000,
                    directions=90, elevation_units=None, bounds=None):
    """Load a DEM and compute horizons once, independently of Sun position."""
    if (not math.isfinite(pixel_size_m) or not math.isfinite(search_dist_m)
            or pixel_size_m <= 0 or search_dist_m <= 0
            or not isinstance(directions, (int, np.integer)) or directions < 4):
        raise ValueError("Pixel size and search distance must be finite and positive; use at least 4 directions")
    if bounds is None:
        dem, footprint = load_regional_terrain(dem_path, pixel_size_m, directions, elevation_units)
    else:
        bounds = validate_bounds(bounds)
        paths = dem_path if isinstance(dem_path, (list, tuple)) else [dem_path]
        dem, footprint = load_bounded_terrain(
            paths, bounds, pixel_size_m, directions, search_dist_m, elevation_units,
        )
    if not np.any(footprint & np.isfinite(dem.values)):
        raise ValueError("The DEM has no valid elevations in its projected extent")
    steps = math.ceil(search_dist_m / pixel_size_m)
    effective_distance = steps * pixel_size_m # Total distance covered by the ray tracing steps in one direction
    print(f"Calculating {directions} horizons on a {dem.shape[1]} x {dem.shape[0]} grid...")

    horizons = compute_horizon_map(dem, n_directions=directions,
                                         max_distance=effective_distance,
                                         step=pixel_size_m,
                                         chunk_size=8,
                                         n_jobs=1)
    return PreparedTerrain(dem, footprint, horizons, steps, directions, bounds)


def render_at_time(prepared, et, output_dir, mask_only=False, mask_filename="polar_illumination.png"):
    """Save images for one time using previously prepared terrain.

    Files in the output directory are overwritten by the next render. Use
    separate output directories to retain images for multiple times. When
    mask_only is true, save and return only the illumination overlay path,
    using mask_filename for its name.
    """
    dem = prepared.dem
    footprint = prepared.footprint
    horizons = prepared.horizons
    steps = prepared.steps
    directions = prepared.directions
    bounds = prepared.bounds
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sun_km, _ = sme.get_sun_vec(et)
    elevation, angle = regional_sun_angles(dem, sun_km)

    direction_index = np.zeros(dem.shape, dtype=np.int64)
    valid_angle = np.isfinite(angle) #mask of boolean values indicating where the angle is valid
    angle_spacing = 360 / directions
    direction_index[valid_angle] = np.floor(angle[valid_angle] / angle_spacing).astype(np.int64) #we convert the angles into indices that can be used to select the corresponding horizon direction (since we only sample every θ increments)
    row, col = np.indices(dem.shape) #create arrays of row and column indices for the DEM grid
    current_sun_horizon = horizons.values[direction_index, row, col] #select the horizon for each pixel based on its direction index
    coverage = complete_ray_coverage(dem.values, #.values allows us to pass the raw numpy array of the DEM
                                     direction_index,
                                     directions,
                                     1,
                                     steps,
                                     ) #essentially another mask that validates the coverage of the ray tracing for each pixel

    known = (coverage #coverage mask indicating where the ray tracing is complete
             & valid_angle #mask indicating where the Sun direction is valid
             & np.isfinite(elevation) #mask indicating where the elevation is valid
             & np.isfinite(current_sun_horizon) #mask indicating where the current sun horizon is valid
             )

    visible = known & (elevation >= current_sun_horizon) #mask indicating where the sun is visible

    terrain = dem.values
    if bounds is not None:
        rows_within, cols_within = np.where(footprint)
        if rows_within.size == 0:
            raise ValueError("The requested bounds contain no output pixels; decrease pixel_size_m")
        region = (slice(rows_within.min(), rows_within.max() + 1),
                  slice(cols_within.min(), cols_within.max() + 1))
        terrain = terrain[region]
        visible = visible[region]
        known = known[region]
        footprint = footprint[region]
    valid_terrain = footprint & np.isfinite(terrain)

    visible_in_region = footprint & visible

    # An RGBA pixel has red, green, blue, and opacity values from 0 to 255.
    # Fill visible pixels in yellow; blocked pixels remain transparent.
    overlay = np.zeros((*terrain.shape, 4), dtype=np.uint8)
    overlay[visible_in_region] = (255, 220, 0, 160)
    overlay[footprint & ~known] = (100, 130, 160, 160)
    if mask_only:
        overlay_path = output_dir / mask_filename
        mpimg.imsave(overlay_path, overlay)
        return overlay_path

    # Stretch terrain heights into grayscale for a matching visual base.
    base = np.zeros((*terrain.shape, 4), dtype=np.uint8)
    low, high = np.percentile(terrain[valid_terrain], (2, 98))
    if high <= low:
        high = low + 1
    shade = np.clip((terrain[valid_terrain] - low) / (high - low), 0, 1)
    base[valid_terrain, :3] = (shade * 255).astype(np.uint8)[:, np.newaxis]
    base[valid_terrain, 3] = 255

    # Blend the translucent overlay over the base for a combined preview.
    preview = overlay.copy()
    alpha = overlay[valid_terrain, 3:4].astype(np.float32) / 255
    preview[valid_terrain, :3] = (
        overlay[valid_terrain, :3] * alpha
        + base[valid_terrain, :3] * (1 - alpha)
    ).astype(np.uint8)
    preview[valid_terrain, 3] = 255

    base_path = output_dir / "polar_base.png"
    overlay_path = output_dir / "polar_illumination.png"
    preview_path = output_dir / "polar_preview.png"
    mpimg.imsave(base_path, base)
    mpimg.imsave(overlay_path, overlay)
    mpimg.imsave(preview_path, preview)
    return base_path, overlay_path, preview_path


def Illumination_filter(dem_path, et, output_dir, pixel_size_m=1000,
                        search_dist_m=500000, directions=90, elevation_units=None,
                        bounds=None):
    """Prepare a regional lunar DEM and save illumination images for one time.

    PNGs use a local projected grid and contain no geographic metadata.
    Results are approximate and limited by terrain coverage and search distance.
    """
    prepared = prepare_terrain(
        dem_path, pixel_size_m=pixel_size_m, search_dist_m=search_dist_m,
        directions=directions, elevation_units=elevation_units, bounds=bounds,
    )
    return render_at_time(prepared, et, output_dir)