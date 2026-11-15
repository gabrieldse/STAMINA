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

@dataclass(frozen=True)
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


def render_at_time(prepared, et, output_dir):
    """Save images for one time using previously prepared terrain.

    Files in the output directory are overwritten by the next render. Use
    separate output directories to retain images for multiple times.
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

# The following triple-quoted block retains the older ray-tracing implementation
# as text; Python does not define or run the functions inside it.
'''
def _sun_ray(et, lon, lat, height_m, sun_vec):
    """Return the site in meters, unit direction toward the Sun, and distance in km.

    et: SPICE ephemeris time; lon, lat: site coordinates in degrees.
    height_m: site elevation in meters; sun_vec: optional Moon-to-Sun vector in km.
    """
    site_km, _ = sme.get_site_vec(et, lon, lat, height_m)
    if sun_vec is None:
        sun_vec, _ = sme.get_sun_vec(et)
    sun_position = np.asarray(sun_vec, dtype=float)
    if sun_position.shape != (3,) or not np.all(np.isfinite(sun_position)):
        raise ValueError("Sun position must be a finite 3D vector")
    # Both positions start at the Moon's center; their difference starts at the site.
    ray = sun_position - site_km
    ray_length = np.linalg.norm(ray)
    if not np.isfinite(ray_length) or ray_length == 0:
        raise ValueError("Sun position must define a finite nonzero 3D direction")
    # A unit vector stores direction only, so distance can be applied separately.
    ray /= ray_length
    return site_km * 1000, ray, ray_length
# site_m , unit vector from site to sun, distance to sun in km

def _ray_step(dem, horizontal_fraction):
    """Return ray step in meters from an open DEM and the ray's horizontal fraction."""
    # East-west pixels shrink towards the poles in a cylindrical projection.
    max_abs_lat = max(abs(dem.bounds.bottom), abs(dem.bounds.top)) / meters_per_degree
    if max_abs_lat >= 90:
        raise ValueError("This simple-cylindrical ray sampler does not support a DEM at the poles")
    ground_pixel_m = min(abs(dem.res[0]) * np.cos(np.radians(max_abs_lat)), #cos to adjust for E-W pixel shrinkage
                         abs(dem.res[1])) #res for resolution along N and E directions
    if not np.isfinite(ground_pixel_m) or ground_pixel_m <= 0:
        raise ValueError("DEM pixel spacing must be positive")
    # Aim for several samples per ground pixel; cap division near vertical rays.
    return ground_pixel_m / (4 * max(horizontal_fraction, 0.001))


# Compile the numerical loop once per argument signature, not once per sample.
@njit
def _trace_ray_numba(heights, mask, site_row, site_col, site_m, ray,
                     ray_length_m, step_m, inverse_transform,
                     has_height_bound, height_bound, max_steps):
    """Trace the ray; return 0 for blocked, 1 for clear, or -1 for unknown.

    heights, mask: 2D DEM elevations in meters and missing-data flags.
    site_row, site_col: site pixel. site_m: Moon-centered site vector in meters.
    ray: unit direction to the Sun; ray_length_m: distance to Sun in meters.
    step_m: sample interval; inverse_transform: map-to-pixel coefficients.
    has_height_bound, height_bound: whether a global height bound in meters exists.
    max_steps: maximum number of samples.
    """
    for step in range(1, max_steps + 1):
        distance_m = step * step_m
        if distance_m >= ray_length_m:
            return -1

        # A straight line in Moon-centered coordinates accounts for curvature.
        point_x = site_m[0] + distance_m * ray[0]
        point_y = site_m[1] + distance_m * ray[1]
        point_z = site_m[2] + distance_m * ray[2]
        horizontal_radius = np.hypot(point_x, point_y)
        radius = np.hypot(horizontal_radius, point_z)
        if radius == 0:
            return -1
        point_lon = np.degrees(np.arctan2(point_y, point_x))
        point_lat = np.degrees(np.arctan2(point_z, horizontal_radius))
        x = point_lon * meters_per_degree
        y = point_lat * meters_per_degree

        # Apply the inverse DEM transform to obtain the containing pixel.
        col = int(np.floor(inverse_transform[0] * x + inverse_transform[1] * y + inverse_transform[2]))
        row = int(np.floor(inverse_transform[3] * x + inverse_transform[4] * y + inverse_transform[5]))
        if not (0 <= row < heights.shape[0] and 0 <= col < heights.shape[1]):
            return -1
        terrain_height = heights[row, col]
        if mask[row, col] or not np.isfinite(terrain_height):
            return -1

        # Both heights are measured above the same reference sphere, in meters.
        ray_height = radius - MOON_RADIUS_KM * 1000
        # Ignore the starting pixel to avoid treating the site as its own obstacle.
        if (row != site_row or col != site_col) and ray_height <= terrain_height:
            return 0
        # Above the assumed global bound and moving outward, the ray stays above it.
        if (has_height_bound and ray_height > height_bound and
                point_x * ray[0] + point_y * ray[1] + point_z * ray[2] > 0):
            return 1
    return -1


