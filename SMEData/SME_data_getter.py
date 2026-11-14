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