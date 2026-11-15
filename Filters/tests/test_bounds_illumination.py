import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib.image as mpimg
import numpy as np
import rasterio
from pyproj import Geod
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from Filters.Sunlight import illumination_funcs, lola_download
from Filters.Sunlight.dem_geometry import MOON_RADIUS_M, _check_grid_size, load_bounded_terrain
from Filters.Sunlight.illumination_filter import IlluminationFilter


def fake_download(bounds, destination):
    """Write a small synthetic lunar DEM covering the requested download."""
    west, south, east, north = bounds
    meter = lola_download.METERS_PER_DEGREE
    left, bottom, right, top = (west * meter, south * meter, east * meter, north * meter)
    width = max(1, math.ceil((right - left) / 1000))
    height = max(1, math.ceil((top - bottom) / 1000))
    with rasterio.open(
        destination, "w", driver="GTiff", width=width, height=height, count=1,
        dtype="float32", nodata=np.nan,
        crs=CRS.from_proj4("+proj=eqc +R=1737400 +units=m +no_defs"),
        transform=from_bounds(left, bottom, right, top, width, height),
    ) as dataset:
        dataset.write(np.zeros((height, width), dtype=np.float32), 1)


class BoundsIlluminationTests(unittest.TestCase):
    def test_spherical_buffer_contains_points_in_all_directions(self):
        geod = Geod(a=MOON_RADIUS_M, b=MOON_RADIUS_M)
        regions = [(-3, -48, 4, -41), (179, -3, -179, 2), (-10, -89, 15, -87)]
        for bounds in regions:
            windows = lola_download.buffered_download_bounds(bounds, 20000)
            west, south, east, north = bounds
            width = (east - west) % 360
            for lon in (west, ((west + width / 2 + 180) % 360) - 180, east):
                for lat in (south, (south + north) / 2, north):
                    for direction in range(0, 360, 15):
                        point_lon, point_lat, _ = geod.fwd(lon, lat, direction, 20000)
                        self.assertTrue(any(
                            left - 1e-8 <= point_lon <= right + 1e-8
                            and bottom - 1e-8 <= point_lat <= top + 1e-8
                            for left, bottom, right, top in windows
                        ), (bounds, point_lon, point_lat, windows))

    def test_bounds_and_buffer_validate_invalid_input(self):
        for bounds in [(0, 0, 0, 1), (-181, 0, 1, 1), (0, 5, 1, 4),
                       (0, float("nan"), 1, 1), (180, 0, -180, 1)]:
            with self.subTest(bounds=bounds):
                with self.assertRaises(ValueError):
                    lola_download.validate_bounds(bounds)
        with self.assertRaises(ValueError):
            lola_download.buffered_download_bounds((-1, -1, 1, 1), -1)

    def test_polar_buffer_includes_all_longitudes(self):
        windows = lola_download.buffered_download_bounds((-20, -90, 20, -89), 10000)
        self.assertEqual(len(windows), 1)
        self.assertEqual((windows[0][0], windows[0][2]), (-180.0, 180.0))
        self.assertEqual(windows[0][1], -90.0)

    def test_downloads_are_cached_and_failures_are_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bounds = (-1, -1, 1, 1)
            with patch.object(lola_download, "download_crop", side_effect=fake_download) as download:
                first = lola_download.download_buffered_dem(bounds, 10000, tmp)
                second = lola_download.download_buffered_dem(bounds, 10000, tmp)
                self.assertEqual(first, second)
                self.assertEqual(download.call_count, 1)
            first[0].write_bytes(b"not a raster")
            with self.assertRaises(rasterio.errors.RasterioIOError):
                lola_download.download_buffered_dem(bounds, 10000, tmp)

    def test_large_download_fails_before_network_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(lola_download, "download_crop") as download:
                with self.assertRaisesRegex(ValueError, "working memory"):
                    lola_download.download_buffered_dem((-180, -90, 180, -80), 120000, tmp)
                download.assert_not_called()

    def test_download_limit_boundary(self):
        def window(width, height):
            degrees_per_pixel = 118 / lola_download.METERS_PER_DEGREE
            return (0, 0, (width - 2.1) * degrees_per_pixel,
                    (height - 2.1) * degrees_per_pixel)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(lola_download, "buffered_download_bounds",
                              return_value=[window(12000, 13421), window(3, 3090)]), \
                 patch.object(lola_download, "download_crop",
                              side_effect=RuntimeError("downloader reached")):
                with self.assertRaisesRegex(RuntimeError, "downloader reached"):
                    lola_download.download_buffered_dem((0, 0, 1, 1), 10000, tmp)
            with patch.object(lola_download, "buffered_download_bounds",
                              return_value=[window(12000, 13421), window(3, 3092)]), \
                 patch.object(lola_download, "download_crop") as download:
                with self.assertRaisesRegex(ValueError, "1.5 GiB"):
                    lola_download.download_buffered_dem((0, 0, 1, 1), 10000, tmp)
                download.assert_not_called()

    def test_horizon_limit_accepts_exactly_1_5_gib(self):
        _check_grid_size(402653184, 1, 1)
        with self.assertRaisesRegex(ValueError, "1.5 GiB"):
            _check_grid_size(402653185, 1, 1)

    def test_large_horizon_grid_fails_before_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = IlluminationFilter(
                bounds=(-1, -1, 1, 1), et=0, output_dir=tmp,
                pixel_size_m=1, search_dist_m=10000, directions=36,
            )
            with patch("Filters.Sunlight.illumination_filter.download_buffered_dem") as download:
                with self.assertRaisesRegex(ValueError, "Horizon grid"):
                    instance.run()
                download.assert_not_called()

    def test_dateline_crops_reproject_to_one_continuous_grid(self):
        bounds = (179, -1, -179, 1)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(lola_download, "download_crop", side_effect=fake_download):
                paths = lola_download.download_buffered_dem(bounds, 10000, tmp)
            self.assertEqual(len(paths), 2)
            dem, requested = load_bounded_terrain(paths, bounds, 2000, 4, 10000, "m")
            self.assertTrue(np.any(requested))
            self.assertTrue(np.all(np.isfinite(dem.values[requested])))
            self.assertTrue(np.any(np.isfinite(dem.values[~requested])))

    def test_south_pole_bounds_include_buffered_terrain(self):
        bounds = (-180, -90, 180, -89)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(lola_download, "download_crop", side_effect=fake_download):
                paths = lola_download.download_buffered_dem(bounds, 10000, tmp)
            dem, requested = load_bounded_terrain(paths, bounds, 2000, 4, 10000, "m")
            self.assertTrue(np.any(requested))
            self.assertTrue(np.all(np.isfinite(dem.values[requested])))
            self.assertTrue(np.any(np.isfinite(dem.values[~requested])))

    def test_bounds_request_downloads_buffer_and_crops_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bounds = (-1, -1, 1, 1)
            filter_instance = IlluminationFilter(
                bounds=bounds, et=0, output_dir=tmp, pixel_size_m=2000,
                search_dist_m=10000, directions=4,
            )
            with patch.object(lola_download, "download_crop", side_effect=fake_download) as download, \
                 patch.object(illumination_funcs.sme, "get_sun_vec",
                              return_value=(np.array([1737.4, 1e8, 0]), 0)):
                paths = filter_instance.run()
            download_bounds = download.call_args.args[0]
            self.assertLess(download_bounds[0], bounds[0])
            self.assertGreater(download_bounds[2], bounds[2])
            self.assertLess(download_bounds[1], bounds[1])
            self.assertGreater(download_bounds[3], bounds[3])
            images = [mpimg.imread(path) for path in paths]
            self.assertTrue(all(image.shape == images[0].shape for image in images))
            self.assertLess(images[0].shape[0], 40)
            self.assertLess(images[0].shape[1], 40)
            self.assertTrue(np.any(images[1][:, :, 3] > 0))
            unknown = np.array([100, 130, 160, 160]) / 255
            self.assertFalse(np.any(np.all(np.isclose(images[1], unknown), axis=-1)))

    def test_bounds_time_changes_reuse_download_and_horizons(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = IlluminationFilter(
                bounds=(-1, -1, 1, 1), et=0, output_dir=tmp,
                pixel_size_m=2000, search_dist_m=10000, directions=4,
            )
            with patch.object(lola_download, "download_crop", side_effect=fake_download) as download, \
                 patch.object(illumination_funcs.sme, "get_sun_vec",
                              return_value=(np.array([1737.4, 1e8, 0]), 0)), \
                 patch.object(illumination_funcs, "compute_horizon_map",
                              wraps=illumination_funcs.compute_horizon_map) as compute:
                first = instance.run()
                second = instance.calculate_at_time(1, Path(tmp) / "second")
            self.assertEqual(download.call_count, 1)
            self.assertEqual(compute.call_count, 1)
            self.assertTrue(first[1].exists())
            self.assertTrue(second[1].exists())
            self.assertNotEqual(first[1], second[1])


if __name__ == "__main__":
    unittest.main()
