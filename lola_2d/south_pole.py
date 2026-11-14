# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio", "matplotlib", "numpy"]
# ///
"""Plot the lunar south pole from LOLA DEMs in polar stereographic projection.

The image is 1080x720 px by default and the DEM is resampled to exactly the
pixels the map circle covers, so --lat-limit sets the zoom and --width/--height
the detail:
    uv run south_pole.py --lat-limit -40                 # whole cap down to 40°S
    uv run south_pole.py --lat-limit -85                 # zoom on the pole
    uv run south_pole.py --lat-limit -40 --show          # also open a window

Sources (downloaded once to data/raw/, converted to COGs in data/):
  - the polar DEM (--product, default LDEM_75S_240M) covers 75°S to the pole;
  - beyond that, a global LOLA DEM fills the map. The coarsest one that
    matches the map resolution is used: LDEM_4 (7.6 km/px, 4 MB), LDEM_16 (1.9 km/px,
    66 MB) or LDEM_64 (474 m/px, 1 GB).
"""

import argparse
import math
import re
from pathlib import Path
from urllib.request import urlretrieve

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio import shutil as rio_shutil
from matplotlib import patheffects
from matplotlib.colors import LightSource
from matplotlib.patches import Circle
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from rasterio.windows import Window

from render_config import DPI, add_size_args, new_figure

PDS_GDR = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr"
MOON_RADIUS = 1737400.0
# "Moon (2015) - Sphere / Ocentric / South Polar": +proj=stere +lat_0=-90 +lon_0=0 +R=1737400
SOUTH_POLAR_CRS = CRS.from_string("IAU_2015:30135")

# Global simple cylindrical DEMs, coarsest first: (product, meters per pixel)
GLOBAL_PRODUCTS = [("LDEM_4", 7580), ("LDEM_16", 1895), ("LDEM_64", 474)]

# Figure layout in pixels. The map axes are square and the circle fills
# 1/MAP_MARGIN of them; the rest holds the longitude labels and scale bar.
TITLE_PX = 60
EDGE_PX = 10
COLORBAR_PX = 110  # colorbar plus its tick labels
MAP_MARGIN = 1.15

# name: (lat, lon, diameter_km), degrees, east-positive longitude
FEATURES = {
    "Shackleton": (-89.67, 129.78, 21),
    "de Gerlache": (-88.5, -87.1, 32),
    "Shoemaker": (-88.1, 44.9, 51),
    "Haworth": (-87.45, -5.0, 51),
    "Faustini": (-87.3, 77.0, 39),
    "Cabeus": (-85.3, -42.1, 98),
    "Malapert": (-84.9, 12.9, 69),
    "Schrödinger": (-75.0, 132.4, 312),
    "Clavius": (-58.4, -14.4, 231),
    "Tycho": (-43.31, -11.36, 85),
}
# Label offsets in points (default up-right) for features that crowd near the pole.
LABEL_OFFSETS = {"Shackleton": (6, -12), "de Gerlache": (-6, 5), "Cabeus": (-6, 5)}

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"


def latlon_to_xy(lat, lon):
    """South polar stereographic: the pole is (0, 0) and lon 0° points up (+y)."""
    lat, lon = np.radians(lat), np.radians(lon)
    r = 2 * MOON_RADIUS * np.tan((np.pi / 2 + lat) / 2)
    return r * np.sin(lon), r * np.cos(lon)


def stereo_radius(lat: float) -> float:
    return 2 * MOON_RADIUS * math.tan(math.radians(90 + lat) / 2)


def prepare_dem(product: str, folder: str) -> Path:
    """Download a LOLA float DEM from PDS once and cache it as a COG in meters."""
    cog = DATA_DIR / f"{product.lower()}_dem.tif"
    if cog.exists():
        return cog

    raw = DATA_DIR / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for ext in ("LBL", "IMG"):
        name = f"{product}_FLOAT.{ext}"
        if not (raw / name).exists():
            print(f"Downloading {name} (once)...")
            urlretrieve(f"{PDS_GDR}/{folder}/float_img/{name}", raw / name)

    # Convert in row chunks to a tiled GeoTIFF, then to a COG: the global
    # LDEM_64 is 1 GB and must not be loaded into memory at once.
    tmp = cog.with_suffix(".tmp.tif")
    with rasterio.open(raw / f"{product}_FLOAT.LBL") as src:
        profile = src.profile
        profile.update(driver="GTiff", dtype="float32", nodata=np.nan, tiled=True,
                       blockxsize=512, blockysize=512, compress="deflate", BIGTIFF="IF_SAFER")
        with rasterio.open(tmp, "w", **profile) as dst:
            for row in range(0, src.height, 2048):
                window = Window(0, row, src.width, min(2048, src.height - row))
                # Values are kilometers relative to the 1737.4 km reference sphere.
                km = src.read(1, window=window)
                dst.write(np.where(km < -1e30, np.nan, km * 1000).astype("float32"), 1, window=window)
    rio_shutil.copy(tmp, cog, driver="COG", compress="deflate", BIGTIFF="IF_SAFER")
    tmp.unlink()
    print(f"Saved to {cog}")
    return cog


