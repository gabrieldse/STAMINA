import math
from numbers import Integral
from pathlib import Path

import rasterio

from Filters.generic_filter_model import Filter
from Filters.Sunlight import illumination_funcs
from Filters.Sunlight.dem_geometry import bounded_grid
from Filters.Sunlight.lola_download import download_buffered_dem, validate_bounds


def _source_signature(source_paths):
    """Track source files and their GDAL sidecars without reading all pixels."""
    source_files = set()
    for source_path in source_paths:
        source_files.add(Path(source_path).resolve())
        with rasterio.open(source_path) as source:
            source_files.update(Path(name).resolve() for name in source.files)
    signature = []
    for source_path in sorted(source_files):
        stat = source_path.stat()
        signature.append((source_path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
    return tuple(signature)


class IlluminationFilter(Filter):
    """Run approximate lunar illumination from a DEM or geographic bounds.

    With bounds and no dem_path, download a buffered LOLA DEM into output_dir.
    With dem_path, use the supplied lunar DEM; bounds optionally restrict output.
    Bounds are (west, south, east, north) in degrees, east-positive; west > east
    crosses the dateline. Downloaded crops are cached under output_dir.
    Set elevation_units='m' or 'km' if a supplied DEM does not specify its
    heights' units. Returned PNGs do not themselves contain georeferencing.
    prepare() caches horizons in memory; run() and calculate_at_time() reuse
    them while terrain settings and source file metadata remain unchanged.
    Treat prepared_terrain and horizons as read-only. File changes are detected
    by size and timestamps, not content hashing; call clear_prepared() if an
    external tool changes a DEM without updating its file metadata.
    Results overwrite the same filenames unless a different output directory
    is passed to calculate_at_time().

    Example (et values are SPICE ephemeris times):
        image_filter.prepare()
        image_filter.calculate_at_time(first_et, "results/first")
        image_filter.calculate_at_time(second_et, "results/second")
    """

    is_time_dependent = True

    def __init__(self, dem_path=None, et=None, output_dir=None, bounds=None, pixel_size_m=1000,
                 search_dist_m=500000, directions=90, elevation_units=None):
        super().__init__(output_dir, bounds, pixel_size_m=pixel_size_m)
        self.dem_path = dem_path
        self.et = et
        self.search_dist_m = search_dist_m
        self.directions = directions
        self.elevation_units = elevation_units
        self.prepared_terrain = None
        self.horizons = None
        self._prepared_key = None

    def prepare(self):
        """Load and cache terrain/horizons, recalculating when inputs change."""
        if self.output_dir is None:
            raise ValueError("An output_dir is required")
        if (not math.isfinite(self.pixel_size_m) or self.pixel_size_m <= 0
                or not math.isfinite(self.search_dist_m) or self.search_dist_m <= 0):
            raise ValueError("Pixel size and search distance must be finite and positive")
        if not isinstance(self.directions, Integral) or self.directions < 4:
            raise ValueError("Use at least 4 horizon directions")
        bounds = validate_bounds(self.bounds) if self.bounds is not None else None
        if bounds is not None:
            bounded_grid(bounds, self.pixel_size_m, self.directions, self.search_dist_m)
        if self.dem_path is None:
            if bounds is None:
                raise ValueError("Provide either a DEM path or longitude/latitude bounds")
            if self.elevation_units is not None and (
                    not isinstance(self.elevation_units, str)
                    or self.elevation_units.strip().lower() not in (
                        "m", "meter", "meters", "metre", "metres")):
                raise ValueError("Downloaded LOLA elevations are in meters")
            distance = (math.ceil(self.search_dist_m / self.pixel_size_m) + 2) * self.pixel_size_m
            paths = download_buffered_dem(bounds, distance, Path(self.output_dir) / ".lola-cache")
            units = "m"
        else:
            path = Path(self.dem_path)
            if not path.exists():
                raise FileNotFoundError(f"DEM does not exist: {path}")
            paths = self.dem_path
            units = self.elevation_units
        source_paths = paths if isinstance(paths, (tuple, list)) else [paths]
        signature = _source_signature(source_paths)
        key = (signature, bounds, self.pixel_size_m,
               self.search_dist_m, self.directions, units)
        if self.prepared_terrain is not None and key == self._prepared_key:
            return self.prepared_terrain

        # Drop stale data before attempting a new preparation.
        self.clear_prepared()
        prepared = illumination_funcs.prepare_terrain(
            paths,
            pixel_size_m=self.pixel_size_m,
            search_dist_m=self.search_dist_m,
            directions=self.directions,
            elevation_units=units,
            bounds=bounds,
        )
        if _source_signature(source_paths) != signature:
            raise RuntimeError("DEM source files changed during terrain preparation; retry")
        self.prepared_terrain = prepared
        self.horizons = prepared.horizons
        self._prepared_key = key
        return prepared

    def clear_prepared(self):
        """Release cached arrays and force the next calculation to prepare again."""
        self.prepared_terrain = None
        self.horizons = None
        self._prepared_key = None

    def calculate_at_time(self, et, output_dir=None):
        """Render one time, reusing prepared data when its inputs are unchanged."""
        if et is None:
            raise ValueError("A SPICE ephemeris time is required")
        prepared = self.prepare()
        destination = self.output_dir if output_dir is None else output_dir
        return illumination_funcs.render_at_time(prepared, et, destination)

    def run(self):
        """Render the configured time, preparing the terrain if needed."""
        return self.calculate_at_time(self.et)