# Data access: current approach vs NASA Moon Trek

*STAMINA, NASA Space Apps 2026. Written 2026-11-14. Every number below comes from a real request made that day. Anything not checked that way is marked **unverified**.*

## TL;DR

- Moon Trek has three access paths:
  1. a **documented** public WMTS that serves **pictures**: 8-bit stretched PNG/JPG tiles;
  2. **undocumented but public** ArcGIS ImageServer endpoints that return **raw Float32 values** as GeoTIFF for any bounding box;
  3. a per-product **full GeoTIFF download**.
- The ImageServer returns data in **exactly our CRS**: `+proj=stere +lat_0=-90 +lon_0=0 +R=1737400`, the same as IAU_2015:30135.
- For LOLA the ImageServer is far faster than what we do now. The Tycho crop (1920x1408 px, 256 ppd) took **3.5 s instead of ~2 min**, and the values are **bit-identical** to the crop we read from the USGS file.
- Trek hosts the **Williams et al. (2019) Diviner polar products as season summaries**: summer/winter avg, min, max and amplitude, 240 m, poleward of 80°S. Each is a 26 MB Float32 GeoTIFF.
- Trek has **no time-resolved PCP data**: nothing by local time, subsolar longitude (SLON) or Ls. For diurnal or seasonal cycles, PDS PCP stays the only source.
- Recommendation:
  - Get LOLA, the WAC mosaic, illumination and Earth-visibility data from the Trek ImageServer (bounding-box GeoTIFF, cached as COG).
  - Keep PDS for Diviner PCP and as the archival/fallback source for LOLA.
  - In the web viewer, use Trek WMTS for imagery basemaps, but host our own COGs or tiles for anything numeric.
  - Don't depend live on undocumented endpoints during the demo.

## 1. What exists today (confirmed in code)

| Script | Source | Access |
|---|---|---|
| `lola_hillshade.py` | USGS `Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif` (8.49 GB; now redirects 302 to `asc-pds-services.s3.us-west-2.amazonaws.com`, `Accept-Ranges: bytes`) | GDAL `/vsicurl` window read, 16 threads, saved locally as a COG. Slow because the file has 1-row strips and no overviews. |
| `south_pole.py` | PDS LOLA GDR `LDEM_75S_240M` (polar), `LDEM_4/16/64` (cylindrical) | Download once, convert to COG, reproject to IAU_2015:30135 at the output resolution (`render_config.py`, 1080x720) |
| `pcp_validate.py` | PDS Diviner PCP (`data_derived_pcp`), ASCII `.TAB`, about 36 + 36 + 31 GB for the south pole | HTTP Range sampling. The PDS server sometimes drops parallel connections. |

## 2. What Moon Trek exposes (verified)

**Catalog.**
- `https://trek.nasa.gov/moon/TrekServices/ws/index/{eq|polar}/searchItems?...` is a Solr JSON search.
- In south-polar projection (`urn:ogc:def:crs:IAU2000::30120`) it lists 890 items, of which 396 are data products.
- `.../getLayerServices?uuid=` returns each product's endpoints. Every product has WMTS; **101 of the 396** also have an ArcGIS ImageServer ("raster").
- Abstract and FGDC metadata endpoints work (`TrekWS/rest/cat/abstract|metadata`).
- The doc page `trek.nasa.gov/tiles/apidoc/trekAPI.html?body=moon` is generated from this catalog, and api.nasa.gov lists "Trek WMTS" (maintained by SSERVI and the JPL Trek team, no API key).

**WMTS (documented).**
- Capabilities: `https://trek.nasa.gov/tiles/Moon/{EQ|SP|NP}/<label>/1.0.0/WMTSCapabilities.xml`
- Tiles: `.../1.0.0/default/default028mm/{z}/{row}/{col}.png|jpg`
- South-polar tile grid (the same for every SP layer checked):
  - origin `(-1095930, 1095930)` m, 256 px tiles;
  - level 0 is 8562 m/px, and each level halves the pixel size;
  - level 0 is a 2x1 matrix, but only column 0 has data (`0/0/1` returns 404).
- Problems:
  - The SP capabilities declare CRS `urn:ogc:def:crs:EPSG::0`, put metres inside `WGS84BoundingBox`, and write `MatrixWidth` as `2.0`.
  - **owslib crashes** on this (`ValueError: '2.0'`) and **GDAL refuses it** (`Cannot parse CRS 'urn:ogc:def:crs:EPSG::0'`).
  - The equatorial capabilities (ESRI:104903) open fine in GDAL.