def warp_into(dem: np.ndarray, transform, source: Path) -> None:
    """Reproject source onto the map grid, keeping existing values where it has no data."""
    with rasterio.open(source) as src:
        reproject(
            source=rasterio.band(src, 1), destination=dem,
            src_nodata=np.nan, dst_nodata=np.nan, init_dest_nodata=False,
            dst_transform=transform, dst_crs=SOUTH_POLAR_CRS,
            resampling=Resampling.average,
        )


def build_map(lat_limit: float, res: float, polar_product: str) -> tuple[np.ndarray, list[str]]:
    radius = stereo_radius(lat_limit)
    size = math.ceil(2 * radius / res)
    transform = from_origin(-radius, radius, res, res)
    dem = np.full((size, size), np.nan, dtype="float32")
    sources = []

    polar_limit = -float(re.match(r"LDEM_(\d+)S", polar_product).group(1))
    if lat_limit > polar_limit:
        # The polar DEM doesn't reach the map edge: fill the background from a global DEM.
        product = next((p for p, px in GLOBAL_PRODUCTS if px <= res), GLOBAL_PRODUCTS[-1][0])
        warp_into(dem, transform, prepare_dem(product, "cylindrical"))
        sources.append(product)

    # The polar DEM is drawn on top: it is sharper close to the pole.
    warp_into(dem, transform, prepare_dem(polar_product, "polar"))
    sources.append(polar_product)
    return dem, sources


def lon_label(lon: int) -> str:
    if lon in (0, 180):
        return f"{lon}°"
    return f"{abs(lon)}°{'E' if lon > 0 else 'W'}"


def draw_graticule(ax, lat_limit: float, radius_km: float, clip) -> None:
    style = dict(color="white", lw=0.6, alpha=0.6)
    lon = np.linspace(-180, 180, 361)
    span = 90 + lat_limit
    step = 10 if span > 30 else 5 if span > 10 else 1
    for lat in range(-90 + step, math.ceil(lat_limit), step):
        x, y = latlon_to_xy(lat, lon)
        ax.plot(x / 1000, y / 1000, **style, clip_path=clip)
        lx, ly = latlon_to_xy(lat, 180)
        ax.text(lx / 1000, ly / 1000, f"{abs(lat)}°S", color="white", fontsize=8,
                ha="center", va="bottom", bbox=dict(fc="black", alpha=0.4, lw=0, pad=1))
    for meridian in range(-150, 181, 30):
        x, y = latlon_to_xy(np.array([-90, lat_limit]), meridian)
        ax.plot(x / 1000, y / 1000, **style, clip_path=clip)
        # Longitude labels sit just outside the circular edge.
        a = math.radians(meridian)
        ax.text(1.07 * radius_km * math.sin(a), 1.07 * radius_km * math.cos(a), lon_label(meridian),
                fontsize=9, ha="center", va="center")


def draw_scale_bar(ax, radius_km: float) -> None:
    # Round to a 1/2/5 x 10^n length close to a quarter of the radius.
    target = radius_km / 4
    magnitude = 10 ** math.floor(math.log10(target))
    length = max(m * magnitude for m in (1, 2, 5) if m * magnitude <= target)
    x0, y0 = -1.1 * radius_km, -1.1 * radius_km
    ax.plot([x0, x0 + length], [y0, y0], color="black", lw=3, solid_capstyle="butt")
    ax.text(x0 + length / 2, y0 + 0.02 * radius_km, f"{length:g} km", ha="center", va="bottom", fontsize=9)


