"""Prepare regional lunar DEMs for planar illumination calculations."""

import math

import numpy as np
import rasterio
import rioxarray
import xarray as xr
from pyproj import CRS as PyprojCRS, Geod, Transformer
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds

MOON_RADIUS_M = 1737400.0
LUNAR_GEOGRAPHIC = PyprojCRS.from_proj4(
    f"+proj=longlat +R={MOON_RADIUS_M} +no_defs"
)


def _elevation_multiplier(source, elevation_units):
    """Resolve the vertical unit without confusing it with the map's units."""
    unit = elevation_units if elevation_units is not None else source.units[0]
    names = {
        "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
        "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
        "kilometre": 1000.0, "kilometres": 1000.0,
    }
    if not isinstance(unit, str) or unit.strip().lower() not in names:
        raise ValueError(
            "DEM elevation units are missing or unsupported; set elevation_units='m' or 'km'"
        )
    return names[unit.strip().lower()]


def _height_parameters(source, elevation_units):
    if source.count != 1:
        raise ValueError("The DEM must have exactly one elevation band")
    if source.crs is None:
        raise ValueError("The DEM must have a lunar coordinate reference system")
    source_crs = PyprojCRS.from_wkt(source.crs.to_wkt())
    ellipsoid = source_crs.ellipsoid
    if (abs(ellipsoid.semi_major_metre - MOON_RADIUS_M) > 10000
            or abs(ellipsoid.semi_minor_metre - MOON_RADIUS_M) > 10000):
        raise ValueError("The DEM CRS must use a lunar reference body")
    multiplier = _elevation_multiplier(source, elevation_units)
    scale, offset = source.scales[0], source.offsets[0]
    if not math.isfinite(scale) or not math.isfinite(offset):
        raise ValueError("DEM scale and offset must be finite")
    # This PDS product's offset is the reference radius, not a height offset.
    if source.driver == "PDS" and offset != 0:
        tags = source.tags()
        if (tags.get("PRODUCT_ID", "").strip('"') == "LDEM_75S_240M"
                and tags.get("DATA_SET_ID", "").strip('"') == "LRO-L-LOLA-4-GDR-V1.0"
                and abs(offset - 1737.4) < 1e-6):
            offset = 0.0
        else:
            raise ValueError(
                "PDS elevation offset requires dataset-specific interpretation; "
                "convert the DEM to a GeoTIFF of heights first"
            )
    return source_crs, multiplier, scale, offset


def _check_grid_size(width, height, directions):
    if width < 1 or height < 1:
        raise ValueError("DEM has an empty projected extent")
    horizon_bytes = width * height * directions * np.dtype(np.float32).itemsize
    if horizon_bytes > 1024**3:
        raise ValueError(
            "Horizon grid exceeds 1 GiB before working memory; "
            "increase pixel_size_m, reduce directions, or use a regional crop"
        )


def _reproject_heights(source, local_crs, transform, shape, elevation_units):
    """Reproject heights and keep pixels with incomplete source data unknown."""
    _, multiplier, scale, offset = _height_parameters(source, elevation_units)
    terrain = np.full(shape, np.nan, dtype=np.float32)
    reproject(
        source=rasterio.band(source, 1), destination=terrain,
        src_transform=source.transform, src_crs=source.crs,
        src_nodata=source.nodata, dst_transform=transform,
        dst_crs=local_crs, dst_nodata=np.nan, resampling=Resampling.average,
    )
    source_valid = source.read_masks(1).astype(np.float32) / 255
    valid_fraction = np.zeros(shape, dtype=np.float32)
    reproject(
        source=source_valid, destination=valid_fraction,
        src_transform=source.transform, src_crs=source.crs,
        dst_transform=transform, dst_crs=local_crs,
        dst_nodata=0, resampling=Resampling.average,
    )
    terrain[valid_fraction < 1 - 1e-6] = np.nan
    return (terrain * scale + offset) * multiplier


