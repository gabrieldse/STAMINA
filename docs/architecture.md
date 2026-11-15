# Architecture and contributor guide

## Request flow

```text
React explorer (frontend/src/App.tsx)
  └─ LunarExplorer: filters, mission date/duration, selected site
       └─ MapTimeline: hourly Sun/Earth ephemerides, time playback
            └─ MapPanel
                 ├─ public/lunar-map/index.html: polar canvas + comparison grid
                 ├─ CircularSiteMap: map centered on user coordinates
                 └─ Globe3D: lazily loaded Cesium Moon
```

Vite proxies `/api` to `http://127.0.0.1:8001` during development. The launcher
can override the target using `STAMINA_API_TARGET`. `backend/web.py` serves
`frontend/dist/` alongside the API for a compiled, single-origin deployment.
The optional build-time `VITE_API_URL` selects an external API address; such a
deployment also needs an appropriate cross-origin policy on that API.

## Scientific backend

- `api.py`: validated HTTP requests and SPICE access protected by a lock.
- `horizon.py`: terrain skyline and observer geometry.
- `visibility_map.py`: packed visibility maps and regional relief overlays.
- `visibility_kernel.py`: optional Numba ray-tracing acceleration.
- `global_lola.py`: on-demand global LOLA terrain windows.
- `custom_filter_engine.py`: evaluates custom rules against site metrics.

Keep scientific methods documented in `backend/README.md`. Changes to frame
conventions, missing-data handling, time sampling, or resolution should update
that document and the relevant tests.

## Data ownership

| Data | Location | Versioned? |
| --- | --- | --- |
| Landing site definitions | `frontend/src/data/landing-sites.json` | Yes |
| SPICE kernels | `SMEData/Kernels/` | Yes |
| Downloaded NASA DEM/Diviner files | `lola_2d/data/` | No; generated/cached |
| Binary polar map grids and terrain tiles | `frontend/public/lunar-map/data/` | No; generated |
| Compiled frontend, including copied data | `frontend/dist/` | No; built |
| Temporary servers/tunnel downloads and logs | `.runtime/`, `backend/*.log` | No |

Do not commit virtual environments, node_modules, caches, logs, secrets, or
generated terrain datasets. Keep original NASA attribution in the generated
metadata. A deployable artifact must include generated assets even though Git
does not contain them.

## Where to change things

- Entry flow and mission setup: `frontend/src/App.tsx`, `Components/WelcomeModal/`.
- Map interactions and comparison: `Components/LunarExplorer/MapPanel.tsx`
  and `frontend/public/lunar-map/index.html`.
- Site menu: `Components/LunarExplorer/SiteList.tsx`.
- Timeline/day axis: `Components/LunarExplorer/MapTimeline.tsx`.
- Filter definitions: `frontend/src/filters/filterRegistry.ts`.
- API client/errors: `frontend/src/services/`.
- Dataset generation: scripts under `lola_2d/`; use `scripts/manage.py prepare-data`.

The standalone image generator lives in `Filters/Sunlight/`, with DEM helpers
in `SurfaceData/` and shared ephemeris utilities in `SMEData/`.
See [the illumination guide](../Filters/README.md) for examples and model limits.
`legacy/website/` is the
original static design reference and does not participate in the React build.

## Change discipline

Use focused commits for UI changes, scientific changes, and tooling/docs. Run
the relevant Python or Node tests and build the frontend after TypeScript
changes. Keep the root README's startup instructions consistent with launcher
defaults; avoid embedding a particular developer's filesystem paths.