def draw_features(ax, lat_limit: float, radius_km: float) -> None:
    for name, (lat, lon, diameter_km) in FEATURES.items():
        # Skip features outside the map or too small to see at this scale.
        if lat > lat_limit or diameter_km < 0.02 * 2 * radius_km:
            continue
        x, y = latlon_to_xy(lat, lon)
        ax.plot(x / 1000, y / 1000, "o", ms=4, mfc="none", mec="white", mew=1)
        dx, dy = LABEL_OFFSETS.get(name, (5, 5))
        ax.annotate(name, (x / 1000, y / 1000), xytext=(dx, dy), textcoords="offset points",
                    ha="right" if dx < 0 else "left", color="white", fontsize=9, fontweight="bold",
                    path_effects=[patheffects.withStroke(linewidth=2.5, foreground="black")])


def map_layout(width: int, height: int) -> tuple[float, float]:
    """Side and left offset, in pixels, of the square map axes."""
    side = min(height - TITLE_PX - EDGE_PX, width - COLORBAR_PX - 2 * EDGE_PX)
    left = (width - side - COLORBAR_PX) / 2
    return side, left


def map_resolution(lat_limit: float, width: int, height: int) -> float:
    """Meters per pixel so that the DEM grid matches the circle's pixels."""
    side, _ = map_layout(width, height)
    return 2 * stereo_radius(lat_limit) / (side / MAP_MARGIN)


def plot_south_pole(dem: np.ndarray, sources: list[str], lat_limit: float, res: float,
                    vert_exag: float, width: int, height: int, show: bool) -> Path:
    filled = np.where(np.isnan(dem), np.nanmean(dem), dem)
    ls = LightSource(azdeg=315, altdeg=35)
    norm = plt.Normalize(np.nanpercentile(dem, 1), np.nanpercentile(dem, 99))
    cmap = plt.cm.cividis
    rgb = ls.shade(filled, cmap=cmap, norm=norm, blend_mode="soft", vert_exag=vert_exag, dx=res, dy=res)
    del filled

    radius_km = stereo_radius(lat_limit) / 1000
    extent = (-radius_km, -radius_km + dem.shape[1] * res / 1000,
              radius_km - dem.shape[0] * res / 1000, radius_km)
    fig = new_figure(width, height)
    side, left = map_layout(width, height)
    ax = fig.add_axes((left / width, EDGE_PX / height, side / width, side / height))
    clip = Circle((0, 0), radius_km, transform=ax.transData)
    ax.imshow(rgb, extent=extent, clip_path=clip)
    ax.add_patch(Circle((0, 0), radius_km, fill=False, color="black", lw=1))
    draw_graticule(ax, lat_limit, radius_km, clip)
    draw_scale_bar(ax, radius_km)
    draw_features(ax, lat_limit, radius_km)

    lim = MAP_MARGIN * radius_km
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.suptitle(f"Lunar south pole, {abs(lat_limit):g}°S to 90°S - polar stereographic, {res:.0f} m/px\n"
                 f"LOLA {' + '.join(sources)}", y=1 - EDGE_PX / height, va="top", fontsize=12)
    cax = fig.add_axes(((left + side + 15) / width, (EDGE_PX + 0.15 * side) / height,
                        15 / width, 0.7 * side / height))
    fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax,
                 label="Elevation relative to 1737.4 km radius (m)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"south_pole_{abs(lat_limit):g}s_{width}x{height}.png"
    fig.savefig(out, dpi=DPI)
    print(f"Figure saved to {out}")
    if show:
        plt.show()
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lat-limit", type=float, default=-75.0, help="outer latitude of the map (e.g. -85, -40)")
    parser.add_argument("--product", default="LDEM_75S_240M",
                        help="LOLA polar DEM on PDS, e.g. LDEM_75S_240M, LDEM_80S_80M, LDEM_85S_20M")
    parser.add_argument("--vert-exag", type=float, default=2.0, help="vertical exaggeration of the terrain")
    parser.add_argument("--show", action="store_true", help="open an interactive window after saving")
    add_size_args(parser)
    args = parser.parse_args()

    if not -90 < args.lat_limit <= 0:
        parser.error("--lat-limit must be greater than -90 (the pole itself is a single point) and at most 0 (the equator)")
    res = map_resolution(args.lat_limit, args.width, args.height)
    print(f"Map: {abs(args.lat_limit):g}°S to the pole, {res:.0f} m/px, image {args.width}x{args.height} px")

    dem, sources = build_map(args.lat_limit, res, args.product)
    plot_south_pole(dem, sources, args.lat_limit, res, args.vert_exag, args.width, args.height, args.show)


if __name__ == "__main__":
    main()
