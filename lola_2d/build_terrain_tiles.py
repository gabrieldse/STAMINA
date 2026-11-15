"""Generate local zoom tiles from the NASA LOLA 80 m polar elevation model."""
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


def build():
    source = prepare_dem("LDEM_80S_80M", "polar")
    radius = stereo_radius(-80)
    output = WEB_DIR / "data" / "terrain"
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
            print(f"Built terrain level {level}: {size} pixels", flush=True)
    (output / "meta.json").write_text(json.dumps(dict(maxZoom=5, tileSize=256, resolutionM=80,
                                                      source="NASA LOLA LDEM_80S_80M")))


if __name__ == "__main__":
    build()
