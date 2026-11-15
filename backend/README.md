Run from the repository root:

```powershell
uv venv .venv --python 3.14 --system-site-packages
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

Visibility follows the terrain-horizon approach of Mazarico et al. (2011),
https://doi.org/10.1016/j.icarus.2010.10.030. The local LOLA
`lola_2d/data/ldem_75s_240m_dem.tif` is required (generate via
`uv run lola_2d/south_pole.py`). Analysis supports sites south of 80 S.
For each surface observer, all valid DEM cells contribute their Moon-curvature
corrected elevation to a maximum skyline in 720 azimuth sectors (0.5 degrees).
Profiles are cached in memory. This sector maximum is conservative and can
merge narrow obstacles. No flat-horizon fallback is used if data is absent.

NASA SPICE DE440s / IAU_MOON body-center directions are compared with the
skyline in the matching sector. This is an approximation inspired by the paper,
not its complete illumination model: finite solar/Earth disks, scattered light,
subpixel relief, observer height and DEM/frame uncertainties are not modeled.
The 240 m grid and sector binning limit precision.

Mission analysis uses 10-minute midpoint samples; instant mode uses midnight UTC.
The map site timelines use hourly samples and `/api/horizon` profiles with the
same visibility predicate. `/api/visibility-map` traces each selected body's
line of sight against the 240 m LOLA DEM, including lunar curvature and parallax.
The map first displays a 384 by 384 preview, then refines to 1536 by 1536
(396 m/cell, versus the previous 2375 m/cell). Playback uses 768 by 768
(792 m/cell) and waits for each result. The API supports up to 2048 by 2048.
Numba compiles independent rays on up to eight CPU threads, with disk caching
and no fast-math transformations. First use may take longer for compilation.
Without Numba, the NumPy reference remains available and API requests are capped
at 512 by 512 to keep the fallback responsive. Masks use a packed bitset in the
web UI; existing API consumers can still request arrays. Cache counts are bounded.
Ray steps are 240 m; subpixel terrain may be missed. Missing terrain is excluded.
Only visible map cells remain displayed and selectable; both controls use their
intersection. Playback waits for each terrain mask before advancing.
Percentages and outages are always physical visibility metrics; the visibility
checkboxes select which bodies constrain both the map and matching site time windows.

Benchmark: `.venv/Scripts/python.exe -m backend.benchmark_visibility`.
Recorded results are in `backend/visibility_benchmark.json` (November 15, 2026,
local machine, date 2026-11-15, warm compiler, uncached body masks):

| Grid | Sampling | Sun + Earth calculation | Packed JSON |
| --- | --- | --- | --- |
| 768 | 792 m | 0.31 s | 98 KB |
| 1536 | 396 m | 1.65 s | 393 KB |
| 2048 | 297 m | 3.27 s | 699 KB |

At 256, individual compiled rays took 0.015–0.035 s versus 0.29–0.55 s for
NumPy (about 16–19 times faster). These are local measurements, not latency
guarantees; the browser/API also incur grid setup, network and rendering costs.
The 1536 default gives most of the source DEM's spatial detail at around half
the computation time of 2048. The source DEM remains 240 m; finer masks do not
increase the underlying terrain accuracy. Tests compare compiled and reference
masks, preserve missing-data exclusions, and check bitset ordering.

API tests: `py -m pip install httpx`, then
`py -m unittest discover -s tests -p test_api.py`.

For the full suite, including the legacy illumination module:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'lola_2d'
.venv/Scripts/python.exe -B -m unittest discover -s tests
```
