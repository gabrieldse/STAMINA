import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Sunlight"))

import illumination as illumination
import Filters
import moon_surface_getter


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "terrain.tif"
        self.memory = MemoryFile()
        self.dem = self.memory.open(
            driver="GTiff", width=7, height=7, count=1, dtype="float32",
            transform=from_origin(-350, 350, 100, 100), nodata=np.nan,
            crs=rasterio.crs.CRS.from_proj4(
                "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +R=1737400 +units=m +no_defs"
            ),
        )
        self.heights = np.zeros((7, 7), dtype="float32")
        site, _ = illumination.sme.get_site_vec(0, 0, 0, 0)
        east, _, up = illumination.directions(0, 0)
        direction = np.cos(np.radians(5)) * east + np.sin(np.radians(5)) * up
        self.sun = site + 1e8 * direction

    def tearDown(self):
        self.dem.close()
        self.memory.close()
        self.tempdir.cleanup()

    def save_dem(self):
        with rasterio.open(self.path, "w", **self.dem.profile) as dataset:
            dataset.write(self.heights, 1)

    def visibility(self, **kwargs):
        self.dem.write(self.heights, 1)
        return illumination.check_visibility(0, 0, 0, self.sun, dem=self.dem, **kwargs)

    def test_ridge_towards_sun_blocks_ray(self):
        self.heights[3, 5] = 100
        self.assertIs(self.visibility(), False)

    def test_ridge_behind_does_not_block_ray(self):
        self.heights[3, 1] = 100
        self.assertIsNone(self.visibility())

    def test_unknown_when_ray_leaves_dem(self):
        self.assertIsNone(self.visibility())

    def test_clear_with_assumed_terrain_bound(self):
        self.assertIs(self.visibility(max_terrain_height_m=0), True)

    def test_invalid_terrain_bound_raises(self):
        self.heights[3, 5] = 100
        with self.assertRaises(ValueError):
            self.visibility(max_terrain_height_m=0)

    def test_missing_terrain_is_unknown(self):
        self.heights[3, 4] = np.nan
        self.assertIsNone(self.visibility())

    def test_masked_terrain_stops_before_a_later_obstruction(self):
        self.heights[3, 5] = 100
        masked = np.ma.array(self.heights, mask=np.zeros((7, 7), dtype=bool))
        masked.mask[3, 4] = True
        self.assertIsNone(self.visibility(dem_array=masked))

    def test_compiled_loop_matches_python_loop_and_limits_steps(self):
        inverse = ~self.dem.transform
        transform = np.array([inverse.a, inverse.b, inverse.c,
                              inverse.d, inverse.e, inverse.f])
        site, _ = illumination.sme.get_site_vec(0, 0, 0, 0)
        ray = self.sun - site
        ray /= np.linalg.norm(ray)
        args = (self.heights, np.zeros((7, 7), dtype=bool), 3, 3,
                site * 1000, ray, 1e11, 1, transform, False, 0.0, 5)
        compiled_result = illumination._trace_ray_numba(*args)
        python_result = illumination._trace_ray_numba.py_func(*args)
        self.assertEqual(compiled_result, -1)
        self.assertEqual(compiled_result, python_result)
        self.assertTrue(illumination._trace_ray_numba.nopython_signatures)

    def test_missing_site_elevation_raises(self):
        self.heights[3, 3] = np.nan
        with self.assertRaisesRegex(ValueError, "no valid elevation"):
            self.visibility()

    def test_supplied_dem_array_shape_is_checked(self):
        with self.assertRaisesRegex(ValueError, "array shape"):
            self.visibility(dem_array=np.zeros((2, 2)))

    def test_upward_ray_is_visible(self):
        site, _ = illumination.sme.get_site_vec(0, 0, 0, 0)
        _, _, up = illumination.directions(0, 0)
        self.sun = site + 1e8 * up
        self.assertIs(self.visibility(), True)

    def test_invalid_sun_vector_raises(self):
        self.sun = [1, 2]
        with self.assertRaisesRegex(ValueError, "finite 3D vector"):
            self.visibility()

    def test_dem_path_is_required_when_dataset_not_supplied(self):
        with self.assertRaisesRegex(ValueError, "dem_path"):
            illumination.check_visibility(0, 0, 0, self.sun)

    def test_filter_returns_each_requested_pixel_once(self):
        self.heights[3, 5] = 100
        self.heights[2, 2] = np.nan
        self.dem.write(self.heights, 1)
        self.save_dem()
        k = illumination.meters_per_degree
        bounds = (-250 / k, -250 / k, 250 / k, 250 / k)
        with patch.object(illumination.sme, "get_sun_vec", return_value=(self.sun, 0)):
            results = list(illumination.IlluminationFilter(0, bounds, self.path))
        self.assertEqual(len(results), 25)
        self.assertEqual(len({(lon, lat) for lon, lat, _ in results}), 25)
        for lon, lat, result in results:
            row, col = self.dem.index(lon * k, lat * k)
            if np.isnan(self.heights[row, col]):
                self.assertIsNone(result)
            else:
                self.assertIs(result, illumination.check_visibility(
                    lon, lat, 0, self.sun, dem=self.dem))

    def test_filter_defaults_to_entire_supplied_dem(self):
        self.save_dem()
        with patch.object(illumination.sme, "get_sun_vec", return_value=(self.sun, 0)):
            results = list(Filters.run_illumination_filter(0, None, self.path))
        self.assertEqual(len(results), 49)

    def test_filter_rejects_bounds_outside_dem(self):
        self.save_dem()
        with self.assertRaisesRegex(ValueError, "outside the DEM"):
            list(illumination.IlluminationFilter(0, (-1, -1, 1, 1), self.path))

    def test_dem_helpers_accept_path(self):
        self.heights[3, 3] = 42
        self.save_dem()
        self.assertEqual(moon_surface_getter.get_dem_value(0, 0, self.path), 42)
        self.assertEqual(moon_surface_getter.get_dem_array(self.path).shape, (7, 7))

    def test_run_illumination_filter_does_not_download_without_permission(self):
        with patch.object(Filters.lola_hs, "download_crop") as download:
            with self.assertRaises(FileNotFoundError):
                Filters.run_illumination_filter(0, (-1, -1, 1, 1), ROOT / "missing-test-dem.tif")
            download.assert_not_called()

    def test_run_illumination_filter_passes_requested_bounds_to_download(self):
        path = ROOT / "missing-test-dem.tif"
        bounds = (-1, 1, 1, 3)
        with patch.object(Filters.lola_hs, "download_crop") as download:
            Filters.run_illumination_filter(0, bounds, path, download=True)
            download.assert_called_once_with(bounds, path)

    def test_coordinates_outside_dem_raise(self):
        with self.assertRaises(ValueError):
            illumination.check_visibility(2, 0, 0, self.sun, dem=self.dem)

    def test_polar_projection_is_rejected(self):
        self.dem.crs = rasterio.crs.CRS.from_epsg(4326)
        with self.assertRaisesRegex(ValueError, "simple-cylindrical"):
            self.visibility()

    def test_sun_vector_uses_site_kilometers(self):
        site, _ = illumination.sme.get_site_vec(0, 0, 0, 0)
        original = illumination.sme.get_sun_vec
        illumination.sme.get_sun_vec = lambda et: (self.sun, 0)
        try:
            result, _ = illumination.sme.get_site2sun_vec(0, 0, 0, 0)
            np.testing.assert_allclose(result, self.sun - site)
        finally:
            illumination.sme.get_sun_vec = original


if __name__ == "__main__":
    unittest.main()
