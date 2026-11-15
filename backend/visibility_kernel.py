"""Compiled, independent line-of-sight rays. Keep IEEE/NaN semantics intact."""
import math
import os

import numpy as np

try:
    from numba import njit, prange, get_num_threads, set_num_threads
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    prange = range


def _trace_rays(observers, target, dem, a, c, e, f, reference_radius, ceiling):
    result = np.zeros(len(observers), dtype=np.bool_)
    for i in prange(len(observers)):
        ox, oy, oz = observers[i, 0], observers[i, 1], observers[i, 2]
        if not (math.isfinite(ox) and math.isfinite(oy) and math.isfinite(oz)):
            continue
        dx, dy, dz = target[0]-ox, target[1]-oy, target[2]-oz
        length = math.sqrt(dx*dx+dy*dy+dz*dz)
        dx, dy, dz = dx/length, dy/length, dz/length
        for step in range(1, 5001):
            distance = step*240.
            x, y, z = ox+distance*dx, oy+distance*dy, oz+distance*dz
            radius = math.sqrt(x*x+y*y+z*z)
            if radius > ceiling and x*dx+y*dy+z*dz > 0:
                result[i] = True
                break
            px = 2*reference_radius*y/(radius-z)
            py = 2*reference_radius*x/(radius-z)
            col, row = math.floor((px-c)/a), math.floor((py-f)/e)
            if row < 0 or col < 0 or row >= dem.shape[0] or col >= dem.shape[1]:
                break
            height = dem[row, col]
            if not math.isfinite(height) or radius < reference_radius+height:
                break
    return result


if NUMBA_AVAILABLE:
    trace_rays = njit(cache=True, parallel=True, nogil=True)(_trace_rays)


def accelerated_trace(observers, target, dem, transform, radius):
    # Limit worker usage so the UI and site-horizon requests remain responsive.
    set_num_threads(min(get_num_threads(), max(1, min(8, (os.cpu_count() or 2)//2))))
    return trace_rays(observers, np.asarray(target, dtype=np.float64)*1000, dem,
                      transform.a, transform.c, transform.e, transform.f,
                      radius, radius+float(np.nanmax(dem))+1)
