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
from pathlib import Path

# rioxarray adds the .rio accessor used to attach map information to xarray data.
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

# This imports names from this module; when imported normally they are already
# defined above. Direct execution can also load the module under its package name.
from Filters.Sunlight.illumination import MOON_RADIUS_KM, sme


# Solshade's projected distances and the DEM elevations are handled in meters.
RADIUS_M = MOON_RADIUS_KM * 1000
# A south-polar stereographic map places the south pole at (0, 0).
# Its projection uses a spherical Moon and projected coordinates in meters.
POLAR_CRS = CRS.from_proj4(
    "+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m +no_defs"
)

# Map coordinates use meters; this is the reference-sphere arc length per degree.
meters_per_degree = MOON_RADIUS_KM * 1000 * np.pi / 180


def directions(lon, lat):
    """Return local east, north and up unit vectors.

    lon, lat: Site longitude and latitude in degrees.
    Returns: Three unit vectors in the Moon-centered frame, in east/north/up order.
    """
    # NumPy's trigonometric functions take radians, not degrees.
    lon_rad, lat_rad = np.radians([lon, lat])

    # Up points out from the Moon's center through the chosen site.
    up = np.array([
        np.cos(lat_rad) * np.cos(lon_rad),
        np.cos(lat_rad) * np.sin(lon_rad),
        np.sin(lat_rad),
    ])
    # East and north lie along the site's local horizontal plane.
    east = np.array([
        -np.sin(lon_rad),
        np.cos(lon_rad),
        0.0,
    ])
    north = np.array([
        -np.sin(lat_rad) * np.cos(lon_rad),
        -np.sin(lat_rad) * np.sin(lon_rad),
        np.cos(lat_rad),
    ])

    return east, north, up

def sun_angles(et, lon, lat, height_m):
    """
    Return Sun elevation and azimuth in degrees.

    Parameters:
    et: SPICE ephemeris time.
    lon, lat: Site coordinates in degrees.
    height_m: Site elevation in meters above the DEM reference sphere.

    Returns:
    (elevation, azimuth): Angles in degrees, with azimuth clockwise from north.
    """
    # Unit vectors defining the site's local directions.
    east, north, up = directions(lon, lat)

    # The second returned value is light travel time, unused here.
    site_to_sun, _ = sme.get_site2sun_vec(et, lon, lat, height_m)

    # Find how much of the vector points east, north, and up.
    e = np.dot(site_to_sun, east)
    n = np.dot(site_to_sun, north)
    u = np.dot(site_to_sun, up)

    # Elevation is above the local horizontal; azimuth is clockwise from north.
    elevation = np.degrees(np.arctan2(u, np.hypot(e, n)))
    azimuth = np.degrees(np.arctan2(e, n)) % 360

    return elevation, azimuth

# Load SPICE data needed by calls that calculate Sun positions or convert time.
kl.load_kernels()


def _validate_dem(dem, lon, lat, max_terrain_height_m):
    """Validate an open DEM, site coordinates in degrees and optional height bound in meters."""
    # This validator belongs to the older simple-cylindrical visibility code,
    # not the polar stereographic Solshade helpers below.
    expected_crs = rasterio.crs.CRS.from_proj4(
        "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +R=1737400 +units=m +no_defs"
    )
    if dem.crs != expected_crs:
        raise ValueError("DEM must use the lunar simple-cylindrical CRS")
    if dem.transform.b != 0 or dem.transform.d != 0: #b for rotation in x, d for rotation in y
        raise ValueError("Rotated DEM grids are not supported")
    if not (-180 <= lon <= 180 and -90 < lat < 90):
        raise ValueError("Longitude must be in [-180, 180] and latitude in (-90, 90)")
    if max_terrain_height_m is not None and not np.isfinite(max_terrain_height_m):
        raise ValueError("Maximum terrain height must be finite")


def _read_site(dem, lon, lat, dem_array, max_terrain_height_m):
    """Return the elevation array, pixel (row, column), and site height in meters.

    dem: Open Rasterio dataset. lon, lat: site coordinates in degrees.
    dem_array: Optional preloaded elevation array, including its no-data mask.
    max_terrain_height_m: Optional global terrain height bound in meters.
    """
    # Use supplied data if available; otherwise read band 1 and retain its mask.
    heights = np.ma.asarray(dem.read(1, masked=True) if dem_array is None else dem_array)
    if heights.shape != (dem.height, dem.width):
        raise ValueError("DEM array shape does not match the dataset")

    # This DEM uses a simple-cylindrical projection in meters.
    row, col = dem.index(lon * meters_per_degree, lat * meters_per_degree)
    if not (0 <= row < dem.height and 0 <= col < dem.width):
        raise ValueError("Coordinates out of DEM bounds")
    sight_height = heights[row, col]
    if np.ma.is_masked(sight_height) or not np.isfinite(sight_height):
        raise ValueError("The DEM has no valid elevation at this location")
    if max_terrain_height_m is not None:
        # This checks the loaded DEM only; the caller must justify a global bound.
        valid_heights = heights.compressed() #compressed allows us to get all valid (non-masked) heights
        if np.any(np.isfinite(valid_heights) & (valid_heights > max_terrain_height_m)):
            raise ValueError("Maximum terrain height is below an elevation in the DEM")
    return heights, (row, col), float(sight_height)


