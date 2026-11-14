import rasterio as rio
import numpy as np

meters_per_degree = np.pi * 1737400 / 180 

def open_dem(dem_path):
    """Open the GeoTIFF at dem_path. The caller must close the dataset."""
    return rio.open(dem_path)

def get_dem_value(lon, lat, dem_path, verbose = False):
    """Return one DEM height in meters.

    lon, lat: Longitude and latitude in degrees for the simple-cylindrical DEM.
    dem_path: Path to the GeoTIFF containing the site.
    verbose: Print the DEM bounds, pixel coordinates, and height when True.
    """
    with open_dem(dem_path) as dem:
        if verbose:
            print("DEM shape:", dem.shape)
            print("DEM bounds:", dem.bounds)

        # This conversion matches the global DEM's simple-cylindrical projection.
        x = lon * meters_per_degree
        y = lat * meters_per_degree

        row, col = dem.index(x, y)

        if not (0 <= row < dem.height and 0 <= col < dem.width):
            raise ValueError("Coordinates out of DEM bounds")

        # Keep the no-data mask so missing elevations are not treated as terrain.
        elevations = dem.read(1, masked=True)
        height_m = elevations[row, col]

        if np.ma.is_masked(height_m) or not np.isfinite(height_m):
            raise ValueError("The DEM has no valid elevation at this location.")

        if verbose:
            print("Pixel row:", row, "column:", col)
            print("Elevation:", float(height_m), "meters")

        # Find the coordinates of the center of that pixel.
        pixel_x, pixel_y = dem.xy(row, col)
        if verbose:
            print("Pixel center longitude:", pixel_x / meters_per_degree)
            print("Pixel center latitude:", pixel_y / meters_per_degree)

        
        return height_m 

def get_dem_array(dem_path, verbose = False):
    """Return the masked elevation array from the GeoTIFF at dem_path.

    dem_path: Path to the DEM; its elevations must be in meters.
    verbose: Print the DEM shape and bounds when True.
    """
    with open_dem(dem_path) as dem:
        if verbose:
            print("DEM shape:", dem.shape)
            print("DEM bounds:", dem.bounds)

        elevations = dem.read(1, masked=True)
        if verbose:
            print("DEM array read successfully")

        return elevations