- Tiles are **8-bit gray+alpha PNG**. For example, a DEM tile holds the values 108–157, not metres. They are pictures, not data.
- The deepest zoom level is often **coarser than the source**:

  | Layer | Source resolution | Deepest WMTS level |
  |---|---|---|
  | LOLA 30 m DEM | 30 m | level 7 ≈ 67 m |
  | WAC 100 m mosaic | 100 m | level 5 ≈ 268 m |
  | Diviner 240 m | 240 m | level 4 ≈ 535 m |
  | LOLA 5 m DEM | 5 m | level 10 ≈ 8.4 m |

- Serving: `Access-Control-Allow-Origin: *`. There is no `Cache-Control` header and no CDN (plain Apache with ETag and Last-Modified).
- Latency: TLS 0.46 s, TTFB 0.66 s, about **1 s per tile**. 32 tiles fetched 16 at a time all returned 200 (median 1.03 s, max 1.12 s).

**ArcGIS ImageServer (public, CORS `*`, not documented for third parties).**
- Base: `https://trek.nasa.gov/moon/trekarcgis{,2}/rest/services/<label>/ImageServer`, ArcGIS 10.61.
- What it can do:
  - `exportImage?bbox=..&size=..&format=tiff&pixelType=F32&compression=LZ77&f=image` returns a georeferenced Float32 GeoTIFF. It resamples to any requested size, up to **15000 x 4100 px per request**; 5000x5000 was rejected.
  - `identify` (one point) and `getSamples` (many points, useful for profiles) work.
- Measured downloads:

  | Request | Size | Time |
  |---|---|---|
  | 30 m DEM, 1080x720 around the pole | 3.5 MB | 2.3 s |
  | 5 m DEM, native 2000x2000 | 16.8 MB raw / 6.5 MB LZ77 | 6.4 s raw / 3.6 s LZ77 |
  | Global 256 ppd DEM, Tycho box, 1920x1408 | 5.8 MB | 3.5 s |

- Checks against our data:
  - The Tycho crop is identical to our USGS crop (|Δ| p99 = 0 m).
  - The 30 m polar DEM vs our `LDEM_75S_240M` over Shackleton: median Δ 0.5 m, median |Δ| 2.3 m (expected from the resolution difference).
  - Heights are relative to the 1737.4 km sphere, like PDS.

**Full-product download.**
- `https://trek.nasa.gov/moon/TrekWS/rest/cat/data/stream?label=<label>` returns a GeoTIFF attachment.
- There is no `Content-Length` and **Range requests are ignored**: a 1 KB range request returned all 26 MB.
- Example: `polar_south_80_summer_max.tif` is 2533x2543 Float32, 240 m, our CRS, 128 px tiles, no overviews, uncompressed. It took 13 s (~2 MB/s).

**3D terrain (undocumented).**
- The Moon app config points at `https://marshub.s3.amazonaws.com/moon_v14/layer.json`: Cesium **quantized-mesh-1.0**, geographic TMS tiling, CORS `*`.
- It is global only up to **z9** (tiles of about 0.35°). No z10+ patch reaches south of 76.7°S, so terrain near the pole is coarse.
- The same config sets `controls.terrain=false`.

**Feature services.**
- ArcGIS MapServer `query?...&f=geojson` works.
- `PSR_SP` is 164 PSR **centroid points** with attributes, not polygons.
- `A3_Named_regions` returns the Artemis III candidate region polygons.

**Analysis tools** (profile, sun angle, lighting, slope, subset, LOS): listed in `trek.nasa.gov/moon/jpl/config/config.json`.
- Lighting is an asynchronous job that takes an e-mail address.
- **Unverified**: I didn't test their parameters. `getSamples` covers profiles.

## 3. Relevant south-pole layers on Trek

