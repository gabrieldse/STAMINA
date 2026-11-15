import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import matplotlib.image as mpimg
import numpy as np
import rasterio
from rasterio.transform import from_origin

# Support running this file directly as well as running it with unittest -m.
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from Filters.Sunlight.illumination_filter import IlluminationFilter, nearest_mask_filename
from Filters.Sunlight import illumination_funcs


def write_dem(path):
    with rasterio.open(
        path, "w", driver="GTiff", width=12, height=12,
        count=1, dtype="float32", crs=illumination_funcs.POLAR_CRS,
        transform=from_origin(-600000, 600000, 100000, 100000),
    ) as dem:
        dem.write(np.zeros((12, 12), dtype=np.float32), 1)


class IlluminationFilterClassTests(unittest.TestCase):
    def test_hourly_run_saves_separate_masks_and_reuses_horizons(self):
        with tempfile.TemporaryDirectory() as tmp:
            dem_path = Path(tmp) / "terrain.tif"
            write_dem(dem_path)
            output_dir = Path(tmp) / "hourly"
            start = illumination_funcs.sp.str2et("2026-11-18T12:00:00")
            instance = IlluminationFilter(
                dem_path=dem_path, et_init=start, et_final=start + 7300, output_dir=output_dir,
                pixel_size_m=100000, search_dist_m=100000, directions=4,
                elevation_units="m",
            )
            with patch.object(illumination_funcs.sme, "get_sun_vec",
                              return_value=(np.array([1e8, 0, 0]), 0)) as sun, \
                 patch.object(illumination_funcs, "compute_horizon_map",
                              wraps=illumination_funcs.compute_horizon_map) as compute:
                masks = instance.run_over_time()
                self.assertEqual([call.args[0] for call in sun.call_args_list],
                                 [start, start + 3600, start + 7200])
                self.assertEqual(compute.call_count, 1)
                self.assertEqual(masks, [
                    output_dir / f"illumination_2026-11-18T{hour:02d}-00-00.000Z.png"
                    for hour in (12, 13, 14)
                ])
                self.assertEqual(set(output_dir.rglob("*.png")), set(masks))
                with (output_dir / "illumination_times.json").open(encoding="utf-8") as index:
                    samples = json.load(index)["samples"]
                self.assertEqual([sample["filename"] for sample in samples],
                                 [path.name for path in masks])
                self.assertEqual([sample["et"] for sample in samples],
                                 [start, start + 3600, start + 7200])
                for utc, expected in (("2026-11-18T11:00:00", masks[0]),
                                      ("2026-11-18T12:29:00", masks[0]),
                                      ("2026-11-18T12:31:00", masks[1]),
                                      ("2026-11-18T15:00:00", masks[2])):
                    self.assertEqual(output_dir / nearest_mask_filename(samples, utc), expected)
                with patch.object(illumination_funcs.sp, "str2et", return_value=start + 1800):
                    self.assertEqual(nearest_mask_filename(samples, "unused"), masks[0].name)
                full_images = instance.calculate_at_time(start, Path(tmp) / "single")
                self.assertEqual(compute.call_count, 1)
                np.testing.assert_array_equal(mpimg.imread(masks[0]), mpimg.imread(full_images[1]))
                self.assertTrue(all(path.exists() for path in full_images))

    def test_hourly_run_validates_range_and_includes_single_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = IlluminationFilter(et_init=10, et_final=10, output_dir=tmp)
            with patch.object(instance, "calculate_at_time", return_value="mask") as calculate:
                self.assertEqual(instance.run_over_time(), ["mask"])
                self.assertEqual(calculate.call_args.args[0], 10)
                self.assertTrue(calculate.call_args.kwargs["mask_only"])
                instance.et_final = 3609.999999
                calculate.reset_mock()
                self.assertEqual(instance.run_over_time(), ["mask", "mask"])
                self.assertEqual([call.args[0] for call in calculate.call_args_list], [10, 3609.999999])
                instance.et_final = 3609.98
                calculate.reset_mock()
                self.assertEqual(instance.run_over_time(), ["mask"])
                for start, end in [(10, 9), (float("nan"), 10), (10, float("inf"))]:
                    instance.et_init, instance.et_final = start, end
                    with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                        instance.run_over_time()
                self.assertEqual(calculate.call_count, 1)

    def test_constructor_stores_configuration(self):
        filter_instance = IlluminationFilter(
            "terrain.lbl", 123.0, "output",
            pixel_size_m=2000, search_dist_m=120000, directions=36, elevation_units="m",
        )

        self.assertEqual(filter_instance.dem_path, "terrain.lbl")
        self.assertEqual(filter_instance.et, 123.0)
        self.assertIsNone(filter_instance.bounds)
        self.assertEqual(filter_instance.output_dir, "output")
        self.assertEqual(filter_instance.pixel_size_m, 2000)
        self.assertEqual(filter_instance.search_dist_m, 120000)
        self.assertEqual(filter_instance.directions, 36)
        self.assertEqual(filter_instance.elevation_units, "m")

    def test_run_passes_settings_to_calculation_and_returns_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            dem_path = Path(tmp) / "terrain.tif"
            write_dem(dem_path)
            output_dir = Path(tmp) / "output"
            expected_paths = (
                output_dir / "polar_base.png",
                output_dir / "polar_illumination.png",
                output_dir / "polar_preview.png",
            )
            filter_instance = IlluminationFilter(
                dem_path, 123.0, output_dir,
                pixel_size_m=2000, search_dist_m=120000, directions=36, elevation_units="m",
                bounds=None,
            )
            prepared = SimpleNamespace(horizons="cached horizons")
            with patch.object(illumination_funcs, "prepare_terrain", return_value=prepared) as prepare, \
                 patch.object(illumination_funcs, "render_at_time", return_value=expected_paths) as render:
                result = filter_instance.run()

            prepare.assert_called_once_with(
                dem_path,
                pixel_size_m=2000, search_dist_m=120000, directions=36, elevation_units="m",
                bounds=None,
            )
            render.assert_called_once_with(prepared, 123.0, output_dir)
            self.assertIs(filter_instance.prepared_terrain, prepared)
            self.assertEqual(filter_instance.horizons, "cached horizons")
            self.assertEqual(result, expected_paths)

    def test_missing_dem_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = Path(tmp) / "missing.lbl"
            filter_instance = IlluminationFilter(missing_path, 123.0, tmp)
            with self.assertRaises(FileNotFoundError):
                filter_instance.run()

    def test_custom_dem_with_bounds_is_passed_to_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terrain.tif"
            write_dem(path)
            filter_instance = IlluminationFilter(path, 123.0, tmp, bounds=(-1, -89, 1, -88))
            with patch.object(illumination_funcs, "prepare_terrain",
                              return_value=SimpleNamespace(horizons=None)) as calculate, \
                 patch.object(illumination_funcs, "render_at_time"):
                filter_instance.run()
            self.assertEqual(calculate.call_args.kwargs["bounds"], (-1.0, -89.0, 1.0, -88.0))

    def test_run_creates_images_with_real_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            dem_path = Path(tmp) / "terrain.tif"
            write_dem(dem_path)
            filter_instance = IlluminationFilter(
                dem_path, 0, tmp, pixel_size_m=100000,
                search_dist_m=100000, directions=4, elevation_units="m",
            )
            with patch.object(illumination_funcs.sme, "get_sun_vec",
                              return_value=(np.array([1e8, 0, 0]), 0)):
                paths = filter_instance.run()
            self.assertEqual(len(paths), 3)
            images = [mpimg.imread(path) for path in paths]
            self.assertTrue(all(image.shape == images[0].shape for image in images))
            self.assertEqual(images[0].shape[-1], 4)
            self.assertTrue(np.any(images[1][:, :, 3] > 0))

    def test_multiple_times_reuse_horizons_and_match_fresh_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            dem_path = Path(tmp) / "terrain.tif"
            write_dem(dem_path)
            instance = IlluminationFilter(
                dem_path, 0, Path(tmp) / "first", pixel_size_m=100000,
                search_dist_m=100000, directions=4, elevation_units="m",
            )
            sun_vectors = {
                0: (np.array([1e8, 0, 0]), 0),
                1: (np.array([-1e8, 0, 0]), 0),
            }
            with patch.object(illumination_funcs.sme, "get_sun_vec",
                              side_effect=lambda et: sun_vectors[et]), \
                 patch.object(illumination_funcs, "compute_horizon_map",
                              wraps=illumination_funcs.compute_horizon_map) as compute, \
                 patch.object(illumination_funcs, "complete_ray_coverage",
                              wraps=illumination_funcs.complete_ray_coverage) as coverage:
                first = instance.run()
                second = instance.calculate_at_time(1, Path(tmp) / "second")
                self.assertEqual(compute.call_count, 1)
                self.assertEqual(coverage.call_count, 2)
                first_image = mpimg.imread(first[1])
                second_image = mpimg.imread(second[1])
                self.assertFalse(np.array_equal(first_image, second_image))
                fresh = illumination_funcs.Illumination_filter(
                    dem_path, 1, Path(tmp) / "fresh", pixel_size_m=100000,
                    search_dist_m=100000, directions=4, elevation_units="m",
                )
                np.testing.assert_array_equal(second_image, mpimg.imread(fresh[1]))
                self.assertEqual(compute.call_count, 2)

    def test_terrain_settings_and_source_change_rebuild_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terrain.tif"
            write_dem(path)
            instance = IlluminationFilter(path, 0, tmp, pixel_size_m=100000,
                                          search_dist_m=100000, directions=4,
                                          elevation_units="m")
            with patch.object(illumination_funcs, "prepare_terrain",
                              side_effect=lambda *a, **k: SimpleNamespace(horizons=object())) as prepare:
                instance.prepare()
                instance.et = 10
                instance.prepare()
                self.assertEqual(prepare.call_count, 1)
                for name, value in (("pixel_size_m", 110000),
                                    ("search_dist_m", 110000),
                                    ("directions", 5),
                                    ("elevation_units", "km"),
                                    ("bounds", (-1, -89, 1, -88))):
                    setattr(instance, name, value)
                    instance.prepare()
                self.assertEqual(prepare.call_count, 6)
                with path.open("ab") as stream:
                    stream.write(b"changed")
                instance.prepare()
                self.assertEqual(prepare.call_count, 7)
                instance.clear_prepared()
                self.assertIsNone(instance.prepared_terrain)
                self.assertIsNone(instance.horizons)
                instance.prepare()
                self.assertEqual(prepare.call_count, 8)

    def test_source_changing_during_preparation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terrain.tif"
            write_dem(path)
            instance = IlluminationFilter(path, 0, tmp, pixel_size_m=100000,
                                          search_dist_m=100000, directions=4,
                                          elevation_units="m")

            def change_source(*args, **kwargs):
                with path.open("ab") as stream:
                    stream.write(b"changed")
                return SimpleNamespace(horizons=object())

            with patch.object(illumination_funcs, "prepare_terrain", side_effect=change_source):
                with self.assertRaisesRegex(RuntimeError, "changed during"):
                    instance.prepare()
            self.assertIsNone(instance.prepared_terrain)

    def test_run_uses_updated_time_without_repreparing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terrain.tif"
            write_dem(path)
            instance = IlluminationFilter(path, 0, tmp, pixel_size_m=100000,
                                          search_dist_m=100000, directions=4,
                                          elevation_units="m")
            prepared = SimpleNamespace(horizons=object())
            with patch.object(illumination_funcs, "prepare_terrain", return_value=prepared) as prepare, \
                 patch.object(illumination_funcs, "render_at_time") as render:
                instance.run()
                instance.et = 20
                instance.run()
            self.assertEqual(prepare.call_count, 1)
            self.assertEqual([call.args[1] for call in render.call_args_list], [0, 20])


if __name__ == "__main__":
    #unittest.main()

    dem_path = ROOT / "lola_2d" / "data" / "tycho_1_1_1_3.tif"
    output_dir = ROOT / "lola_2d" / "output"
    illum_filter = IlluminationFilter(
        dem_path, 0, output_dir, elevation_units="m",
        pixel_size_m=2000, search_dist_m=10000, directions=90,
    )

    print(*illum_filter.run(), sep="\n")