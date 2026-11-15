import spiceypy as sp
from Filters.Sunlight.illumination_filter import IlluminationFilter

illumination = IlluminationFilter(
    bounds=(-10, -10, 10, 10),  # west, south, east, north
    et=sp.str2et("2026-11-18T12:00:00"),
    output_dir="results",
    pixel_size_m=500,
    search_dist_m=10000,
    directions=90,
)

print(illumination.run())