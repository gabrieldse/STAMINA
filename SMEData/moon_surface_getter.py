import numpy as np
import SME_data_getter as sme

#simploified model, perfectly smooth moon

MOON_RADIUS = 1737.4  # in kilometers

# two angles, one for longitude θ the other for latitude φ
MOON_VEC = lambda lon, lat: MOON_RADIUS * np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])

def get_sun_site_vec(et, lon, lat):
    """
    Get the position vector of the Sun relative to a specific site on the Moon's surface.

    Parameters:
    et (float): Ephemeris time.
    lon (float): Longitude of the site on the Moon in radians.
    lat (float): Latitude of the site on the Moon in radians.

    Returns:
    tuple: Position vector and light travel time for the Sun relative to the site.
    """
    site_vec = MOON_VEC(lon, lat)
    sun_vec, light_travel_time = sme.get_sun_vec(et)
    sun_site_vec = sun_vec - site_vec
    return sun_site_vec, light_travel_time

def get_earth_site_vec(et, lon, lat):
    """
    Get the position vector of the Earth relative to a specific site on the Moon's surface.

    Parameters:
    et (float): Ephemeris time.
    lon (float): Longitude of the site on the Moon in radians.
    lat (float): Latitude of the site on the Moon in radians.

    Returns:
    tuple: Position vector and light travel time for the Earth relative to the site.
    """
    site_vec = MOON_VEC(lon, lat)
    earth_vec, light_travel_time = sme.get_earth_vec(et)
    earth_site_vec = earth_vec - site_vec
    return earth_site_vec, light_travel_time