| Theme | Layer label (examples) | Resolution / extent | Raw values? |
|---|---|---|---|
| LOLA DEM | `LRO_LOLA_DEM_SPole45_100mp_v04`, `..._SPole75_30mp_v04`, `..._SPole875_5mp_v04` (+ `Count` and hillshade) | 100 m to 45°S; 30 m to 75°S; 5 m to 87.5°S | Yes, F32 ImageServer |
| LOLA global | `LRO_LOLA_DEM_Global_256ppd_v06` | 118 m, equirectangular | Yes, F32 ImageServer |
| Artemis site DEMs | `Site01/04/06/07/11/20/23_final_adj_5mpp_surf`, `DM2`, `Haworth`, `Shoemaker` (+ hillshade, slope, error) | 5 m, local | ImageServer only for Site20 and Site23; the others are WMTS-only (data/stream likely, **unverified**) |
| LROC WAC | `LRO_WAC_Mosaic_SPole60_100m_v02` | 100 m to 60°S | U8 ImageServer |
| LROC NAC | `LRO_NAC_Mosaic_SPole85.5_1mp`, `NAC_POLE_PSR_SOUTH_STRETCH` (20 m), site orthos and DEMs (0.5–3.5 m) | local | WMTS (sources are tens of GB) |
| Diviner (Williams 2019) | `polar_south_80_{summer,winter}_{avg,min,max,amplitude}`, `polar_south_80_sw_max_diff`, threshold masks (<50, 50–100, >100, <110 K) | 240 m, ≥80°S | F32 via data/stream (26 MB). ImageServer only for `DIVINER_*_Max_Temp_SP_below110K_240mp` (clipped 45–110 K) |
| Diviner global-derived | `diviner_tbol_{min,max,hour00,hour12,...}_SP` | 0.5 ppd (~2.4 km) | F64 ImageServer |
| Illumination / PSR | `WAC_POLE_ILL_{PCT,TWI}_SOUTH_100M`, `LRO_LOLA_Illumination_SPole65S_240m` (PSR mask 0/1), `PSR_SP` points | 100–240 m | WMTS, or data/stream for values |
| Visibility / ice | `AVGVISIB_*_EARTH_SP` (60–240 m), `SKYV_65S_240M_SP`, `sp_ice_depth_*_240m` | 60–240 m | F32 ImageServer |

The catalog has nothing comparable to PCP time slices. I searched all 1540 polar and 9391 equatorial items for pcp / cumulative / slon / ltim / local time and found no Diviner match. One data note: `polar_south_80_summer_max` reaches 439 K at a few pixels, which needs checking before use.

## 4. Comparison

| Criterion | Current (USGS / PDS) | Moon Trek | QuickMap (reference) |
|---|---|---|---|
| LOLA | Full archive; PDS GDR polar 240 m (and finer products in PDS) | Same LOLA v04 polar DEMs at 100/30/5 m plus 5 m site DEMs; global 256 ppd | DEM terrain only; `qts_demstack/layer.json` now returns **404** |
| LROC | Not fetched yet | WAC 100 m polar (values); NAC mosaics as WMTS | Rich NAC data (features API, COGs) but proprietary tiles |
| Diviner | PCP: full diurnal and seasonal cubes (~100 GB ASCII) | Season summaries only (avg/min/max/amp), 240 m GeoTIFF | – |
| Illumination / PSR | none | Yes: WAC illumination, PSR mask, Earth/sky visibility | Yes (undocumented) |
| Projection fit | PDS polar products are already polar stereographic; the USGS global file needs reprojecting | ImageServer output **is** our CRS; WMTS SP grid uses the same CRS but declares it non-standardly | Own polar terrain |
| Raw values | Yes | ImageServer and data/stream: yes. WMTS: no (8-bit) | Mostly no |
| Size / speed | Tycho crop ~2 min; PCP needs Range tricks | Bbox export 2–6 s for 1–17 MB; whole product ~2 MB/s; tiles ~1 s each | features-api: 18.9 MB in >30 s, Range ignored |
| Reliability | Archival, stable URLs; PDS drops parallel connections | Up throughout testing; no SLA, no cache headers; ImageServer undocumented | Endpoints changed (404) |
| Python static renders | Works now | Excellent through ImageServer (`requests` + rasterio). WMTS breaks owslib/GDAL in polar | Avoid |
| Web 2D (OpenLayers) | Needs our own tiling | SP WMTS works with a hand-written tile grid; CORS ok | Avoid |
| Web 3D (Cesium) | Needs our own terrain | EQ WMTS matches Cesium's geographic 2x1 scheme; quantized-mesh terrain coarse at the pole and undocumented | Avoid |
| Terms | PDS/USGS public archives, citable DOIs | Public NASA service; I found no explicit terms page (**unverified**). Cite the original data producers. | Commercial (ACT), undocumented |

## 5. Recommendation

**Static Python renders**
- **LOLA:** Replace the USGS `/vsicurl` read with ImageServer `exportImage`:
  - `LRO_LOLA_DEM_Global_256ppd_v06` for non-polar targets like Tycho;
  - `..._SPole75_30mp_v04` and `..._SPole875_5mp_v04` for the south pole;
  - pass `size=` equal to the render size and `compression=LZ77`.
  - Keep the existing COG cache.
  - Keep the PDS GDR path as a fallback and as the citable archive source.
