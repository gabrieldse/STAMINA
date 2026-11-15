"""Generate local zoom tiles from the NASA LOLA 80 m polar elevation model.

For every tile of the pyramid (levels 0-5, 256 px, 80°S to the pole) this
writes a shaded-relief tile to data/terrain/ and a transparent contour-line
tile to data/contours/ (500 m lines, 1,000 m lines in bold), which the map
loads on demand for the "Terrain overlay" filter.
"""
import json
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.transform import from_origin
from rasterio.enums import Resampling
from rasterio.windows import Window
from PIL import Image
from south_pole import prepare_dem, stereo_radius, SOUTH_POLAR_CRS
from diviner_web import WEB_DIR

CONTOUR_MINOR_M = 500
CONTOUR_MAJOR_M = 1000
# RGBA of the contour layers (match the map legend and the in-browser fallback)
HALO = (0, 0, 0, 166)
MINOR = (108, 239, 224, 166)
MAJOR = (173, 255, 241, 255)


def crossings(heights: np.ndarray, valid: np.ndarray, interval: float) -> np.ndarray:
    """Pixels where the height crosses a multiple of interval towards the right or down neighbour."""
    band = np.floor(np.where(valid, heights, 0) / interval)
    edge = np.zeros(heights.shape, dtype=bool)
    edge[:, :-1] |= (band[:, :-1] != band[:, 1:]) & valid[:, 1:]
    edge[:-1, :] |= (band[:-1, :] != band[1:, :]) & valid[1:, :]
    return edge & valid


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    """Thicken lines by radius pixels (no wrap-around at the tile edges)."""
    padded = np.pad(mask, radius)
    rows, cols = mask.shape
    out = np.zeros_like(mask)
    for dy in range(2 * radius + 1):
        for dx in range(2 * radius + 1):
            out |= padded[dy:dy + rows, dx:dx + cols]
    return out


def contour_tile(heights: np.ndarray) -> np.ndarray:
    """Transparent 256x256 RGBA contour lines from a 258x258 height window (1 px border)."""
    valid = np.isfinite(heights)
    minor = crossings(heights, valid, CONTOUR_MINOR_M)
    major = crossings(heights, valid, CONTOUR_MAJOR_M)
    rgba = np.zeros(heights.shape + (4,), dtype=np.uint8)
    rgba[dilate(major, 2)] = HALO
    rgba[minor] = MINOR
    rgba[dilate(major, 1)] = MAJOR
    return rgba[1:-1, 1:-1]


def build():
    source = prepare_dem("LDEM_80S_80M", "polar")
    radius = stereo_radius(-80)
    output = WEB_DIR / "data" / "terrain"
    contours = WEB_DIR / "data" / "contours"
    output.mkdir(parents=True, exist_ok=True)
    with rasterio.open(source) as src:
        for level in range(6):
            size = 256 * 2**level
            resolution = 2 * radius / size
            # A one-pixel border supplies gradients across tile boundaries.
            with WarpedVRT(src, crs=SOUTH_POLAR_CRS,
                           transform=from_origin(-radius-resolution, radius+resolution, resolution, resolution),
                           width=size+2, height=size+2, resampling=Resampling.bilinear,
                           nodata=float("nan")) as vrt:
                for y in range(2**level):
                    for x in range(2**level):
                        heights = vrt.read(1, window=Window(x*256, y*256, 258, 258))
                        valid = np.isfinite(heights[1:-1, 1:-1])
                        dy, dx = np.gradient(np.nan_to_num(heights), resolution)
                        # Fixed illumination (315 deg azimuth, 35 deg altitude), no per-tile stretching.
                        nx, ny = -2*dx, 2*dy
                        length = np.sqrt(nx*nx + ny*ny + 1)
                        light = (-.579228*nx + .579228*ny + .573576) / length
                        shade = (np.clip(.18 + .82*np.maximum(light, 0), 0, 1)*255).astype("uint8")[1:-1, 1:-1]
                        rgba = np.stack([shade, shade, shade, valid.astype("uint8")*255], axis=-1)
                        folder = output / str(level) / str(x)
                        folder.mkdir(parents=True, exist_ok=True)
                        Image.fromarray(rgba).save(folder / f"{y}.png")
                        contour_folder = contours / str(level) / str(x)
                        contour_folder.mkdir(parents=True, exist_ok=True)
                        Image.fromarray(contour_tile(heights)).save(contour_folder / f"{y}.png", optimize=True)
            print(f"Built terrain and contour level {level}: {size} pixels", flush=True)
    (output / "meta.json").write_text(json.dumps(dict(maxZoom=5, tileSize=256, resolutionM=80,
                                                      source="NASA LOLA LDEM_80S_80M")))
    (contours / "meta.json").write_text(json.dumps(dict(maxZoom=5, tileSize=256, resolutionM=80,
                                                        minorM=CONTOUR_MINOR_M, majorM=CONTOUR_MAJOR_M,
                                                        source="NASA LOLA LDEM_80S_80M")))


if __name__ == "__main__":
    build()
