# React + TypeScript + Vite

## Choose the map before exploring

On opening the application, no map or scientific workspace is mounted. The
user must choose one of two options: provide coordinates and create a circular
2D map centered exactly on that point, or explicitly use the default south-pole
map. Both poles, longitudes near 180 degrees and 0..360 east longitudes are
supported. The custom circular map uses a local stereographic projection with
an initial ten-degree radius. Drag to pan, use the mouse wheel to zoom around
the cursor, and double-click or use Reset view to return to the chosen center.
Navigation uses the same projected-coordinate rules as the default polar map.
During gestures the previous image is transformed immediately, then refreshed
at the new view once the interaction ends.

Custom maps use LROC WAC imagery, first the bundled offline mosaic and then
visible NASA Moon Trek tiles. Markers and surface clicks use the same local
projection; clicks outside the circle cannot add points. Sun and Earth visibility
use the south-pole LOLA DEM or fetch a cached regional window from NASA's global
LOLA DEM for other lunar locations. Contours and Diviner temperature layers
remain specific to the default south-pole map; custom maps show globally sourced
shaded LOLA relief when Terrain overlay is enabled. Contour generation is sliced
into idle browser work to keep map interactions responsive. Custom sites and map center survive
date changes. **Map area**, at the upper-left inside the map, opens the coordinate
or default-map choice, with Cancel to keep the current area. **Help** opens the
original Site Demo / Free Exploration menu, without emoji icons.

Browser regression (local frontend/API running, Microsoft Edge installed):

```powershell
uv pip install --python .venv/Scripts/python.exe playwright
.venv/Scripts/python.exe -B frontend/tests/site-centered.browser.py
.venv/Scripts/python.exe -B frontend/tests/map-controls.browser.py
```

It checks the initial map gate, empty coordinate validation, actual surface
picks inside circular maps at equatorial, north-pole, south-pole and dateline
sites, rejection of clicks outside the circle, date persistence and the explicit
default choice. The controls check covers Help, demo/free exploration, the Map
area menu, dragging without adding a point, cursor-anchored zoom verified through
exported coordinates, and reset. Projection and navigation geometry are tested
with Node's test runner.

## Lunar map data

For detailed terrain when zooming, run `py lola_2d/build_terrain_tiles.py`
from the repository root after installing the Python requirements. This downloads
the NASA LOLA 80 m polar DEM and generates local tile pyramids of shaded relief and
of contour lines (500 m, bold every 1,000 m) for the "Terrain overlay" filter. The
viewer loads only visible tiles; without them it keeps the original base map and
computes coarser contours in the browser. Temperature
overlays retain their own scientific grid resolution; terrain detail is not
orbital photography and cannot reveal features smaller than the source data.

The Lunar South Pole map (`public/lunar-map/`) needs its temperature grids,
which are generated and not committed. From the repository root, once:

```bash
uv run lola_2d/diviner_web.py --no-serve   # downloads ~210 MB from Moon Trek once, writes ~77 MB of grids (loaded on demand)
```

Then `npm run dev` as usual. The viewer also runs on its own with
`uv run lola_2d/diviner_web.py` (http://localhost:8000).


This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```

You can also install [eslint-plugin-react-x](https://npmx.dev/package/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://npmx.dev/package/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```
