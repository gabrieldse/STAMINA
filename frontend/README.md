# STAMINA frontend

React + TypeScript + Vite, with a lazily loaded Cesium 3D Moon and a canvas-based
polar map. See the [root README](../README.md) for installation and the complete
website/API startup procedure.

## Commands

Run inside `frontend/`:

```bash
npm ci
npm run dev     # http://localhost:5173; scientific API must run on port 8001
npm test        # Node geometry, configuration, and visibility tests
npm run build  # TypeScript check and production build in dist/
```

Alternatively, from the repository root with Python dependencies installed:

```bash
python scripts/manage.py dev
```

This starts both frontend and API. `STAMINA_API_TARGET` overrides Vite's local
proxy destination. `VITE_API_URL`, if set before building, selects a separate
API origin; same-origin API requests are the default.

## Source layout

| Path | Purpose |
| --- | --- |
| `src/App.tsx` | Introduction, mission window, app navigation |
| `src/Components/LunarExplorer/` | Maps, site menu, analysis controls, timelines |
| `src/Components/WelcomeModal/` | Welcome, date/duration setup, map area selection |
| `src/Components/SiteDemo/` | Guided tour of the active explorer |
| `src/Components/MissionTutorial/` | Earlier mission walkthrough components |
| `src/services/` | Scientific API client and error messages |
| `src/filters/` | Built-in filter definitions and configuration import/export |
| `src/types/`, `src/utils/` | Shared types and projection/navigation helpers |
| `src/data/landing-sites.json` | Landing site names, coordinates, descriptions |
| `public/lunar-map/index.html` | Embedded polar canvas and comparison cells |
| `public/brand/`, `public/globe/` | Brand assets and bundled lunar imagery |
| `tests/` | Node tests and optional Playwright browser scripts |

## Generated map assets

The polar viewer requires `public/lunar-map/data/meta.json` and its binary
grids. They are not versioned. Build them from the repository root:

```bash
python scripts/manage.py prepare-data
```

The optional `--terrain` flag also generates detailed shaded terrain and
500 m / 1,000 m contours. Without those tiles, the default map uses its bundled
base grid and coarser browser-generated contours.

Custom-coordinate maps use LROC WAC imagery and regional global LOLA relief.
Diviner temperature layers remain specific to the default south-pole map.
Both custom and polar maps support terrain-aware Sun/Earth visibility.

For a compiled website with working API calls, run `python scripts/manage.py
serve` from the repository root after building. Vite preview alone does not
start the scientific API.
