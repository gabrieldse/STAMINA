# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio", "matplotlib", "numpy"]
# ///
"""Crop the global LOLA DEM (118 m/px) and plot a 2D hillshade.

Usage:
    uv run lola_hillshade.py                 # Tycho (default)
    uv run lola_hillshade.py --region copernicus
    uv run lola_hillshade.py --bounds -15 -46 -7.5 -40.5   # lon_min lat_min lon_max lat_max

The crop is saved to data/<name>_dem.tif (COG). Subsequent runs read it from
disk instead of downloading it again.
"""

import argparse
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LightSource
from rasterio.windows import Window, from_bounds

# Global LOLA DEM, simple cylindrical (equirectangular), int16 with a 0.5 m scale.
# Not a COG: 8.5 GB stored in 1-row strips, so remote reads are slow.
LOLA_URL = (
    "/vsicurl/https://planetarymaps.usgs.gov/mosaic/"
    "Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif"
)
MOON_RADIUS = 1737400.0
METERS_PER_DEGREE = math.pi * MOON_RADIUS / 180

# lon_min, lat_min, lon_max, lat_max (degrees; east-positive longitude, -180..180)
REGIONS = {
    "tycho": (-15.0, -46.0, -7.5, -40.5),
    "copernicus": (-24.0, 7.0, -16.0, 12.5),
    "apollo15": (1.5, 24.5, 5.5, 27.5),  # Hadley Rille
}

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"

GDAL_ENV = {"CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"}


def _read_rows(window: Window) -> np.ndarray:
    # Each thread opens its own dataset: GDAL handles aren't thread-safe.
    with rasterio.Env(**GDAL_ENV), rasterio.open(LOLA_URL) as src:
        return src.read(1, window=window)


def download_crop(bounds: tuple[float, float, float, float], dest: Path, workers: int = 16) -> None:
    lon_min, lat_min, lon_max, lat_max = bounds
    with rasterio.Env(**GDAL_ENV), rasterio.open(LOLA_URL) as src:
        window = from_bounds(
            lon_min * METERS_PER_DEGREE, lat_min * METERS_PER_DEGREE,
            lon_max * METERS_PER_DEGREE, lat_max * METERS_PER_DEGREE,
            src.transform,
        ).round_offsets().round_lengths()
        profile = src.profile
        transform = src.window_transform(window)
        scale = src.scales[0]
        nodata = src.nodata

    # Split the crop into row chunks and download them in parallel.
    step = math.ceil(window.height / (workers * 4))
    chunks = [
        Window(window.col_off, window.row_off + r, window.width, min(step, window.height - r))
        for r in range(0, window.height, step)
    ]
    print(f"Downloading {window.width}x{window.height} px in {len(chunks)} chunks...")
    with ThreadPoolExecutor(workers) as pool:
        raw = np.vstack(list(pool.map(_read_rows, chunks)))

    heights = np.where(raw == nodata, np.nan, raw * scale).astype("float32")

    profile.update(
        driver="COG", dtype="float32", nodata=np.nan, compress="deflate",
        width=window.width, height=window.height, transform=transform,
    )
    for key in ("blockxsize", "blockysize", "tiled", "interleave"):
        profile.pop(key, None)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dest, "w", **profile) as dst:
        dst.write(heights, 1)
    print(f"Saved to {dest}")


def plot_hillshade(dem_path: Path, title: str, out: Path, vert_exag: float) -> None:
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        b = src.bounds
        res = src.res[0]

    lon_min, lon_max = b.left / METERS_PER_DEGREE, b.right / METERS_PER_DEGREE
    lat_min, lat_max = b.bottom / METERS_PER_DEGREE, b.top / METERS_PER_DEGREE
    # In equirectangular, one x pixel covers less ground as latitude increases.
    coslat = math.cos(math.radians((lat_min + lat_max) / 2))

    filled = np.where(np.isnan(dem), np.nanmean(dem), dem)
    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(filled, vert_exag=vert_exag, dx=res * coslat, dy=res)
    norm = plt.Normalize(np.nanpercentile(dem, 1), np.nanpercentile(dem, 99))
    rgb = ls.shade(filled, cmap=plt.cm.cividis, norm=norm, blend_mode="soft",
                   vert_exag=vert_exag, dx=res * coslat, dy=res)

    extent = (lon_min, lon_max, lat_min, lat_max)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5), constrained_layout=True)
    axes[0].imshow(hs, cmap="gray", extent=extent, aspect=1 / coslat)
    axes[0].set_title("Hillshade")
    axes[1].imshow(rgb, extent=extent, aspect=1 / coslat)
    axes[1].set_title("Elevation + hillshade")
    fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=plt.cm.cividis), ax=axes[1],
                 label="Elevation relative to 1737.4 km radius (m)", shrink=0.85)
    for ax in axes:
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
    fig.suptitle(f"{title} - LOLA DEM 118 m/px")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"Figure saved to {out}")
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", choices=REGIONS, default="tycho")
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
    parser.add_argument("--vert-exag", type=float, default=2.0, help="vertical exaggeration of the terrain")
    parser.add_argument("--refresh", action="store_true", help="download again even if a cached crop exists")
    args = parser.parse_args()

    if args.bounds:
        bounds, name = tuple(args.bounds), "custom_" + "_".join(f"{v:g}" for v in args.bounds)
    else:
        bounds, name = REGIONS[args.region], args.region

    dem_path = DATA_DIR / f"{name}_dem.tif"
    if args.refresh or not dem_path.exists():
        download_crop(bounds, dem_path)
    plot_hillshade(dem_path, name.capitalize(), OUT_DIR / f"{name}_hillshade.png", args.vert_exag)


if __name__ == "__main__":
    main()