def load_regional_terrain(source_path, resolution_m, directions, elevation_units=None):
    """Reproject a regional lunar DEM to a local azimuthal-equidistant grid.

    The result includes the whole raster extent, not terrain beyond its edges.
    Heights are converted to meters. A separate footprint identifies pixels
    outside the source raster from missing elevations within that footprint.
    """
    with rasterio.open(source_path) as source:
        source_crs, _, _, _ = _height_parameters(source, elevation_units)

        to_lonlat = Transformer.from_crs(source_crs, LUNAR_GEOGRAPHIC, always_xy=True)
        center_x, center_y = source.transform @ (source.width / 2, source.height / 2)
        lon0, lat0 = to_lonlat.transform(center_x, center_y)
        if not np.isfinite(lon0) or not np.isfinite(lat0) or abs(lat0) > 90:
            raise ValueError("Cannot determine the DEM's lunar location")
        local_crs = CRS.from_proj4(
            f"+proj=aeqd +lat_0={lat0:.12g} +lon_0={lon0:.12g} "
            f"+R={MOON_RADIUS_M} +units=m +no_defs"
        )
        left, bottom, right, top = transform_bounds(
            source.crs, local_crs, *source.bounds, densify_pts=101,
        )
        if not all(math.isfinite(v) for v in (left, bottom, right, top)):
            raise ValueError("Cannot project the complete DEM extent to a local grid")
        # A single local planar approximation is not appropriate for a global DEM.
        grid_radius = math.hypot(max(abs(left), abs(right)), max(abs(bottom), abs(top)))
        if grid_radius >= math.pi * MOON_RADIUS_M / 2:
            raise ValueError("DEM extent is too large for one local grid; use a regional crop")
        width = math.ceil((right - left) / resolution_m)
        height = math.ceil((top - bottom) / resolution_m)
        _check_grid_size(width, height, directions)
        transform = from_origin(left, top, resolution_m, resolution_m)
        terrain = _reproject_heights(source, local_crs, transform,
                                     (height, width), elevation_units)
        x = transform.c + (np.arange(width) + 0.5) * resolution_m
        y = transform.f - (np.arange(height) + 0.5) * resolution_m
        grid_x, grid_y = np.meshgrid(x, y)
        to_source = Transformer.from_crs(local_crs.to_wkt(), source_crs, always_xy=True)
        source_x, source_y = to_source.transform(grid_x, grid_y)
        cols, rows = ~source.transform @ (source_x, source_y)
        footprint = (
            np.isfinite(cols) & np.isfinite(rows)
            & (cols >= 0) & (cols < source.width)
            & (rows >= 0) & (rows < source.height)
        )

    dem = xr.DataArray(terrain, dims=("y", "x"), coords={"y": y, "x": x})
    dem.rio.write_crs(local_crs, inplace=True)
    dem.rio.write_transform(transform, inplace=True)
    return dem, footprint


