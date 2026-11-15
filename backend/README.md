Run from the repository root:

```powershell
py -m pip install -r requirements.txt
py -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Analysis uses the checked-in NASA SPICE kernels, the IAU_MOON frame, and
body-center elevations above a spherical local horizon. Dates start at midnight
UTC. Mission mode uses midpoint samples every 10 minutes; instant mode reports
visibility at midnight and omits outage durations. Elevation filters apply to
the Sun and Earth respectively. Terrain overlay is a display control: these
calculations do not model topographic shadows or radio propagation.

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
