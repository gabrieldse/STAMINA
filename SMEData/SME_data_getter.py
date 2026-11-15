from pathlib import Path

ROOT = Path(__file__).resolve().parent

#kernels found on: https://naif.jpl.nasa.gov/pub/naif/generic_kernels/

import spiceypy as sp
import numpy as np

MOON_RADIUS = 1737400  # in meters

# two angles, one for longitude θ the other for latitude φ
MOON_VEC = lambda lon, lat, elevation: (MOON_RADIUS + elevation) * np.array([np.cos(np.radians(lat)) * np.cos(np.radians(lon)), np.cos(np.radians(lat)) * np.sin(np.radians(lon)), np.sin(np.radians(lat))])

CODES = {
    "SUN": 10,
    "MOON": 301,
    "EARTH": 399,
}
code = lambda name: str(CODES[name])

MOON_FRAME = 'IAU_MOON' #use this frame to calculate positions relative to the Moon

'''
#example of getting the position of the Sun relative to the Moon at a specific time

from SMEData import kernel_loaders as kl
from SMEData import time_getter as tg

kl.load_kernels() # Load the necessary SPICE kernels for planetary and lunar data

et = tg.get_et("2026-11-14T12:00:00") #Convert UTC to ephemeris time

#Get Sun position relative to the Moon
sun_position, light_travel_time = sp.spkpos(code("SUN"), et, MOON_FRAME, "NONE", code("MOON")) 
#spkpos args: target, ephemeris time, reference frame, aberration correction, observer

earth_position, light_travel_time = sp.spkpos(code("EARTH"), et, MOON_FRAME, "NONE", code("MOON"))
#Get Earth position relative to the Moon
'''


def get_pos(et):
    """
    Get the position of the Sun and the Earth relative to the Moon.

    Parameters:
    et (float): Ephemeris time.

    Returns:
    tuple: Position vectors and light travel times for the Sun and the Earth.
    """
    sun_position, sun_light_travel_time = sp.spkpos(code("SUN"), et, MOON_FRAME, "NONE", code("MOON"))
    earth_position, earth_light_travel_time = sp.spkpos(code("EARTH"), et, MOON_FRAME, "NONE", code("MOON"))
    return (sun_position, sun_light_travel_time), (earth_position, earth_light_travel_time)


def get_site_vec(et, lon, lat, sight_height=0):
    """
    Get the position vector of a site on the Moon's surface.

    Parameters:
    et (float): Ephemeris time.
    lon (float): Longitude of the site on the Moon in degrees.
    lat (float): Latitude of the site on the Moon in degrees.
    sight_height (float): Elevation of the site above the Moon's surface in meters.
    sun_site_vec = sme.get_site2sun_vec(et, lon, lat, get_dem_value(lon, lat))  
    Returns:
    tuple: Position vector and light travel time for the site.
    """
    site_vec = MOON_VEC(lon, lat, sight_height) / 1000  # Convert meters to kilometers
    return site_vec, 0  # Light travel time is 0 for a surface site relative to itself


def get_sun_vec(et):
    """
    Get the position of the Sun relative to the Moon.

    Parameters:
    et (float): Ephemeris time.

    Returns:
    tuple: Position vector and light travel time for the Sun.
    """
    return sp.spkpos(code("SUN"), et, MOON_FRAME, "NONE", code("MOON"))


def get_earth_vec(et):
    """
    Get the position of the Earth relative to the Moon.

    Parameters:
    et (float): Ephemeris time.

    Returns:
    tuple: Position vector and light travel time for the Earth.
    """
    return sp.spkpos(code("EARTH"), et, MOON_FRAME, "NONE", code("MOON"))


def get_obstacle_vec(et, lon_obstacle, lat_obstacle, obstacle_height=0):
    """
    Get the position vector of an obstacle on the Moon's surface.

    Parameters:
    et (float): Ephemeris time.
    lon_obstacle (float): Longitude of the obstacle on the Moon in degrees.
    lat_obstacle (float): Latitude of the obstacle on the Moon in degrees.
    obstacle_height (float): Elevation of the obstacle above the Moon's surface in meters.

    Returns:
    tuple: Position vector and light travel time for the obstacle.
    """
    obstacle_vec = MOON_VEC(lon_obstacle, lat_obstacle, obstacle_height) / 1000  # Convert meters to kilometers
    return obstacle_vec, 0  # Light travel time is 0 for a surface obstacle relative to itself


def get_site2sun_vec(et, lon, lat, sight_height=0):
    """
    Get the position vector of the Sun relative to a specific site on the Moon's surface.

    Parameters:
    et (float): Ephemeris time.
    lon (float): Longitude of the site on the Moon in degrees.
    lat (float): Latitude of the site on the Moon in degrees.

    Returns:
    tuple: Position vector and light travel time for the Sun relative to the site.
    """
    site_vec, _ = get_site_vec(et, lon, lat, sight_height)
    sun_vec, light_travel_time = get_sun_vec(et)
    sun_site_vec = sun_vec - site_vec
    return sun_site_vec, light_travel_time      

    
def get_site2earth_vec(et, lon, lat, sight_height=0, obstacle_height=0):
    """
    Get the position vector of the Earth relative to a specific site on the Moon's surface.

    Parameters:
    et (float): Ephemeris time.
    lon (float): Longitude of the site on the Moon in degrees.
    lat (float): Latitude of the site on the Moon in degrees.
    sight_height (float): Elevation of the site above the Moon's surface in meters.

    Returns:
    tuple: Position vector and light travel time for the Earth relative to the site.
    """
    site_vec, _ = get_site_vec(et, lon, lat, sight_height)
    earth_vec, light_travel_time = get_earth_vec(et)
    earth_site_vec = earth_vec - site_vec
    return earth_site_vec, light_travel_time


def get_obstacle2site_vec(et, lon_obstacle, lat_obstacle, lon_site, lat_site, sight_height=0, obstacle_height=0):
    """
    Get the position vector from an obstacle to a specific site on the Moon's surface.

    Parameters:
    et (float): Ephemeris time.
    lon_obstacle (float): Longitude of the obstacle on the Moon in degrees.
    lat_obstacle (float): Latitude of the obstacle on the Moon in degrees.
    lon_site (float): Longitude of the site on the Moon in degrees.
    lat_site (float): Latitude of the site on the Moon in degrees.
    sight_height (float): Elevation of the site above the Moon's surface in meters.
    obstacle_height (float): Elevation of the obstacle above the Moon's surface in meters.

    Returns:
    tuple: Position vector from the obstacle to the site and light travel time for the obstacle relative to the site.
    """
    obstacle_vec, _ = get_site_vec(et, lon_obstacle, lat_obstacle, obstacle_height)
    site_vec, _ = get_site_vec(et, lon_site, lat_site, sight_height)
    obstacle_to_site_vec = site_vec - obstacle_vec
    obstacle_vec, light_travel_time = get_obstacle_vec(et, lon_obstacle, lat_obstacle, obstacle_height)
    return obstacle_to_site_vec, light_travel_time