Run from the repository root:

```powershell
uv venv .venv --python 3.14 --system-site-packages
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

Visibility follows the terrain-horizon approach of Mazarico et al. (2011),
https://doi.org/10.1016/j.icarus.2010.10.030. The local LOLA
`lola_2d/data/ldem_75s_240m_dem.tif` is required (generate via
`uv run lola_2d/south_pole.py`) and supplies the highest-detail south-polar
analysis. Other locations use cached, on-demand regional windows from NASA
Moon Trek's global `LRO_LOLA_DEM_Global_256ppd_v06` ImageServer (about 400 m
per output cell). The global service needs an internet connection the first
time a region is analyzed; the most recent two terrain windows remain cached
in memory.
For each surface observer, all valid DEM cells contribute their Moon-curvature
corrected elevation to a maximum skyline in 720 azimuth sectors (0.5 degrees).
Profiles are cached in memory. This sector maximum is conservative and can
merge narrow obstacles. No flat-horizon fallback is used if data is absent.

SPICE kernels remain loaded in the process so illumination calculations can
reuse them after API requests. API requests are serialized with a SPICE lock;
other components must also coordinate concurrent SPICE access.

The map time explorer uses `/api/position-timeline?date=2032-11-01&durationDays=14`.
It preloads hourly Sun and Earth vectors (including the end of the window), then
updates the map mask and landing-site elevation windows locally during playback.
Green site windows meet every enabled elevation threshold; other environmental
filters and terrain obstructions are not included in these windows. The separate
selected-site analysis retains its 10-minute sampling.

API tests: `py -m pip install httpx`, then
`py -m unittest discover -s tests -p test_api.py`.

For the full suite, including the legacy illumination module:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'lola_2d'
.venv/Scripts/python.exe -B -m unittest discover -s tests
```
