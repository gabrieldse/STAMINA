# React + TypeScript + Vite

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
`uv run lola_2d/diviner_web.py` (http://localhost:8001; port 8000 is the scientific API).


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
