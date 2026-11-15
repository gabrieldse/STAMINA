import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib.image as mpimg
import numpy as np
import rasterio
import xarray as xr
from rasterio.transform import from_origin

from Filters.Sunlight import illumination_funcs


class IlluminationPolarOutputTests(unittest.TestCase):
    def test_illuminated_region_is_filled_and_blocked_pixels_transparent(self):
        coords = np.arange(-450000, 500000, 100000)
        dem = xr.DataArray(
            np.zeros((10, 10), dtype=np.float32), dims=("y", "x"),
            coords={"x": coords, "y": coords[::-1]},
        )
        horizon = xr.DataArray(np.zeros((4, 10, 10), dtype=np.float32))
        elevation = np.full((10, 10), -1.0)
        elevation[3:7, 3:7] = 10
        angle = np.zeros((10, 10))
        coverage = np.ones((10, 10), dtype=bool)
        coverage[2, 3] = False

        with tempfile.TemporaryDirectory() as tmp:
            footprint = np.zeros((10, 10), dtype=bool)
            footprint[1:-1, 1:-1] = True
            with patch.object(illumination_funcs, "load_regional_terrain", return_value=(dem, footprint)), \
                 patch.object(illumination_funcs, "compute_horizon_map", return_value=horizon), \
                 patch.object(illumination_funcs.sme, "get_sun_vec", return_value=(np.zeros(3), 0)), \
                 patch.object(illumination_funcs, "regional_sun_angles", return_value=(elevation, angle)), \
                 patch.object(illumination_funcs, "complete_ray_coverage", return_value=coverage):
                _, overlay_path, preview_path = illumination_funcs.Illumination_filter(
                    "unused", 0, tmp, pixel_size_m=100000,
                    search_dist_m=100000, directions=4,
                )
            overlay = mpimg.imread(overlay_path)
            preview = mpimg.imread(preview_path)

        expected_visible = np.zeros((10, 10), dtype=bool)
        expected_visible[3:7, 3:7] = True
        yellow = np.array([255, 220, 0, 160]) / 255
        actual_visible = np.all(np.isclose(overlay, yellow), axis=-1)
        np.testing.assert_array_equal(actual_visible, expected_visible)
        np.testing.assert_allclose(overlay[4, 4], yellow)
        np.testing.assert_array_equal(overlay[2, 4], np.zeros(4))
        np.testing.assert_allclose(overlay[2, 3], np.array([100, 130, 160, 160]) / 255)
        self.assertEqual(preview[4, 4, 3], 1)

    def test_overlay_colors_and_crops_buffer(self):
        coords = np.arange(-500000, 600000, 200000)
        dem = xr.DataArray(
            np.zeros((6, 6), dtype=np.float32), dims=("y", "x"),
            coords={"x": coords, "y": coords[::-1]},
        )
        horizon = np.zeros((4, 6, 6), dtype=np.float32)
        horizon[1, 2, 2] = 50
        elevation = np.full((6, 6), 10.0)
        elevation[2, 3] = -1
        angle = np.zeros((6, 6))
        angle[2, 2] = 89
        angle[3, 3] = np.nan
        coverage = np.ones((6, 6), dtype=bool)
        coverage[3, 2] = False

        with tempfile.TemporaryDirectory() as tmp:
            footprint = np.zeros((6, 6), dtype=bool)
            footprint[1:-1, 1:-1] = True
            with patch.object(illumination_funcs, "load_regional_terrain", return_value=(dem, footprint)), \
                 patch.object(illumination_funcs, "compute_horizon_map", return_value=xr.DataArray(horizon)), \
                 patch.object(illumination_funcs.sme, "get_sun_vec", return_value=(np.zeros(3), 0)), \
                 patch.object(illumination_funcs, "regional_sun_angles", return_value=(elevation, angle)), \
                 patch.object(illumination_funcs, "complete_ray_coverage", return_value=coverage):
                paths = illumination_funcs.Illumination_filter(
                    "unused", 0, tmp, pixel_size_m=200000,
                    search_dist_m=200000, directions=4,
                )
            base, overlay, preview = (mpimg.imread(path) for path in paths)

        self.assertEqual(base.shape, (6, 6, 4))
        self.assertEqual(overlay.shape, base.shape)
        self.assertEqual(preview.shape, base.shape)
        np.testing.assert_allclose(overlay[2, 2], np.array([255, 220, 0, 160]) / 255)
        np.testing.assert_array_equal(overlay[2, 3], np.zeros(4))
        np.testing.assert_allclose(overlay[3, 2], np.array([100, 130, 160, 160]) / 255)
        np.testing.assert_allclose(overlay[3, 3], np.array([100, 130, 160, 160]) / 255)
        np.testing.assert_array_equal(overlay[0, 0], np.zeros(4))
        self.assertEqual(preview[2, 2, 3], 1)

    def test_real_horizons_save_matching_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terrain.tif"
            with rasterio.open(
                path, "w", driver="GTiff", width=12, height=12,
                count=1, dtype="float32", crs=illumination_funcs.POLAR_CRS,
                transform=from_origin(-600000, 600000, 100000, 100000),
            ) as dem:
                dem.write(np.zeros((12, 12), dtype=np.float32), 1)
            with patch.object(illumination_funcs.sme, "get_sun_vec",
                              return_value=(np.array([1e8, 0, 0]), 0)):
                paths = illumination_funcs.Illumination_filter(
                    path, 0, tmp, pixel_size_m=100000,
                    search_dist_m=100000, directions=4, elevation_units="m",
                )
            images = [mpimg.imread(path) for path in paths]
            self.assertTrue(all(image.shape == images[0].shape for image in images))
            self.assertEqual(images[0].shape[-1], 4)
            self.assertTrue(np.any(images[1][:, :, 3] > 0))


if __name__ == "__main__":
    unittest.main()
