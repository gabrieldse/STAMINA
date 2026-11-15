import spiceypy as sp
from Filters.Sunlight.illumination_filter import IlluminationFilter
import time


illumination = IlluminationFilter(
    bounds=(-10, -10, 10, 10),  # west, south, east, north
    et_init=sp.str2et("2032-11-1T00:00:00"),
    et_final=sp.str2et("2032-11-26T12:00:00"),
    output_dir="results_over_time",
    pixel_size_m=500,
    search_dist_m=10000,
    directions=36,
)

start_time = time.time()
print(illumination.run_over_time())
print("Elapsed time:", time.time() - start_time)