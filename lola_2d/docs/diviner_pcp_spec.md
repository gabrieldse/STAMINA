# Task: Lunar south-pole surface temperature tool from Diviner PCP data

Revised spec. Items marked **[fixed]** were corrected against the real data with
`pcp_validate.py` (labels of all 336 south polar SLON products plus 264 000 sampled
records from 11 files, ~20 MB downloaded). Full output: `output/pcp_validation.md`.

## Context
Mission-planning analysis for candidate Artemis landing sites near the lunar south
pole. Build a Python tool that turns LRO Diviner **Polar Cumulative Products (PCP)**
into (1) temperature heatmaps and (2) site-level temperature timelines.
Use **PCP only**: no Polar Resource Product (PRP), no global Diviner products.

LOLA 5 m/pix DEM GeoTIFFs (e.g. `Site23_final_adj_5mpp_surf.tif`) are in south polar
stereographic, metres, sphere R = 1737.4 km. All outputs must line up with them.

Stack: Python 3.11, numpy, pandas, pyproj, rasterio, matplotlib, spiceypy (optional, step 6).

Rendering: every static image is at most **1080x720 px** (configurable with
`--width/--height`, see `render_config.py`). Maps are computed at the resolution
the image can show; interactive views will use other resolutions later.

## What the PCP data is (verified)
- Source: Diviner L1 RDR radiances, nadir observations, binned at 240 m/pix.
- **[fixed] Time spans differ by set:** diurnal 2009-07-05 → 2019-02-17
  (Williams et al. 2019, JGR 124); seasonal 2009-07-05 → **2020-03-15**
  (Schorghofer & Williams 2020, PSJ 1, 54). Take them from each label.
- Coverage: south cap −90° to −80°. Use only `pols` files.
- Value: `tbol` = mean bolometric brightness temperature, kelvin.
- **[fixed] Layout:** fixed-width ASCII, CRLF records, one header record, empty bins omitted.
  Read field names, positions and lengths from the PDS4 label (`.xml`; a PDS3 `.lbl`
  also exists).

  | Set | Columns | Record |
  |---|---|---|
  | diurnal | `x, y, clon, clat, tbol` | 59 B |
  | seasonal | `x, y, clon, clat, ltim, tbol` (**6 columns**) | 68 B |

- **[fixed] Units: don't trust them blindly.** The labels give `deg` for `x` and `y`,
  but these are dimensionless: polar stereographic coordinates divided by 1737.4 km
  (range ±0.174908). Validate units against value ranges.
- **[fixed] x, y are polar stereographic** (not distance along the surface):
  `x = r·sin(lon)`, `y = r·cos(lon)`, `r = 2·tan(colat/2)`. pyproj with the CRS below
  reproduces `clat` to 4e-5° and `clon` to 3e-3°; azimuthal equidistant would be 0.026° off.
- **[fixed] Grid:** regular, **centred on the pole** (a bin centre at x = y = 0),
  step **240.036 m** (= 0.174908 × 1737400 / 1266), i.e. 2533 × 2533 bins out to 80°S.
  Residuals after fitting are ≤ 0.92 m, which is the 1.74 m quantization of the
  6-decimal coordinates. Fit the step and origin from the data; don't assume 240.000 m
  (that gives up to ~44 m errors).
- **[fixed] Empty bins:** 31–46% of the ~5.04 M bins inside 80°S, per file
  (`1 − records / bins`, from the label record count).
- File names are **lower case** on the server; match case-insensitively.
  - Diurnal: `pcp_avg_tbol_pols_{sum|win}_{ltim|slon}{NUM}_240.tab`, NUM = 01–96.
    LTIM bin start = (NUM−1)×0.25 h; SLON bin start = (NUM−1)×3.75°.
  - Seasonal: `pcp_avg_tbol_pols_ls{NUMLS}_slon{NUM}_240.tab`.
    **[fixed]** NUMLS ∈ {030, 090, 150, 210, 270, 330} (60°-wide bins, centre ± 30°);
    NUM = 01–24, **15° wide**: SLON bin start = (NUM−1)×15°.
    Confirmed from the data: `ltim` and `clon` give a subsolar longitude of exactly
    7.5° in slon01 and 187.5° in slon13 (bin centres), using
    `local time = 12 h + (lon − slon)/15°`.
- **[fixed] SUM/WIN** come from the labels: SUM = "subsolar latitude less than zero
  degrees (summer season)", WIN = "greater than zero (winter season)". For the south
  pole SUM is southern **summer**, and the data agree: on shared pixels SUM is
  6–10 K warmer than WIN on average (80–94% of pixels). Label outputs
  "southern summer/winter" from the label, and keep the data check as a sanity test.
- **[fixed] Ls definition is missing from the labels**, and their descriptions are
  wrong: all six Ls bins say "L_s 0 to 60 degrees" (copy-paste). Take the Ls bin from
  the file name, and the definition of Ls from Schorghofer & Williams (2020).
- Inventory: `data_derived_pcp/collection_data_derived_pcp_inventory.csv` lists every
  product; use it instead of scraping HTML listings.