def bounded_grid(bounds, resolution_m, directions, search_distance_m):
    """Build and check the requested buffered grid without downloading data."""
    west, south, east, north = bounds
    width_degrees = 360 if (west == -180 and east == 180) else (east - west) % 360
    lon0 = ((west + width_degrees / 2 + 180) % 360) - 180
    lat0 = (south + north) / 2
    if width_degrees == 360 and south == -90:
        lat0 = -90
    elif width_degrees == 360 and north == 90:
        lat0 = 90
    local_crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat0:.12g} +lon_0={lon0:.12g} "
        f"+R={MOON_RADIUS_M} +units=m +no_defs"
    )
    to_grid = Transformer.from_crs(LUNAR_GEOGRAPHIC, local_crs.to_wkt(), always_xy=True)
    longitudes = np.linspace(west, west + width_degrees, 721)
    latitudes = np.linspace(south, north, 181)
    edge_lon = np.concatenate((longitudes, longitudes,
                               np.full_like(latitudes, west),
                               np.full_like(latitudes, west + width_degrees)))
    edge_lat = np.concatenate((np.full_like(longitudes, south), np.full_like(longitudes, north),
                               latitudes, latitudes))
    edge_x, edge_y = to_grid.transform(edge_lon, edge_lat)
    if not np.all(np.isfinite(edge_x)) or not np.all(np.isfinite(edge_y)):
        raise ValueError("Cannot project the requested bounds onto one local grid")
    # Include the rounded-up ray distance and resampling margin in the grid.
    padding = math.ceil(search_distance_m / resolution_m) * resolution_m + 2 * resolution_m
    left, right = float(np.min(edge_x)) - padding, float(np.max(edge_x)) + padding
    bottom, top = float(np.min(edge_y)) - padding, float(np.max(edge_y)) + padding
    if math.hypot(max(abs(left), abs(right)), max(abs(bottom), abs(top))) >= math.pi * MOON_RADIUS_M / 2:
        raise ValueError("Requested area and buffer are too large for one local grid")
    width = math.ceil((right - left) / resolution_m)
    height = math.ceil((top - bottom) / resolution_m)
    _check_grid_size(width, height, directions)
    transform = from_origin(left, top, resolution_m, resolution_m)
    return local_crs, transform, width, height


def load_bounded_terrain(source_paths, bounds, resolution_m, directions,
                         search_distance_m, elevation_units=None):
    """Load buffered source crops on a grid centered on the requested bounds."""
    west, south, east, north = bounds
    width_degrees = 360 if (west == -180 and east == 180) else (east - west) % 360
    local_crs, transform, width, height = bounded_grid(
        bounds, resolution_m, directions, search_distance_m,
    )
    terrain = np.full((height, width), np.nan, dtype=np.float32)
    if len(source_paths) == 2:
        # A request crossing 180 degrees is downloaded as two crops. Join
        # their source pixels before averaging so the seam is not a data gap.
        with rasterio.open(source_paths[0]) as first, rasterio.open(source_paths[1]) as second:
            east_source, west_source = sorted((first, second), key=lambda source: source.bounds.left, reverse=True)
            east_crs, east_multiplier, east_scale, east_offset = _height_parameters(east_source, elevation_units)
            west_crs, west_multiplier, west_scale, west_offset = _height_parameters(west_source, elevation_units)
            half_world = math.pi * MOON_RADIUS_M
            tolerance = abs(east_source.res[0]) / 100
            projection = east_source.crs.to_dict()
            if (east_crs != west_crs or projection.get("proj") != "eqc"
                    or any(projection.get(key, 0) != 0 for key in ("lon_0", "lat_0", "lat_ts", "x_0", "y_0"))
                    or east_source.transform.b != 0 or east_source.transform.d != 0
                    or west_source.transform.b != 0 or west_source.transform.d != 0
                    or east_source.height != west_source.height
                    or not math.isclose(east_source.res[0], west_source.res[0], abs_tol=tolerance)
                    or not math.isclose(east_source.res[1], west_source.res[1], abs_tol=tolerance)
                    or abs(east_source.bounds.top - west_source.bounds.top) > tolerance
                    or abs(east_source.bounds.right - half_world) > tolerance
                    or abs(west_source.bounds.left + half_world) > tolerance):
                raise ValueError("Dateline DEM crops do not share an aligned lunar cylindrical grid")
            east_raw = east_source.read(1, masked=True).astype(np.float32).filled(np.nan)
            west_raw = west_source.read(1, masked=True).astype(np.float32).filled(np.nan)
            east_values = (east_raw * east_scale + east_offset) * east_multiplier
            west_values = (west_raw * west_scale + west_offset) * west_multiplier
            mosaic = np.concatenate((east_values, west_values), axis=1).astype(np.float32)
            seam_crs = CRS.from_proj4(
                f"+proj=eqc +lon_0=180 +R={MOON_RADIUS_M} +units=m +no_defs"
            )
            seam_transform = from_origin(
                east_source.bounds.left - half_world, east_source.bounds.top,
                east_source.res[0], abs(east_source.res[1]),
            )
            with MemoryFile() as memory:
                with memory.open(
                    driver="GTiff", width=mosaic.shape[1], height=mosaic.shape[0],
                    count=1, dtype="float32", crs=seam_crs,
                    transform=seam_transform, nodata=np.nan,
                ) as source:
                    source.write(mosaic, 1)
                    terrain = _reproject_heights(source, local_crs, transform,
                                                 (height, width), "m")
    else:
        for path in source_paths:
            with rasterio.open(path) as source:
                part = _reproject_heights(source, local_crs, transform,
                                          (height, width), elevation_units)
                usable = np.isfinite(part)
                terrain[usable] = part[usable]

    x = transform.c + (np.arange(width) + 0.5) * resolution_m
    y = transform.f - (np.arange(height) + 0.5) * resolution_m
    grid_x, grid_y = np.meshgrid(x, y)
    to_lonlat = Transformer.from_crs(local_crs.to_wkt(), LUNAR_GEOGRAPHIC, always_xy=True)
    lon, lat = to_lonlat.transform(grid_x, grid_y)
    if width_degrees == 360:
        in_longitude = np.isfinite(lon)
    elif west < east:
        in_longitude = (lon >= west) & (lon <= east)
    else:
        in_longitude = (lon >= west) | (lon <= east)
    requested = in_longitude & (lat >= south) & (lat <= north)
    dem = xr.DataArray(terrain, dims=("y", "x"), coords={"y": y, "x": x})
    dem.rio.write_crs(local_crs, inplace=True)
    dem.rio.write_transform(transform, inplace=True)
    return dem, requested


