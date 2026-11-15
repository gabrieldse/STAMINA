"""Pixel-by-pixel reference ray tracer for simple-cylindrical lunar DEMs."""
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from SMEData import kernel_loaders as kl
from SMEData import SME_data_getter as sme
from SurfaceData.moon_surface_getter import open_dem
import numpy as np
import rasterio
import spiceypy as sp
from numba import njit

MOON_RADIUS_KM = 1737.4

# Map coordinates use meters; this is the reference-sphere arc length per degree.
meters_per_degree = MOON_RADIUS_KM * 1000 * np.pi / 180


def directions(lon, lat):
    """Return local east, north and up unit vectors.

    lon, lat: Site longitude and latitude in degrees.
    Returns: Three unit vectors in the Moon-centered frame, in east/north/up order.
    """
    lon_rad, lat_rad = np.radians([lon, lat])

    # These three unit vectors describe the site's local directions in Moon coordinates.
    up = np.array([
        np.cos(lat_rad) * np.cos(lon_rad),
        np.cos(lat_rad) * np.sin(lon_rad),
        np.sin(lat_rad),
    ])
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

    site_to_sun, _ = sme.get_site2sun_vec(et, lon, lat, height_m)

    # Find how much of the vector points east, north, and up.
    e = np.dot(site_to_sun, east)
    n = np.dot(site_to_sun, north)
    u = np.dot(site_to_sun, up)

    # Elevation is above the local horizontal; azimuth is clockwise from north.
    elevation = np.degrees(np.arctan2(u, np.hypot(e, n)))
    azimuth = np.degrees(np.arctan2(e, n)) % 360

    return elevation, azimuth

kl.load_kernels()


def _validate_dem(dem, lon, lat, max_terrain_height_m):
    """Validate an open DEM, site coordinates in degrees and optional height bound in meters."""
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