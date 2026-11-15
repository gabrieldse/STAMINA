# STAMINA — Lunar Landing Site Explorer

STAMINA combines a React website with a Python scientific API to explore lunar
terrain, surface temperatures, and Sun/Earth visibility. It includes a circular
south-pole map, maps centered on custom coordinates, a 3D Moon, site comparison,
distance measurements, and mission timelines.

**The website needs both the frontend and the API.** Opening an HTML file or
running Vite alone does not enable the scientific calculations.

## Requirements

- Python 3.12 or newer. Development has also been checked with Python 3.14.
- Node.js 22.12 or newer, with npm.
- Git and an internet connection for the initial NASA data downloads.
- Enough free disk space for downloaded terrain and generated map tiles; allow
  several GB if you generate the optional detailed terrain tiles.

## 1. Get the project and install dependencies

```bash
git clone --branch site-stamina-anas https://github.com/gabrieldse/STAMINA.git
cd STAMINA
python -m venv .venv
```

Activate the Python environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

On Windows, use `py` instead of `python` to create the environment if needed.
If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` in place of
`python` in the following commands; activation is optional.

```bash
python -m pip install -r requirements.txt
npm --prefix frontend ci
```

## 2. Prepare scientific data once

```bash
python scripts/manage.py prepare-data
```

This downloads the required LOLA and Diviner datasets from NASA and builds the
polar map grids in `frontend/public/lunar-map/data/`. Downloads are reused on
subsequent runs. These generated files are deliberately excluded from Git, so a
fresh checkout must run this step. The SPICE kernels in `SMEData/Kernels/` are
already included in the repository.

For a smaller 1024-pixel map, use `prepare-data --size 1024`. For optional
detailed terrain shading and contour tiles, use `prepare-data --terrain`; this
also downloads the higher-resolution polar DEM and takes longer.

Check the installation without downloading or changing anything:

```bash
python scripts/manage.py doctor
```

## 3. Run the website

From the repository root, with the Python environment active:

```bash
python scripts/manage.py dev
```

Open **http://localhost:5173**. The API runs on **http://localhost:8001**;
interactive API documentation is at **http://localhost:8001/docs**. Press
**Ctrl+C** in the terminal to stop the launcher.

If a port is already in use, stop the old server or choose different ports:

```bash
python scripts/manage.py dev --api-port 8002 --web-port 5174
```

The launcher connects Vite to the chosen API port automatically.

You can also start the two services in separate terminals:

```bash
# Terminal 1, repository root
python scripts/manage.py api --reload

# Terminal 2, repository root
npm --prefix frontend run dev
```

## Using the explorer

1. Choose **Site Demo** or **Free Exploration** in the introduction.
2. Enter the mission start date and duration. Defaults: **8 February 2028**,
   **20 Earth days**. Exploration begins with the south-pole map.
3. Open **Landing sites**, expand a group, and switch on the sites you want.
   Sites, their groups, and the scientific details panel start hidden/folded.
4. Enable **Sun visibility** or **Earth visibility** to show the visible terrain
   at the time selected in the Time Explorer. Both enabled require both bodies
   to be visible. These map filters are instantaneous; mission percentages and
   outages are calculated with **Run Scientific Analysis**.
5. Open **Show details** to set analysis parameters and run an analysis.

**Map area** selects a custom map center or restores the default south pole.
Drag to pan, scroll to zoom, and double-click to reset. Comparison views number
the enabled sites, resize to fill their grid, and offer 10/20/30/40/80 km crops;
mouse-wheel or two-finger scrolling changes the crop. **Measure distance** on
the polar map measures between two clicks. Above site visibility bars, **D1**
means the first mission day; hover a tick for its UTC date or click to seek.

## Build and serve the compiled website

```bash
python scripts/manage.py build
python scripts/manage.py serve
```

Open **http://localhost:8080**. This serves the compiled website and Python API
from one address, including the generated map data. Rebuild after editing the
frontend. To listen on a server's network interface:

```bash
python scripts/manage.py serve --host 0.0.0.0 --port 8080
```

`npm run preview` in `frontend/` previews static build files only; use the Python
server above when you need working scientific endpoints. For deployment, the
host needs Python dependencies, SPICE kernels, the polar DEM, and the generated
frontend assets. GitHub Pages alone cannot run the Python API. The temporary
Cloudflare sharing process is a local development tool, not permanent hosting.

## Project layout

| Path | Purpose |
| --- | --- |
| `frontend/` | Active React/TypeScript website, assets, and frontend tests |
| `backend/` | FastAPI endpoints, terrain horizons, and visibility maps |
| `scripts/manage.py` | Setup checks, data generation, development and build commands |
| `lola_2d/` | NASA dataset downloads and map/terrain asset generators |
| `SMEData/` | SPICE kernel loading and bundled ephemeris kernels |
| `Sunlight/`, `Filters.py`, `moon_surface_getter.py` | Earlier scientific utilities, still covered by Python tests |
| `tests/` | Python scientific and API tests |
| `docs/` | Architecture and contributor notes |
| `legacy/website/` | Original static prototype; not the active application |

See [architecture](docs/architecture.md), [frontend notes](frontend/README.md),
[scientific methods](backend/README.md), and
[dataset documentation](lola_2d/docs/data_access_vs_moontrek.md).

## Checks for contributors

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests
npm --prefix frontend test
npm --prefix frontend run build
```

Python API tests require the local scientific data; some global-terrain tests
also contact NASA. Browser scripts in `frontend/tests/` use Playwright and
Microsoft Edge, require running servers, and include older onboarding
expectations that may need updating when the entry flow changes. They are
separate from the default Node tests.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Blank polar map or `meta.json` 404 | Run `prepare-data`; restart/rebuild the frontend afterward. |
| Visibility/Time Explorer fails or API 502 | Run `doctor`, check that the API is listening on port 8001, and inspect its terminal output. |
| Port already occupied | Stop your previous instance or use the launcher's alternate ports. |
| First visibility result is slow | Numba may be compiling; terrain downloads and horizon calculations are cached afterward. |
| NASA download fails | Check connectivity/certificate configuration; retry once the service is reachable. |
| Custom map cannot load terrain | NASA Moon Trek is needed on the first request for a region. |
| Compiled website shows old changes | Run `build` again, then refresh the browser. |

The visibility model uses terrain horizons and body centers. It does not model
every illumination effect and should not be treated as a flight-planning tool.
Method details and resolution limits are documented in [backend/README.md](backend/README.md).