- Sizes (south pole): diurnal SLON 192 files / 36 GB, diurnal LTIM 192 / 36 GB,
  seasonal 144 / 31 GB. Files are ~200 MB and ~3.2 M rows each.
- Data: https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_pcp/

## Steps

### 1. Fetch (`fetch.py`)
- Build the file list from the inventory CSV; keep only `pols` products plus their `.xml` labels.
- **Print the file count and total size before downloading, and ask for confirmation.**
- Options: `--set diurnal|seasonal|all`, `--type SLON|LTIM` (default SLON),
  `--cache-dir`, skip existing files, resume partial downloads (HTTP Range).
- The PDS server drops parallel connections: at most 4 at a time, retry with back-off.
- `--delete-after-grid`: remove each `.tab` once it is gridded (saves ~67 GB).
- Records are fixed width, so `--sample` mode reads only chosen record ranges with
  HTTP Range (as `pcp_validate.py` does) for quick tests.

### 2. Parse & grid (`grid.py`)
- Column layout from the label; stream each file in chunks.
- Convert x, y to metres (×1,737,400), fit step and origin (see above), snap to bin
  indices, and report the maximum snapping residual (expected < 1 m).
- `--max-colat` **defaults to 6°** (84–90°S, ~1520² bins); 10° is the full product.
  A full 10° cube is ~2533² × 96 × 4 B ≈ 2.5 GB per season.
- Float32 cubes `T[bin, row, col]` for diurnal SUM, diurnal WIN and seasonal (Ls × SLON),
  NaN for empty bins, cached to disk (.npz / netCDF / zarr).

### 3. Envelope maps (`maps.py`)
- Per pixel: `Tmax`, `Tmin`, `Trange`, `Tmean`, `n_valid`,
  (a) over all bins and (b) per season (SUM, WIN, each Ls bin).
- GeoTIFFs: CRS `+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs`,
  pixel size = fitted step, transform built so the pole is a **pixel centre**
  (N = 2533 is odd, so the upper-left corner is at x = −(N/2)·step, y = +(N/2)·step), NoData = NaN.
- PNG previews (≤ 1080x720): colorbar in K, black 110 K contour, circles at −84/−86/−88°,
  optional footprints and names of LOLA GeoTIFFs.
- README caveat: these are max/min of bin averages (10 years; time and season bins), so
  they underestimate instantaneous extremes; SUM/WIN each mix half a year.

### 4. Time axis (`timeaxis.py`)
- Use subsolar longitude (SLON) as the clock near the pole; prefer SLON files.
- Synodic month 29.530589 d: 3.75° ≈ 7.38 h, 15° ≈ 1.23 d.
- The subsolar point moves westward (SLON decreases with time); confirm with step 6.

### 5. Site timeline (`site.py`)
- Site as lat/lon, x/y in metres, or a LOLA GeoTIFF footprint; optional radius
  (mean and spread over the pixels inside).
- Outputs: TBOL vs time over one lunar day, one curve per season bin, 110 K line
  (≤ 1080x720); CSV of the same data; daily min / max / mean table per season.

### 6. Mission window (`mission.py`)
- Input: `--start 2028-03-01T00:00 --duration 6.5d`.
- SPICE: the repo already has `SMEData/Kernels` (`naif0012.tls`, `pck00011.tpc`,
  `de440s.bsp`). `IAU_MOON` is precise enough to choose a 3.75° SLON bin; `MOON_ME`
  (needs `moon_pa_de421_1900-2050.bpc`, `moon_080317.tf`, `moon_assoc_me.tf`) is an optional refinement.
- Subsolar longitude and latitude hourly through the window. Season from the sign of
  the subsolar latitude (SUM if < 0). Ls bin: from the Schorghofer & Williams (2020)
  definition if implemented; otherwise require `--ls` and print a warning.
- Map each step to its SLON bin, extract the site's TBOL, report min / max / mean over
  the window, and redo the step-5 plot with the window shaded.
- Fallback without SPICE: `--slon-start`.

### 7. LOLA alignment (`align.py`)
- Resample a PCP map onto a LOLA GeoTIFF grid (nearest neighbour; 240 m vs 5 m gives blocks).
- Overlay PNG (≤ 1080x720): LOLA hillshade plus semi-transparent temperature.

### 8. CLI + README
- `python pcp_tool.py fetch|build|maps|site|mission ...` with `--help`.
- README with example commands for Site23 (Malapert) and Haworth.

## Acceptance checks
- **[fixed] TBOL range:** label minima are 6.7–6.9 K in every diurnal file and below
  20 K in 125 of 144 seasonal files; maxima reach 439 K. A 20–420 K rule would fail
  every file. Check 5–450 K, and report the fraction below 20 K and above 400 K per file.
- Empty-bin (NaN) fraction per file.
- Grid round-trip: pixel x/y → lat/lon via pyproj matches the `clat` column to < 1e-4°
  and `clon` to < 1e-2° away from the pole (|lat| < 89.9°).
- Grid fit residual < 1 m on both axes.
- SUM warmer than WIN on most shared pixels.
- *(The original spec was cut off here: "matches the file's lat/lon columns to within 1…".)*