def _prepare_ray_data(dem, heights):
    """Return elevation data, no-data mask and map-to-pixel transform for a DEM."""
    # The inverse transform converts projected map coordinates into pixel indices.
    inverse = ~dem.transform
    inverse_transform = np.array([inverse.a, inverse.b, inverse.c,
                                  inverse.d, inverse.e, inverse.f])
    return np.asarray(np.ma.getdata(heights)), np.ma.getmaskarray(heights), inverse_transform


def _trace_ray(dem, heights, site_cell, site_m, ray, ray_length,
               step_m, max_terrain_height_m, ray_data=None):
    """Trace a ray through an open DEM and return True, False or None.

    dem, heights: open Rasterio DEM and masked elevation array in meters.
    site_cell: site pixel; site_m: Moon-centered site position in meters.
    ray: unit direction; ray_length: distance to the Sun in kilometers.
    step_m: sample interval in meters; max_terrain_height_m: optional global bound.
    ray_data: Optional precomputed arrays and transform from _prepare_ray_data.
    """
    # Numba cannot consume Rasterio datasets or NumPy masked arrays directly.
    if ray_data is None:
        ray_data = _prepare_ray_data(dem, heights)
    height_data, mask, inverse_transform = ray_data
    has_height_bound = max_terrain_height_m is not None
    height_bound = float(max_terrain_height_m) if has_height_bound else 0.0
    result = _trace_ray_numba(
        height_data, mask, site_cell[0], site_cell[1], site_m, ray,
        ray_length * 1000, step_m, inverse_transform,
        has_height_bound, height_bound, 200000,
    )
    # Translate Numba's numeric codes back to the public three-state result.
    if result == -1:
        return None
    return result == 1


def _check_site(dem, heights, site_cell, et, lon, lat, height_m, sun_vec,
                max_terrain_height_m, ray_data=None):
    """Return site visibility using the DEM, site coordinates, time and Sun vector.

    dem, heights, site_cell: open dataset, height array and pixel coordinates.
    et: SPICE time; lon, lat: degrees; height_m: site height in meters.
    sun_vec: optional Moon-to-Sun vector in kilometers.
    max_terrain_height_m: optional global height bound; ray_data: preloaded arrays.
    """
    site_m, ray, ray_length = _sun_ray(et, lon, lat, height_m, sun_vec)
    _, _, up = directions(lon, lat)
    # Remove the vertical component to find how much the ray moves horizontally.
    horizontal = np.linalg.norm(ray - np.dot(ray, up) * up)
    if horizontal < 1e-12 and np.dot(ray, up) > 0:
        return True
    step_m = _ray_step(dem, horizontal)
    return _trace_ray(dem, heights, site_cell, site_m, ray, ray_length,
                      step_m, max_terrain_height_m, ray_data)


