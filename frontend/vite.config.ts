import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { viteStaticCopy } from 'vite-plugin-static-copy'

// CesiumJS loads its workers, assets and widget styles at runtime from
// window.CESIUM_BASE_URL (set in Globe3D), so they are copied next to the
// app as static files under /cesium.
const cesiumSource = 'node_modules/cesium/Build/Cesium'
const cesiumBaseUrl = 'cesium'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: ['Workers', 'ThirdParty', 'Assets', 'Widgets'].map((dir) => ({
        src: `${cesiumSource}/${dir}`,
        dest: cesiumBaseUrl,
        // Drop "node_modules/cesium/Build/Cesium" so files land in /cesium/<dir>/
        rename: { stripBase: 4 },
      })),
    }),
  ],
  build: {
    // The lazily loaded Globe3D chunk is CesiumJS itself (~4 MB, ~1.1 MB gzipped).
    chunkSizeWarningLimit: 4500,
  },
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
