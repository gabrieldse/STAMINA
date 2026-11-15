# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio", "matplotlib", "numpy", "pillow"]  # rasterio via south_pole
# ///
"""Static images for the 3D globe and the map switcher in the explorer.

    uv run globe_assets.py

Writes to frontend/public/globe/ (small files, committed):
  - lroc_wac_global.jpg: LROC WAC global mosaic (Moon Trek WMTS level 2,
    2048x1024 plate carree), the globe's offline base under the live tiles;
  - thumb_2d.png / thumb_3d.png: thumbnails for the 2D/3D map switcher.
"""

import io
import math
import urllib.request
from pathlib import Path

import numpy as np
from matplotlib.colors import LightSource
from PIL import Image

from south_pole import build_map, stereo_radius

OUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public" / "globe"
# Moon Trek WMTS: geographic 2x1 tiles at level 0, 256 px; level 2 is 8x4 tiles.
WAC_TILE = ("https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/"
            "default/default028mm/{z}/{row}/{col}.jpg")
WAC_LEVEL = 2
THUMB_PX = 96


def wac_mosaic() -> np.ndarray:
    """LROC WAC global mosaic, columns from 180°W to 180°E, grey values 0..1."""
    cols, rows = 2 * 2**WAC_LEVEL, 2**WAC_LEVEL
    image = Image.new("L", (cols * 256, rows * 256))
    for row in range(rows):
        for col in range(cols):
            url = WAC_TILE.format(z=WAC_LEVEL, row=row, col=col)
            with urllib.request.urlopen(url, timeout=60) as resp:
                tile = Image.open(io.BytesIO(resp.read())).convert("L")
            image.paste(tile, (col * 256, row * 256))
    return np.asarray(image, dtype=float) / 255


def orthographic(image: np.ndarray, lat0: float, lon0: float, size: int) -> Image.Image:
    """The Moon seen from far away above (lat0, lon0), on a transparent background.
    Rendered 4x larger and downsampled, so the thumbnail isn't grainy."""
    final, size = size, size * 4
    y, x = np.mgrid[1:-1:size * 1j, -1:1:size * 1j]
    rho2 = x**2 + y**2
    inside = rho2 <= 1
    z = np.sqrt(np.clip(1 - rho2, 0, 1))
    phi0, lam0 = math.radians(lat0), math.radians(lon0)
    lat = np.arcsin(np.clip(z * math.sin(phi0) + y * math.cos(phi0), -1, 1))
    lon = lam0 + np.arctan2(x, z * math.cos(phi0) - y * math.sin(phi0))
    rows, cols = image.shape
    r = np.clip(((math.pi / 2 - lat) / math.pi * rows).astype(int), 0, rows - 1)
    c = (((lon + math.pi) % (2 * math.pi)) / (2 * math.pi) * cols).astype(int) % cols
    grey = (image[r, c] * 255).astype(np.uint8)
    rgba = np.dstack([grey, grey, grey, np.where(inside, 255, 0).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA").resize((final, final), Image.LANCZOS)


def polar_thumbnail(size: int) -> Image.Image:
    """The 80°S polar cap as drawn by the 2D map."""
    radius = stereo_radius(-80)
    dem, _ = build_map(-80, 2 * radius / size, "LDEM_75S_240M")
    dem = dem[:size, :size]
    shade = LightSource(azdeg=315, altdeg=35).hillshade(
        np.where(np.isnan(dem), np.nanmean(dem), dem), vert_exag=2, dx=2 * radius / size, dy=2 * radius / size)
    yy, xx = np.mgrid[:size, :size]
    inside = (xx - size / 2 + 0.5) ** 2 + (yy - size / 2 + 0.5) ** 2 <= (size / 2) ** 2
    grey = (shade * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([grey, grey, grey, np.where(inside, 255, 0).astype(np.uint8)]), "RGBA")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wac = wac_mosaic()
    Image.fromarray((wac * 255).astype(np.uint8)).save(OUT_DIR / "lroc_wac_global.jpg", quality=85)
    # 3D thumbnail: near side tilted south, so both the Apollo sites and the pole show.
    orthographic(wac, -35, 10, THUMB_PX).save(OUT_DIR / "thumb_3d.png")
    polar_thumbnail(THUMB_PX).save(OUT_DIR / "thumb_2d.png")
    for path in sorted(OUT_DIR.iterdir()):
        print(f"{path.name}: {path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
