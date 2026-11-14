import spiceypy as sp

from pathlib import Path
ROOT = Path(__file__).resolve().parent

KERNELS = [
    "naif0012.tls", #conversion of time strings to ephemeris time data
    "de440s.bsp", #planetary positions/velocities data (26 December 1849, 00:00:00 → 22 January 2150, 00:00:00)
    "pck00011.tpc", #planetary orientation/size data 
]

def load_kernels():
    for kernel in KERNELS:
        sp.furnsh(str(ROOT / "Kernels" / kernel))

def clear_kernels():
    sp.kclear()

def get_kernel_paths():
    return [str(ROOT / "Kernels" / kernel) for kernel in KERNELS]