def load_polar_terrain(source_path, resolution_m, search_distance_m):
    """Reproject the LOLA 75S FLOAT product, in kilometers, to a buffered grid."""
    # On a stereographic map, this radius encloses the 80 S to 90 S cap.
    cap_radius = 2 * RADIUS_M * math.tan(math.radians(10) / 2)
    # Round up so the requested cap and the terrain-search buffer both fit.
    cap_pixels = math.ceil(cap_radius / resolution_m)
    buffer_pixels = math.ceil(search_distance_m / resolution_m)
    # Build a square grid centered on the pole, including terrain outside the cap.
    half_size = cap_pixels + buffer_pixels
    size = 2 * half_size
    # Rasterio's transform maps rows and columns to projected x and y positions.
    transform = from_origin(-half_size * resolution_m, half_size * resolution_m,
                            resolution_m, resolution_m)
    # Start with missing values so uncovered terrain is not mistaken for zero height.
    terrain = np.full((size, size), np.nan, dtype=np.float32)
    with rasterio.open(source_path) as source:
        if source.crs is None:
            raise ValueError("The polar DEM must have a coordinate reference system")
        # Reproject band 1 onto our grid; averaging reduces the DEM's resolution.
        # Missing source pixels remain NaN rather than becoming elevations.
        reproject(
            source=rasterio.band(source, 1), destination=terrain,
            src_transform=source.transform, src_crs=source.crs,
            src_nodata=source.nodata, dst_transform=transform,
            dst_crs=POLAR_CRS, dst_nodata=np.nan, resampling=Resampling.average,
        )
    terrain *= 1000  # The LOLA FLOAT product stores elevations in kilometers.
    # Coordinates are at pixel centers: +0.5 moves from the edge to the center.
    # Rows move downward in the array, so projected y decreases as row increases.
    x = transform.c + (np.arange(size) + 0.5) * resolution_m
    y = transform.f - (np.arange(size) + 0.5) * resolution_m
    # Xarray associates each row and column with its projected coordinate.
    dem = xr.DataArray(terrain, dims=("y", "x"), coords={"y": y, "x": x})
    # Attach the projection and transform for Solshade and other raster tools.
    dem.rio.write_crs(POLAR_CRS, inplace=True)
    dem.rio.write_transform(transform, inplace=True)
    return dem, cap_pixels, buffer_pixels


def polar_sun_angles(dem, sun_km):
    """Return local solar elevation and Solshade grid angle for every pixel."""
    # Expand the 1D coordinate lists into a pair of 2D grids, one value per pixel.
    x, y = np.meshgrid(dem.x.values, dem.y.values)
    # Invert the south-polar stereographic projection; angles here are in radians.
    lon = np.arctan2(x, y)
    lat = -np.pi / 2 + 2 * np.arctan(np.hypot(x, y) / (2 * RADIUS_M))
    # Reuse these sine and cosine arrays when calculating position and directions.
    cos_lat, sin_lat = np.cos(lat), np.sin(lat)
    cos_lon, sin_lon = np.cos(lon), np.sin(lon)
    # Convert the Moon-centered site radius to km to match the SPICE Sun position.
    radius_km = (RADIUS_M + dem.values) / 1000
    # Sun position minus site position gives the direction from the site to Sun.
    sx = sun_km[0] - radius_km * cos_lat * cos_lon
    sy = sun_km[1] - radius_km * cos_lat * sin_lon
    sz = sun_km[2] - radius_km * sin_lat
    # Express that Moon-centered vector in each site's local east/north/up frame.
    east = -sx * sin_lon + sy * cos_lon
    north = -sx * sin_lat * cos_lon - sy * sin_lat * sin_lon + sz * cos_lat
    up = sx * cos_lat * cos_lon + sy * cos_lat * sin_lon + sz * sin_lat
    # Elevation is measured above the local horizontal; negative is below it.
    elevation = np.degrees(np.arctan2(up, np.hypot(east, north)))
    # North rotates around the pole, so convert the local direction to grid axes.
    # Solshade 1.0.0 horizon samples use 0 = grid east, 90 = grid north.
    grid_east = east * cos_lon + north * sin_lon
    grid_north = -east * sin_lon + north * cos_lon
    # Wrap angles to [0, 360) so they can be matched to horizon directions.
    angle = np.degrees(np.arctan2(grid_north, grid_east)) % 360
    return elevation, angle


def complete_ray_coverage(terrain, direction_index, directions, step_pixels, steps):
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

def 

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