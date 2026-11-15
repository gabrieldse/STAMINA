import json
import math
from bisect import bisect_left
from numbers import Integral
from pathlib import Path

import rasterio
import spiceypy as sp

from Filters.generic_filter_model import Filter
from Filters.Sunlight import illumination_funcs
from Filters.Sunlight.dem_geometry import bounded_grid
from Filters.Sunlight.lola_download import download_buffered_dem, validate_bounds


def nearest_mask_filename(samples, utc):
    """Return the nearest indexed filename for a UTC time, preferring earlier ties.

    Load the ordered samples from illumination_times.json once, then reuse them
    for slider updates. This function does not prepare terrain or render images.
    """
    if not samples:
        raise ValueError("The illumination time index has no samples")
    et = sp.str2et(utc)
    position = bisect_left(samples, et, key=lambda sample: sample["et"])
    if position == 0:
        return samples[0]["filename"]
    if position == len(samples):
        return samples[-1]["filename"]
    before, after = samples[position - 1], samples[position]
    return (before if et - before["et"] <= after["et"] - et else after)["filename"]


def _source_signature(source_paths):
    """Describe DEM files and GDAL sidecars for cache invalidation.

    The signature contains each path, size, modification time and creation
    time. It is not a hash of the file contents.
    """
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
    prepare() caches horizons in memory; calculate_at_time() and run_over_time()
    reuse them while terrain settings and source file metadata remain unchanged.
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

    # Illumination changes with time even though the terrain horizons do not.
    is_time_dependent = True

    def __init__(self, dem_path=None, et_init=0, et_final=None, output_dir=None, bounds=None, pixel_size_m=1000,
                 search_dist_m=500000, directions=90, elevation_units=None):
        """Store the input settings; no DEM or horizon calculation runs yet.

        et_init and et_final are SPICE ephemeris times, not calendar dates. A DEM path can be
        provided directly, or bounds can be used to download LOLA terrain.
        pixel_size_m sets the projected grid spacing, search_dist_m sets the
        horizon search distance, and directions sets the number of horizons
        calculated at each grid pixel.
        """
        super().__init__(output_dir, bounds, pixel_size_m=pixel_size_m)
        self.dem_path = dem_path
        self.et_init = et_init
        self.et_final = et_final if et_final is not None else et_init
        self.search_dist_m = search_dist_m
        self.directions = directions
        self.elevation_units = elevation_units
        # These remain empty until the first preparation. The prepared object
        # holds the buffered DEM, output footprint, horizons and grid settings.
        self.prepared_terrain = None
        self.horizons = None  # The same horizon array held in prepared_terrain.
        self._prepared_key = None  # Identifies the inputs used for that data.

    def prepare(self):
        """Return reusable terrain data, preparing it when needed.

        On the first call, obtain or reuse the DEM, reproject it to a local
        grid and calculate a horizon for every sampled direction and pixel.
        Solshade's horizon array has dimensions (direction, row, column);
        its values are terrain horizon angles, not Sun angles. None of this
        depends on et, so later times can reuse it in the same object.

        Every call validates settings and checks source-file metadata. Changes
        to the source, bounds, resolution, search distance, direction count or
        elevation units invalidate the cached data. A change to et does not.
        """
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
            # Download extra terrain so rays can check beyond the output bounds.
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
        # Time and rendering destination are intentionally absent from the key.
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
        """Forget the cached terrain and horizons for this filter object.

        This does not delete downloaded DEMs or PNGs. The next preparation
        recalculates the horizons; other references may still hold the arrays.
        """
        self.prepared_terrain = None
        self.horizons = None
        self._prepared_key = None

    def calculate_at_time(self, et, output_dir=None, mask_only=False,
                          mask_filename="polar_illumination.png"):
        """Calculate and save illumination for the supplied SPICE time.

        prepare() first checks whether the existing terrain and horizons can
        be reused. For each time, render_at_time() calculates the Sun position
        and per-pixel Sun elevation/direction, selects the matching horizon,
        checks terrain coverage along that direction, and rebuilds the
        visible/unknown masks and PNGs. Unless mask_only is set, it also
        regenerates the base image and blended preview.

        By default, returns paths to the base, overlay and preview PNGs. With
        mask_only=True, saves and returns only the illumination overlay path,
        named mask_filename.
        Existing files of those names are overwritten; pass a different
        output_dir for each time to retain them. This method does not update
        the stored time range.
        """
        if et is None:
            raise ValueError("A SPICE ephemeris time is required")
        prepared = self.prepare()
        destination = self.output_dir if output_dir is None else output_dir
        if mask_only:
            return illumination_funcs.render_at_time(
                prepared, et, destination, mask_only=True, mask_filename=mask_filename,
            )
        return illumination_funcs.render_at_time(prepared, et, destination)

    '''
    def run(self):
        """Render self.et, preparing or reusing the terrain as needed."""
        return self.calculate_at_time(self.et)
    '''

    def run_over_time(self):
        """Save hourly masks from et_init, stopping at or before et_final.

        SPICE ephemeris times are in seconds. Return mask paths in time order.
        Filenames contain UTC times, and illumination_times.json maps each
        UTC time and ephemeris time to its filename. Load this index once to
        select the nearest sample without recomputing illumination.
        An end time within 0.01 seconds of an hourly sample is included to
        account for the difference between UTC and ephemeris time.
        """
        if self.output_dir is None:
            raise ValueError("An output_dir is required")
        if not math.isfinite(self.et_init) or not math.isfinite(self.et_final):
            raise ValueError("Start and end ephemeris times must be finite")
        if self.et_final < self.et_init:
            raise ValueError("End ephemeris time must not be before start time")

        results = []
        samples = []
        count = math.floor((self.et_final - self.et_init + 0.01) / 3600) + 1
        for hour in range(count):
            et = min(self.et_init + hour * 3600, self.et_final)
            utc = sp.et2utc(et, "ISOC", 3) + "Z"
            filename = f"illumination_{utc.replace(':', '-')}.png"
            results.append(self.calculate_at_time(et, mask_only=True, mask_filename=filename))
            samples.append({"utc": utc, "et": float(et), "filename": filename})

        with (Path(self.output_dir) / "illumination_times.json").open("w", encoding="utf-8") as index:
            json.dump({"samples": samples}, index, indent=2)

        return results
