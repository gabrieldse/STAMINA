# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio", "matplotlib", "numpy"]
# ///
"""Map Diviner south polar surface temperatures (80°S to the pole) side by side.

Uses the Williams et al. (2019) season summaries hosted by NASA Moon Trek:
Float32 GeoTIFFs at 240 m in south polar stereographic, 26 MB each, downloaded
once to data/diviner/.

    uv run diviner_maps.py                                  # summer max vs winter min
    uv run diviner_maps.py --layers summer_avg winter_avg
    uv run diviner_maps.py --layers summer_amplitude --width 720

Layers: {summer,winter}_{avg,min,max,amplitude}.
Summer max below 110 K marks cold traps where water ice is stable; winter min
is the coldest a lander would face.
"""

import argparse
import math
from pathlib import Path
from urllib.request import urlretrieve

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Circle
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

from render_config import DPI, add_size_args, new_figure
from south_pole import draw_features, latlon_to_xy, lon_label, stereo_radius

TREK_STREAM = "https://trek.nasa.gov/moon/TrekWS/rest/cat/data/stream?label=polar_south_80_{}"
LAYERS = [f"{s}_{v}" for s in ("summer", "winter") for v in ("avg", "min", "max", "amplitude")]
LAT_LIMIT = -80.0
ICE_THRESHOLD_K = 110

# Figure layout in pixels; each map axes is square and the circle fills 1/MAP_MARGIN of it.
TITLE_PX = 50
COLORBAR_PX = 80  # horizontal colorbar with ticks and label
GAP_PX = 20
MAP_MARGIN = 1.12

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data" / "diviner"
OUT_DIR = ROOT / "output"


def layer_path(layer: str) -> Path:
    path = DATA_DIR / f"polar_south_80_{layer}.tif"
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {layer} from Moon Trek (26 MB, once)...")
        urlretrieve(TREK_STREAM.format(layer), path)
    return path


def read_layer(layer: str, size_px: int) -> np.ndarray:
    """Read the 80°S disc resampled to size_px x size_px (the pixels the map shows)."""
    r = stereo_radius(LAT_LIMIT)
    with rasterio.open(layer_path(layer)) as src:
        window = from_bounds(-r, -r, r, r, src.transform)
        return src.read(1, window=window, out_shape=(size_px, size_px), boundless=True,
                        fill_value=np.nan, resampling=Resampling.average)


def draw_grid(ax, radius_km: float, clip) -> None:
    style = dict(color="white", lw=0.5, alpha=0.5)
    lon = np.linspace(-180, 180, 361)
    for lat in (-82, -84, -86, -88):
        x, y = latlon_to_xy(lat, lon)
        ax.plot(x / 1000, y / 1000, **style, clip_path=clip)
        lx, ly = latlon_to_xy(lat, 180)
        ax.text(lx / 1000, ly / 1000, f"{abs(lat)}°S", color="white", fontsize=7,
                ha="center", va="bottom", bbox=dict(fc="black", alpha=0.4, lw=0, pad=1))
    for meridian in range(-150, 181, 30):
        x, y = latlon_to_xy(np.array([-90, LAT_LIMIT]), meridian)
        ax.plot(x / 1000, y / 1000, **style, clip_path=clip)
        if meridian % 90 == 0:
            a = math.radians(meridian)
            ax.text(1.06 * radius_km * math.sin(a), 1.06 * radius_km * math.cos(a), lon_label(meridian),
                    fontsize=8, ha="center", va="center")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--layers", nargs="+", choices=LAYERS, default=["summer_max", "winter_min"],
                        help="one or more layers, drawn side by side")
    parser.add_argument("--show", action="store_true", help="open an interactive window after saving")
    add_size_args(parser)
    args = parser.parse_args()

    n = len(args.layers)
    width, height = args.width, args.height
    side = min(height - TITLE_PX - COLORBAR_PX, (width - (n + 1) * GAP_PX) / n)
    radius_km = stereo_radius(LAT_LIMIT) / 1000
    disc_px = round(side / MAP_MARGIN)
    data = {layer: read_layer(layer, disc_px) for layer in args.layers}
    print(f"Map: 80°S to the pole, {2 * radius_km * 1000 / disc_px:.0f} m/px, image {width}x{height} px")

    # One color scale for all panels so the same color means the same temperature.
    values = np.concatenate([d[np.isfinite(d)] for d in data.values()])
    norm = plt.Normalize(np.percentile(values, 0.1), np.percentile(values, 99.9))
    cmap = plt.cm.inferno

    fig = new_figure(width, height)
    left0 = (width - n * side - (n - 1) * GAP_PX) / 2
    bottom = COLORBAR_PX + (height - TITLE_PX - COLORBAR_PX - side) / 2
    extent = (-radius_km, radius_km, -radius_km, radius_km)
    for i, layer in enumerate(args.layers):
        left = left0 + i * (side + GAP_PX)
        ax = fig.add_axes((left / width, bottom / height, side / width, side / height))
        clip = Circle((0, 0), radius_km, transform=ax.transData)
        ax.imshow(data[layer], extent=extent, cmap=cmap, norm=norm, clip_path=clip, interpolation="nearest")
        # Amplitude is a temperature difference, so the ice threshold doesn't apply to it.
        if not layer.endswith("amplitude"):
            cs = ax.contour(data[layer], levels=[ICE_THRESHOLD_K], colors="cyan", linewidths=0.8,
                            extent=extent, origin="upper")
            cs.set_clip_path(clip)
        ax.add_patch(Circle((0, 0), radius_km, fill=False, color="black", lw=1))
        draw_grid(ax, radius_km, clip)
        draw_features(ax, LAT_LIMIT, radius_km)
        lim = MAP_MARGIN * radius_km
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        ax.axis("off")
        season, stat = layer.split("_")
        ax.set_title(f"Southern {season}, {'average' if stat == 'avg' else stat}", fontsize=11)

    fig.suptitle("Diviner surface temperature, 80°S to the pole (Williams et al. 2019, via Moon Trek)",
                 y=1 - 10 / height, va="top", fontsize=12)
    cax = fig.add_axes((0.25, 45 / height, 0.5, 14 / height))
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    cbar.set_label(f"Temperature (K) - cyan line: {ICE_THRESHOLD_K} K, water ice stable where colder")
    cbar.ax.axvline(ICE_THRESHOLD_K, color="cyan", lw=2)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"diviner_{'_'.join(args.layers)}_{width}x{height}.png"
    fig.savefig(out, dpi=DPI)
    print(f"Figure saved to {out}")
    if args.show:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()
