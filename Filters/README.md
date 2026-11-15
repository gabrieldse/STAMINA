# Lunar illumination tools

This project generates terrain-aware illumination images for a lunar region,
including an hourly series that can drive a time slider. It shares NASA SPICE
kernels with the web explorer, and can be used independently of the website.

Install the Python dependencies using the [root setup guide](../README.md).
Run Python from the repository root so package imports and bundled kernels work.

## Generate an illumination image

```python
import spiceypy as sp
from SMEData.kernel_loaders import load_kernels
from Filters.Sunlight.illumination_filter import IlluminationFilter

load_kernels()
start = sp.str2et("2028-02-08T00:00:00")
image_filter = IlluminationFilter(
    bounds=(-1, -1, 1, 1),  # west, south, east, north; degrees
    et_init=start,
    et_final=start + 3600,
    output_dir="results/illumination",
    pixel_size_m=1000,
    search_dist_m=10000,
    directions=36,
)
base, overlay, preview = image_filter.calculate_at_time(start)
print(base, overlay, preview)
```

With `bounds`, the first calculation downloads a buffered LOLA terrain crop
from NASA. It needs internet access and can take time. Terrain downloads are
cached in the output directory. A supplied `dem_path` reuses a local lunar DEM;
set `elevation_units="m"` or `"km"` when the file has no vertical unit metadata.
Bounds use east-positive longitude and support a dateline crossing when west
is greater than east. The example uses a small equatorial region to keep the
download manageable; choose coordinates for the region you want to study.

For hourly images over the configured interval:

```python
masks = image_filter.run_over_time()
print(masks)
```

This writes timestamped PNG masks and `illumination_times.json`, whose samples
contain UTC, SPICE ephemeris time, and filenames. The end is included when it
falls on an hourly sample. Terrain horizons are prepared once and reused.
`nearest_mask_filename(samples, utc)` selects a nearby saved image for a slider.
Repeated calculations overwrite matching filenames; choose a new output folder
to preserve a different run. PNGs do not contain geographic metadata.

## Modules and limits

| Module | Purpose |
| --- | --- |
| `Sunlight/illumination_filter.py` | Main image-generation class and hourly index lookup |
| `Sunlight/illumination_funcs.py` | Solshade horizon preparation and image rendering |
| `Sunlight/dem_geometry.py` | Lunar projection, DEM units, bounded regional grids |
| `Sunlight/lola_download.py` | Buffered downloads and cached DEM validation |
| `Sunlight/illumination.py` | Reference ray tracer for simple-cylindrical DEMs |
| `Sunlight/overlay.py`, `filters.py` | Reference-ray-tracer overlay and iterator helpers |
| `tests/` | Synthetic DEM, bounds, coverage, image, and time-series tests |

Yellow pixels indicate illumination; gray-blue pixels indicate unknown terrain
coverage; blocked pixels are transparent in the overlay. Results approximate
the Sun's center and depend on terrain resolution, horizon directions and search
distance. Missing terrain must remain unknown. This standalone Solshade model
and the web API's visibility model are separate implementations; see
[backend methods](../backend/README.md) for the explorer's assumptions.

Run the standalone tests without NASA downloads:

```bash
python -m unittest discover -s Filters/tests
```
