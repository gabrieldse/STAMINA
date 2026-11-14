import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib.image as mpimg
import numpy as np
import rasterio
import xarray as xr
from rasterio.transform import from_origin
from solshade.terrain import compute_horizon_map

from Filters.Sunlight.solshade_polar import (
    POLAR_CRS, complete_ray_coverage, create_preview, polar_sun_angles,
)


class SolshadePolarTests(unittest.TestCase):
    def test_solshade_samples_east_at_zero_degrees(self):
        terrain = np.zeros((11, 11), dtype=np.float32)
        terrain[5, 7] = 100
        dem = xr.DataArray(terrain, dims=("y", "x"),
                           coords={"y": -np.arange(11) * 100,
                                   "x": np.arange(11) * 100})
        dem.rio.write_crs(POLAR_CRS, inplace=True)
        dem.rio.write_transform(from_origin(-50, 50, 100, 100), inplace=True)
        horizon = compute_horizon_map(
            dem, n_directions=4, max_distance=300, step=100,
            chunk_size=11, n_jobs=1, progress=False,
        )
        self.assertAlmostEqual(float(horizon.values[0, 5, 5]), 26.565, places=2)
        self.assertEqual(float(horizon.values[1, 5, 5]), 0)

    def test_local_east_and_north_map_to_polar_grid(self):
        dem = xr.DataArray(np.zeros((1, 1)), dims=("y", "x"),
                           coords={"y": [10000.0], "x": [0.0]})
        _, east_angle = polar_sun_angles(dem, np.array([0, 1e8, 0]))
        _, north_angle = polar_sun_angles(dem, np.array([0, 0, 1e8]))
        self.assertAlmostEqual(float(east_angle[0, 0]), 0, places=5)
        self.assertAlmostEqual(float(north_angle[0, 0]), 90, places=5)

    def test_coverage_marks_missing_cells_and_grid_edges(self):
        terrain = np.zeros((7, 7), dtype=np.float32)
        terrain[3, 5] = np.nan
        directions = np.zeros((7, 7), dtype=int)
        complete = complete_ray_coverage(terrain, directions, 4, 1, 2)
        self.assertFalse(complete[3, 3])
        self.assertFalse(complete[1, 5])
        self.assertTrue(complete[1, 2])

    def test_preview_uses_matching_base_and_overlay_grids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terrain.tif"
            with rasterio.open(
                path, "w", driver="GTiff", width=12, height=12,
                count=1, dtype="float32", crs=POLAR_CRS,
                transform=from_origin(-600000, 600000, 100000, 100000),
            ) as dem:
                dem.write(np.zeros((12, 12), dtype=np.float32), 1)
            with patch("Filters.Sunlight.solshade_polar.sme.get_sun_vec",
                       return_value=(np.array([1e8, 0, 0]), 0)):
                base, overlay = create_preview(
                    path, 0, tmp, resolution_m=100000,
                    search_distance_m=100000, directions=4,
                )
            base_pixels = mpimg.imread(base)
            overlay_pixels = mpimg.imread(overlay)
            preview_pixels = mpimg.imread(Path(tmp) / "polar_preview.png")
            self.assertEqual(base_pixels.shape, (8, 8, 4))
            self.assertEqual(overlay_pixels.shape, base_pixels.shape)
            self.assertEqual(preview_pixels.shape, base_pixels.shape)
            self.assertTrue(np.any(overlay_pixels[:, :, 3] > 0))
            self.assertEqual(overlay_pixels[0, 0, 3], 0)


if __name__ == "__main__":
    unittest.main()