def regional_sun_angles(dem, sun_km):
    """Return Sun elevation and grid direction for each local-grid pixel."""
    x, y = np.meshgrid(dem.x.values, dem.y.values)
    local_crs = PyprojCRS.from_wkt(dem.rio.crs.to_wkt())
    to_lonlat = Transformer.from_crs(local_crs, LUNAR_GEOGRAPHIC, always_xy=True)
    to_grid = Transformer.from_crs(LUNAR_GEOGRAPHIC, local_crs, always_xy=True)
    lon_deg, lat_deg = to_lonlat.transform(x, y)
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    cos_lat, sin_lat = np.cos(lat), np.sin(lat)
    cos_lon, sin_lon = np.cos(lon), np.sin(lon)
    radius_km = (MOON_RADIUS_M + dem.values) / 1000
    sx = sun_km[0] - radius_km * cos_lat * cos_lon
    sy = sun_km[1] - radius_km * cos_lat * sin_lon
    sz = sun_km[2] - radius_km * sin_lat
    east = -sx * sin_lon + sy * cos_lon
    north = -sx * sin_lat * cos_lon - sy * sin_lat * sin_lon + sz * cos_lat
    up = sx * cos_lat * cos_lon + sy * cos_lat * sin_lon + sz * sin_lat
    elevation = np.degrees(np.arctan2(up, np.hypot(east, north)))

    # Project small east/north displacements to capture local grid rotation
    # and projection scale, including away from the projection center.
    geod = Geod(a=MOON_RADIUS_M, b=MOON_RADIUS_M)
    distance = np.full(x.shape, 10.0)
    east_lon, east_lat, _ = geod.fwd(lon_deg, lat_deg, np.full(x.shape, 90.0), distance)
    north_lon, north_lat, _ = geod.fwd(lon_deg, lat_deg, np.zeros(x.shape), distance)
    east_x, east_y = to_grid.transform(east_lon, east_lat)
    north_x, north_y = to_grid.transform(north_lon, north_lat)
    grid_east = east * (east_x - x) + north * (north_x - x)
    grid_north = east * (east_y - y) + north * (north_y - y)
    angle = np.degrees(np.arctan2(grid_north, grid_east)) % 360
    return elevation, angle
