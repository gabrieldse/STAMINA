import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr
from rasterio.crs import CRS
from rasterio.transform import from_origin

from Filters.Sunlight.dem_geometry import load_regional_terrain, regional_sun_angles
from Filters.Sunlight.illumination_funcs import complete_ray_coverage


class RegionalIlluminationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "dem.tif"
        self.crs = CRS.from_proj4("+proj=eqc +R=1737400 +units=m +no_defs")

    def write_dem(self, values, *, unit=None, scale=1, offset=0, crs=None):
        with rasterio.open(
            self.path, "w", driver="GTiff", width=values.shape[1], height=values.shape[0],
            count=1, dtype="float32", crs=crs or self.crs,
            transform=from_origin(-2500, 2500, 1000, 1000), nodata=-9999,
        ) as dataset:
            dataset.write(values.astype(np.float32), 1)
            dataset.scales = (scale,)
            dataset.offsets = (offset,)
            if unit is not None:
                dataset.set_band_unit(1, unit)

    def test_explicit_meters_and_kilometers_are_equivalent(self):
        values = np.full((5, 5), 2.0)
        self.write_dem(values)
        dem_m, _ = load_regional_terrain(self.path, 1000, 4, "m")
        dem_km, _ = load_regional_terrain(self.path, 1000, 4, "km")
        np.testing.assert_allclose(dem_km.values, dem_m.values * 1000, equal_nan=True)
        self.assertAlmostEqual(float(np.nanmedian(dem_m.values)), 2.0)

    def test_metadata_units_scale_offset_and_nodata(self):
        values = np.full((5, 5), 2.0)
        values[2, 2] = -9999
        self.write_dem(values, unit="m", scale=2, offset=3)
        dem, footprint = load_regional_terrain(self.path, 1000, 4)
        self.assertAlmostEqual(float(np.nanmedian(dem.values)), 7.0)
        self.assertTrue(np.any(footprint & ~np.isfinite(dem.values)))

    def test_missing_units_must_be_supplied(self):
        self.write_dem(np.zeros((5, 5)))
        with self.assertRaisesRegex(ValueError, "elevation_units"):
            load_regional_terrain(self.path, 1000, 4)

    def test_ray_coverage_marks_missing_cells_and_dem_edges_unknown(self):
        terrain = np.zeros((5, 5), dtype=np.float32)
        terrain[2, 3] = np.nan
        indices = np.zeros((5, 5), dtype=np.int64)
        complete = complete_ray_coverage(terrain, indices, 4, 1, 2)
        self.assertFalse(complete[2, 1])
        self.assertFalse(complete[1, 4])
        self.assertTrue(complete[1, 1])

    def test_earth_crs_is_rejected(self):
        self.write_dem(np.zeros((5, 5)), unit="m", crs=CRS.from_epsg(3857))
        with self.assertRaisesRegex(ValueError, "lunar"):
            load_regional_terrain(self.path, 1000, 4)

    def test_sun_directions_on_equatorial_grid(self):
        crs = CRS.from_proj4("+proj=aeqd +lat_0=0 +lon_0=0 +R=1737400 +units=m")
        dem = xr.DataArray(np.zeros((1, 1)), dims=("y", "x"),
                           coords={"y": [0.0], "x": [0.0]})
        dem.rio.write_crs(crs, inplace=True)
        _, east = regional_sun_angles(dem, np.array([1737.4, 1e8, 0]))
        _, north = regional_sun_angles(dem, np.array([1737.4, 0, 1e8]))
        self.assertAlmostEqual(float(east[0, 0]), 0, places=4)
        self.assertAlmostEqual(float(north[0, 0]), 90, places=4)

    def test_sun_angle_on_polar_grid(self):
        crs = CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m")
        dem = xr.DataArray(np.zeros((1, 1)), dims=("y", "x"),
                           coords={"y": [50000.0], "x": [0.0]})
        dem.rio.write_crs(crs, inplace=True)
        _, east_angle = regional_sun_angles(dem, np.array([0, 1e8, 0]))
        _, north_angle = regional_sun_angles(dem, np.array([0, 0, 1e8]))
        self.assertAlmostEqual(float((east_angle[0, 0] + 180) % 360 - 180), 0, places=4)
        self.assertAlmostEqual(float(north_angle[0, 0]), 90, places=4)


if __name__ == "__main__":
    unittest.main()
