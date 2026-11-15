"""Example: generate an hourly illumination image series from the repository root."""
import time

import spiceypy as sp
from SMEData.kernel_loaders import load_kernels
from Filters.Sunlight.illumination_filter import IlluminationFilter


def main():
    load_kernels()
    start = sp.str2et("2028-02-08T00:00:00")
    illumination = IlluminationFilter(
        bounds=(-1, -1, 1, 1),  # west, south, east, north; degrees
        et_init=start,
        et_final=start + 3600,
        output_dir="results_over_time",
        pixel_size_m=1000,
        search_dist_m=10000,
        directions=36,
    )
    started = time.monotonic()
    print(illumination.run_over_time())
    print("Elapsed seconds:", time.monotonic() - started)


if __name__ == "__main__":
    main()
