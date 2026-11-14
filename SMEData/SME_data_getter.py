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

MOON_FRAME = 'IAU_MOON' #use this frame to calculate positions relative to the Moon

#example of getting the position of the Sun relative to the Moon at a specific time

kl.load_kernels() # Load the necessary SPICE kernels for planetary and lunar data

et = tg.get_et("2026-11-14T12:00:00") #Convert UTC to ephemeris time

#Get Sun position relative to the Moon
sun_position, light_travel_time = sp.spkpos(str(CODES["SUN"]), et, MOON_FRAME, "NONE", str(CODES["MOON"])) 
#spkpos args: target, ephemeris time, reference frame, aberration correction, observer

earth_position, light_travel_time = sp.spkpos(str(CODES["EARTH"]), et, MOON_FRAME, "NONE", str(CODES["MOON"]))
#Get Earth position relative to the Moon