- **LROC WAC, illumination, Earth visibility, ice stability:** Take them from Trek (ImageServer, or a one-off `data/stream` download when there is no ImageServer).
- **Diviner:**
  - Use Trek's `polar_south_80_{summer,winter}_{avg,min,max}` GeoTIFFs (26 MB each) for headline temperature maps and to cross-check our PCP decoding (same source paper).
  - **Keep PDS PCP** for anything time-resolved (local time, SLON, Ls). Convert the sampled or needed slices to COGs once, offline.

**Interactive viewer**
- *2D (OpenLayers, south polar stereographic):*
  - Register the proj4 definition and build a `WMTSTileGrid` by hand: origin `[-1095930, 1095930]`, resolutions `8562.0/2^z`, 256 px tiles.
  - Use Trek SP WMTS for basemap pictures: WAC, NAC, hillshade, PSR mask.
  - For numeric layers (temperature colormaps, value readout on hover) serve **our own COGs** from static hosting and render them client-side (OpenLayers GeoTIFF/WebGL source). Optionally use ImageServer `identify` for point readouts.
- *3D (CesiumJS):*
  - Use the Moon ellipsoid with Trek **EQ** WMTS imagery.
  - For south-pole relief, don't rely on `moon_v14` terrain: it's coarse at the pole and undocumented. Build a local terrain or mesh from the 30 m / 5 m LOLA export instead (quantized-mesh or heightmap tiles generated offline, or a local mesh for a polar-cap scene).
- *Caching:* Pre-fetch and store every export the demo uses (the bboxes are small), and put a thin cache/proxy in front of the Trek tiles. The demo must still run if trek.nasa.gov is slow or down.

Minimal Python pattern (verified):
```python
url = ("https://trek.nasa.gov/moon/trekarcgis/rest/services/LRO_LOLA_DEM_SPole75_30mp_v04/ImageServer/exportImage"
       "?bbox=-30000,-20000,30000,20000&size=1080,720&format=tiff&pixelType=F32"
       "&compression=LZ77&noData=-9999&f=image")
# -> GeoTIFF, float32 metres, CRS +proj=stere +lat_0=-90 +R=1737400; open with rasterio.MemoryFile
```

## 6. Open risks

1. **Undocumented endpoints.** ImageServer, TrekServices and the marshub terrain could change without notice; QuickMap's terrain URL already went 404. Mitigation: cache every export, keep the PDS fallback, isolate URLs in one config module.
2. **Request limits.** `exportImage` caps out at 15000 x 4100 px, so larger exports need tiling. `data/stream` doesn't support Range or Content-Length, so downloads can't be resumed.
3. **Latency.** About 1 s per tile with no HTTP caching, which is noticeable in an interactive viewer. Mitigation: a proxy cache or pre-baked tiles.
4. **Non-standard polar WMTS capabilities.** The tile grid has to be hard-coded. Max zoom is coarser than the source data for several layers (30 m DEM → 67 m tiles).
5. **Diviner semantics.** Trek has only the season summaries. Their "summer"/"winter" definition (by subsolar latitude) and the outlier maxima (439 K) must be reconciled with our PCP analysis before we show them side by side.
6. **Licensing.** I found no explicit Trek terms. Treat the data as NASA public data, credit "NASA Moon Trek (SSERVI/JPL)" plus the instrument teams and Williams et al. (2019), and confirm before publishing.
7. **The 5 m Artemis site DEMs** mostly have no ImageServer; raw access through `data/stream` is **unverified**.

## 7. URLs verified (2026-11-14)

