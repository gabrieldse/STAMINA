# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio", "matplotlib", "numpy"]
# ///
"""Build and serve the interactive Diviner south polar temperature viewer.

Exports every Moon Trek Diviner season summary (see diviner_maps.py) as a small
binary grid for the viewer in frontend/public/lunar-map/, which the React app
embeds in its Lunar South Pole map. The viewer also runs on its own:

    uv run diviner_web.py                 # build (1024 px grids) and serve on :8000
    uv run diviner_web.py --size 2048     # finer grids (4x the data)
    uv run diviner_web.py --no-serve      # only build the data, e.g. before `npm run dev`

Each grid is uint16 little-endian, kelvin x 100, 0 = no data.
"""

import argparse
import functools
import http.server
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from diviner_maps import ICE_THRESHOLD_K, LAT_LIMIT, LAYERS, read_layer
from south_pole import FEATURES, latlon_to_xy, stereo_radius

SCALE = 100  # stored value = kelvin * SCALE
WEB_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public" / "lunar-map"


def build(size: int) -> None:
    data_dir = WEB_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    layers = []
    for layer in LAYERS:
        grid = read_layer(layer, size)
        valid = np.isfinite(grid)
        packed = np.where(valid, np.round(np.clip(grid, 0, 655) * SCALE), 0).astype("<u2")
        packed.tofile(data_dir / f"{layer}.bin")
        season, stat = layer.split("_")
        layers.append({
            "id": layer,
            "name": f"Southern {season}, {'average' if stat == 'avg' else stat}",
            "isDifference": stat == "amplitude",
            "p01": round(float(np.percentile(grid[valid], 0.1)), 1),
            "p999": round(float(np.percentile(grid[valid], 99.9)), 1),
        })
        print(f"  {layer}: {layers[-1]['p01']}..{layers[-1]['p999']} K")

    features = []
    for name, (lat, lon, diameter_km) in FEATURES.items():
        if lat <= LAT_LIMIT:
            x, y = latlon_to_xy(lat, lon)
            features.append({"name": name, "lat": lat, "lon": lon, "x": round(float(x)), "y": round(float(y)),
                             "diameterKm": diameter_km})

    lut = (plt.cm.inferno(np.linspace(0, 1, 256))[:, :3] * 255).round().astype(int).tolist()
    meta = {
        "size": size,
        "radiusM": stereo_radius(LAT_LIMIT),
        "moonRadiusM": 1737400,
        "latLimit": LAT_LIMIT,
        "scale": SCALE,
        "iceThresholdK": ICE_THRESHOLD_K,
        "layers": layers,
        "features": features,
        "colormap": lut,
        "source": "Diviner polar temperatures, Williams et al. (2019), via NASA Moon Trek",
    }
    (data_dir / "meta.json").write_text(json.dumps(meta))
    print(f"Built {len(layers)} layers at {size}x{size} px "
          f"({2 * meta['radiusM'] / size:.0f} m/px) in {data_dir}")


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=WEB_DIR)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Open http://localhost:{port}/  (Ctrl+C to stop)")
        httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", type=int, default=1024, help="grid size in pixels across the 80°S disc")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-serve", action="store_true", help="only build the data")
    args = parser.parse_args()

    build(args.size)
    if not args.no_serve:
        serve(args.port)


if __name__ == "__main__":
    main()
