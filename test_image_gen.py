import spiceypy as sp
from Filters.Sunlight.illumination_filter import IlluminationFilter

illumination = IlluminationFilter(
    bounds=(-10, -10, 10, 10),  # west, south, east, north
    et_init=sp.str2et("2026-11-18T12:00:00"),
    et_final=sp.str2et("2026-11-19T12:00:00"),
    output_dir="results_over_time",
    pixel_size_m=500,
    search_dist_m=10000,
    directions=36,
)

print(illumination.run_over_time())