| URL | Status / note |
|---|---|
| `https://trek.nasa.gov/moon/` | 200 (9.8 s) |
| `https://trek.nasa.gov/tiles/apidoc/` , `.../trekAPI.html`, `.../config/config.json`, `.../js/trekApi.js` | 200 |
| `https://trek.nasa.gov/moon/jpl/config/config.json` | 200 (list of app service endpoints) |
| `https://trek.nasa.gov/moon/TrekServices/ws/index/polar/searchItems?start=0&rows=5000&proj=urn:ogc:def:crs:IAU2000::30120` | 200, 890 items |
| `https://trek.nasa.gov/moon/TrekServices/ws/index/{eq,polar}/searchItems?start=0&rows=10000` | 200 (9391 / 1540 items) |
| `https://trek.nasa.gov/moon/TrekServices/ws/index/getLayerServices?uuid=<uuid>` | 200 |
| `https://trek.nasa.gov/tiles/Moon/SP/<label>/1.0.0/WMTSCapabilities.xml` (LOLA 30 m/5 m, WAC, Diviner, illumination, Site04) | 200 |
| `https://trek.nasa.gov/tiles/Moon/SP/` | 403 (no listing) |
| `.../SP/LRO_LOLA_DEM_SPole75_30mp_v04/1.0.0/default/default028mm/{0/0/0, 4/7/7, 7/63/63}.png` | 200; `0/0/1`, `8/127/127` → 404 |
| `.../SP/LRO_LOLA_DEM_SPole875_5mp_v04/.../{9/255/255,10/511/511}.png` | 200; `11/1023/1023` → 404 |
| `.../SP/LRO_WAC_Mosaic_SPole60_100m_v02/.../{3/3/3,5/15/15}.png` | 200; `6/31/31` → 404 |
| `.../SP/polar_south_80_summer_max/.../{2/1/1,4/7/7}.png` | 200; `5/15/15` → 404 |
| `https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/WMTSCapabilities.xml`, `.../0/0/0.jpg` | 200 |
| `https://trek.nasa.gov/moon/trekarcgis/rest/services/LRO_LOLA_DEM_SPole75_30mp_v04/ImageServer?f=json`, `/exportImage`, `/identify` | 200 |
| `.../trekarcgis/rest/services/LRO_LOLA_DEM_SPole875_5mp_v04/ImageServer` `?f=json`, `/exportImage`, `/getSamples`, `/keyProperties` | 200 (oversize request → JSON error 400 in body) |
| `.../trekarcgis/rest/services/LRO_LOLA_DEM_Global_256ppd_v06/ImageServer` `?f=json`, `/exportImage` | 200 |
| `.../trekarcgis/rest/services/{LRO_WAC_Mosaic_SPole60_100m_v02, DIVINER_summer_Max_Temp_SP_below110K_240mp}/ImageServer` | 200 |
| `.../trekarcgis2/rest/services/{diviner_tbol_max_SP, SKYV_65S_240M_SP, AVGVISIB_85S_060M_201608_EARTH_SP}/ImageServer?f=json` | 200 |
| `https://trek.nasa.gov/moon/trekarcgis/rest/services?f=json` | 200 (service directory) |
| `https://trek.nasa.gov/moon/TrekWS/rest/cat/data/stream?label=polar_south_80_summer_max` | 200, 26.2 MB GeoTIFF, Range ignored |
| `.../cat/data/stream?label={LRO_LOLA_DEM_128ppd_SiteC_SP, LRO_LOLA_DEM_SPole875_5mp_v04}` | HEAD 200 (`attachment; *.tif`) |
| `https://trek.nasa.gov/moon/TrekWS/rest/cat/abstract?label=...`, `.../metadata/fgdc/html?label=...` | 200 |
| `https://trek.nasa.gov/moon/trekarcgis/rest/services/PSR_SP/MapServer/0/query?...&f=geojson` | 200, 164 points |
| `https://trek.nasa.gov/moon/trekarcgis2/rest/services/A3_Named_regions/MapServer/0/query?...&f=geojson` | 200 |
| `https://trek.nasa.gov/tiles/Moon/rasters/sp/list.json` | 404 |
| `https://marshub.s3.amazonaws.com/moon_v14/layer.json`, `/0/0/0.terrain`, `/9/0/0.terrain` | 200 (CORS `*`); `/14/0/0`, `/12/100/0` → 404 |
| `http://moontrek.jpl.nasa.gov/trektiles/...` (old host on api.nasa.gov) | no response (dead) |
| `https://api.nasa.gov/assets/json/apis.json` | 200 (lists "Trek WMTS") |
| `https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif` | 302 → S3, 200, 8,494,203,833 B, Range ok |
| PDS `.../lola_gdr/polar/float_img/LDEM_75S_240M_FLOAT.IMG`, PDS `data_derived_pcp/` | 200 |
| `https://dem-tiles.b-cdn.net/lunar/qts_demstack/layer.json` (QuickMap) | **404** now |
| `https://features-api.quickmap.io/collections/nac.geojson` | 200 GET (18.9 MB, >30 s; HEAD → 405) |

Total downloaded during this evaluation: about 125 MB.
