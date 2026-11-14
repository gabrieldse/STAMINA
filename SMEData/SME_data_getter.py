import pathlib as pathl

ROOT = pathl.Path(__file__).resolve().parent

#kernels found on: https://naif.jpl.nasa.gov/pub/naif/generic_kernels/

import spiceypy as sp
import time_getter as tg
import kernel_loaders as kl

CODES = {
    "SUN": 10,
    "MOON": 301,
    "EARTH": 399,
}
code = lambda name: str(CODES[name])

MOON_FRAME = 'IAU_MOON' #use this frame to calculate positions relative to the Moon

'''
#example of getting the position of the Sun relative to the Moon at a specific time

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