def check_visibility(lon, lat, et, sun_vec=None, dem_array=None, *, dem=None,
                     dem_path=None, max_terrain_height_m=None, verbose=False):
    """Estimate visibility of the Sun's center through a simple-cylindrical DEM.

    Return False for a sampled obstruction, True if the ray clears an assumed
    global maximum terrain height, or None if coverage is insufficient.
    Heights and the optional global maximum are meters above the DEM reference
    sphere. sun_vec, if supplied, is the Moon-center-to-Sun vector in km.
    Pixels are sampled as constant-height cells; this is not a precision model.

    lon, lat: site longitude and latitude in degrees.
    et: SPICE ephemeris time; sun_vec: optional Moon-to-Sun position in km.
    dem_path: path to the DEM; alternatively pass an open dataset as dem.
    dem_array: optional masked array matching dem.
    max_terrain_height_m: optional independently justified global height bound.
    verbose: reserved for compatibility; no output is currently printed.
    """
    if dem is None:
        if dem_path is None:
            raise ValueError("Provide dem_path or an open dem")
        # Reuse the same function with an open dataset; the context closes it afterwards.
        with open_dem(dem_path) as dataset:
            return check_visibility(lon, lat, et, sun_vec, dem_array, dem=dataset,
                                    max_terrain_height_m=max_terrain_height_m, verbose=verbose)

    _validate_dem(dem, lon, lat, max_terrain_height_m)
    heights, site_cell, height_m = _read_site(dem, lon, lat, dem_array, max_terrain_height_m)
    return _check_site(dem, heights, site_cell, et, lon, lat, height_m, sun_vec,
                       max_terrain_height_m)

def IlluminationFilter(et, bounds, dem_path, *, max_terrain_height_m=None):
    """Yield (longitude, latitude, visibility) for DEM pixel centers inside bounds.

    et: SPICE ephemeris time.
    bounds: (lon_min, lat_min, lon_max, lat_max) in degrees, or None for the
        entire supplied DEM. Bounds must be inside the DEM and not cross 180°.
    dem_path: Path to the terrain GeoTIFF, which may extend beyond the output area.
    max_terrain_height_m: Optional independently justified global height bound.

    Visibility is True, False, or None (unknown or missing site data).
    This samples the Sun's center and does not model partial illumination.
    """
    with open_dem(dem_path) as dem:
        # No bounds means all of this DEM, not necessarily the whole Moon.
        if bounds is None:
            bounds = tuple(value / meters_per_degree for value in dem.bounds)
        if len(bounds) != 4 or not np.all(np.isfinite(bounds)):
            raise ValueError("Bounds must contain four finite coordinates")
        lon_min, lat_min, lon_max, lat_max = bounds
        if not (-180 <= lon_min < lon_max <= 180 and -90 < lat_min < lat_max < 90):
            raise ValueError("Invalid bounds; use (lon_min, lat_min, lon_max, lat_max)")
        _validate_dem(dem, lon_min, lat_min, max_terrain_height_m)
        left, bottom, right, top = (value * meters_per_degree for value in bounds)
        tolerance = max(dem.res) * 1e-6
        if (left < dem.bounds.left - tolerance or bottom < dem.bounds.bottom - tolerance
                or right > dem.bounds.right + tolerance or top > dem.bounds.top + tolerance):
            raise ValueError("Requested bounds extend outside the DEM")

        # Read the surrounding terrain once; rays may leave the output bounds.
        heights = dem.read(1, masked=True)
        if max_terrain_height_m is not None:
            valid = heights.compressed()
            if np.any(np.isfinite(valid) & (valid > max_terrain_height_m)):
                raise ValueError("Maximum terrain height is below an elevation in the DEM")
        sun_vec, _ = sme.get_sun_vec(et)
        ray_data = _prepare_ray_data(dem, heights) 
        # Restrict output iteration to pixels intersecting the requested bounds.
        window = rasterio.windows.from_bounds(left, bottom, right, top, dem.transform)
        row_start = max(0, int(np.floor(window.row_off)))
        row_end = min(dem.height, int(np.ceil(window.row_off + window.height)))
        col_start = max(0, int(np.floor(window.col_off)))
        col_end = min(dem.width, int(np.ceil(window.col_off + window.width)))

        for row in range(row_start, row_end):
            for col in range(col_start, col_end):
                x, y = dem.xy(row, col)
                lon, lat = x / meters_per_degree, y / meters_per_degree
                # Windows can include edge pixels whose centers are outside the bounds.
                if not (lon_min <= lon < lon_max and lat_min <= lat < lat_max):
                    continue
                height_m = heights[row, col]
                if np.ma.is_masked(height_m) or not np.isfinite(height_m):
                    yield lon, lat, None
                    continue
                visible = _check_site(dem, heights, (row, col), et, lon, lat,
                                      float(height_m), sun_vec, max_terrain_height_m, ray_data)
                # Yield one result at a time instead of storing a whole output map.
                yield lon, lat, visible

'''