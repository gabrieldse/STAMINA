# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pyproj"]
# ///
"""Validate the Diviner PCP spec against the real data, without downloading GBs.

Reads the collection inventory and the PDS4 labels of every south polar SLON
product (~4 MB), then samples a few thousand records from a handful of TAB
files with HTTP range requests (records are fixed width, ~15 MB in total).

    uv run pcp_validate.py

Writes output/pcp_validation.md and caches downloads in data/pcp_sample/.
"""

import math
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from pyproj import Transformer

PCP_URL = "https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_pcp"
MOON_RADIUS = 1737400.0
SOUTH_POLAR = "+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
NOMINAL_STEP_M = 240.0
ICE_THRESHOLD_K = 110

# Files sampled with range requests: SUM/WIN pairs at 4 points of the lunar
# day, and seasonal files at two subsolar longitudes and opposite Ls.
SAMPLED = [f"pcp_avg_tbol_pols_{s}_slon{n:02d}_240" for n in (1, 25, 49, 73) for s in ("sum", "win")]
SAMPLED += ["pcp_avg_tbol_pols_ls030_slon01_240", "pcp_avg_tbol_pols_ls030_slon13_240",
            "pcp_avg_tbol_pols_ls210_slon01_240"]
CHUNKS_PER_FILE = 16
RECORDS_PER_CHUNK = 1500

ROOT = Path(__file__).parent
CACHE = ROOT / "data" / "pcp_sample"
REPORT = ROOT / "output" / "pcp_validation.md"

NAME_RE = re.compile(
    r"pcp_avg_tbol_(?P<pole>pol[ns])_"
    r"(?:(?P<season>sum|win)_(?P<clock>ltim|slon)(?P<num>\d+)|ls(?P<ls>\d+)_slon(?P<snum>\d+))_240"
)


def fetch(url: str, dest: Path, byte_range: tuple[int, int] | None = None) -> bytes:
    if dest.exists():
        return dest.read_bytes()
    req = urllib.request.Request(url)
    if byte_range:
        req.add_header("Range", f"bytes={byte_range[0]}-{byte_range[1]}")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            break
        except (OSError, urllib.error.URLError) as err:
            # The PDS server drops connections under load: wait and retry.
            if attempt == 4:
                raise
            print(f"  retrying {url.rsplit('/', 1)[-1]} ({err})")
            time.sleep(2 ** attempt)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data


def product_dir(name: str) -> str:
    m = NAME_RE.fullmatch(name)
    if m["ls"]:
        return "seasonal/slon/pols"
    return f"diurnal/{m['clock']}/{m['pole']}"


def tag(block: str, name: str) -> str | None:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", block, re.S)
    return re.sub(r"\s+", " ", m[1]).strip() if m else None


def parse_label(xml: str) -> dict:
    table = xml[xml.index("<Table_Character>"):]
    fields = []
    for block in re.findall(r"<Field_Character>(.*?)</Field_Character>", table, re.S):
        fields.append({
            "name": tag(block, "name"), "unit": tag(block, "unit"),
            "location": int(tag(block, "field_location")), "length": int(tag(block, "field_length")),
            "min": float(tag(block, "minimum")), "max": float(tag(block, "maximum")),
            "description": tag(block, "description"),
        })
    return {
        "offset": int(re.search(r'<Table_Character>.*?<offset unit="byte">(\d+)', xml, re.S)[1]),
        "records": int(tag(table, "records")),
        "record_length": int(tag(table, "record_length")),
        "start": tag(xml, "start_date_time"), "stop": tag(xml, "stop_date_time"),
        "description": tag(table, "description"),
        "fields": fields,
    }


def sample_records(name: str, label: dict) -> dict[str, np.ndarray]:
    """Read CHUNKS_PER_FILE evenly spaced blocks of records with range requests."""
    url = f"{PCP_URL}/{product_dir(name)}/{name}.tab"
    rl = label["record_length"]
    starts = np.linspace(0, label["records"] - RECORDS_PER_CHUNK, CHUNKS_PER_FILE).astype(int)
    rows = []
    for i, rec in enumerate(starts):
        first = label["offset"] + rec * rl
        raw = fetch(url, CACHE / "tab" / f"{name}.{i:02d}", (first, first + RECORDS_PER_CHUNK * rl - 1))
        for k in range(0, len(raw) - rl + 1, rl):
            line = raw[k:k + rl].decode("ascii")
            rows.append([float(line[f["location"] - 1:f["location"] - 1 + f["length"]].strip(" ,"))
                         for f in label["fields"]])
    arr = np.array(rows)
    return {f["name"]: arr[:, i] for i, f in enumerate(label["fields"])}


def fit_axis(values_m: np.ndarray) -> tuple[float, float, float]:
    """Fit centres = origin + k*step. Returns (step, phase = origin/step mod 1, max residual)."""
    u = np.unique(values_m)
    # Consecutive unique values are at most a few hundred bins apart, so rounding
    # each gap with the nominal step gives exact bin indices.
    k = np.concatenate([[0], np.cumsum(np.round(np.diff(u) / NOMINAL_STEP_M))])
    step, origin = np.polyfit(k, u, 1)
    residual = u - (origin + k * step)
    return step, (origin / step) % 1, np.abs(residual).max()


def main() -> None:
    out: list[str] = ["# Diviner PCP spec validation", ""]

    def say(line: str = "") -> None:
        print(line)
        out.append(line)

    # --- Inventory: which files exist ------------------------------------------------
    inv = fetch(f"{PCP_URL}/collection_data_derived_pcp_inventory.csv", CACHE / "inventory.csv").decode()
    names = [m[0] for m in (NAME_RE.search(line) for line in inv.splitlines()) if m]
    pols = [n for n in names if "_pols_" in n]
    diurnal_slon = sorted(n for n in pols if "_slon" in n and ("_sum_" in n or "_win_" in n))
    diurnal_ltim = sorted(n for n in pols if "_ltim" in n)
    seasonal = sorted(n for n in pols if "_ls" in n)
    ls_bins = sorted({int(NAME_RE.fullmatch(n)["ls"]) for n in seasonal})
    seasonal_slon = sorted({int(NAME_RE.fullmatch(n)["snum"]) for n in seasonal})
    diurnal_nums = sorted({int(NAME_RE.fullmatch(n)["num"]) for n in diurnal_slon})
    say("## Inventory (south pole only)")
    say(f"- diurnal SLON: {len(diurnal_slon)} files, NUM {diurnal_nums[0]}..{diurnal_nums[-1]} "
        f"({len(diurnal_nums)} bins = {360 / len(diurnal_nums):g}° each), SUM and WIN")
    say(f"- diurnal LTIM: {len(diurnal_ltim)} files")
    say(f"- seasonal: {len(seasonal)} files, Ls bins {ls_bins}, SLON NUM {seasonal_slon[0]}..{seasonal_slon[-1]} "
        f"({len(seasonal_slon)} bins = {360 / len(seasonal_slon):g}° each)")
    say(f"- file names on the server are lower case: {all(n == n.lower() for n in pols)}")
    say()

    # --- Labels of every SLON product -------------------------------------------------
    targets = diurnal_slon + seasonal
    with ThreadPoolExecutor(4) as pool:
        xmls = list(pool.map(lambda n: fetch(f"{PCP_URL}/{product_dir(n)}/{n}.xml",
                                             CACHE / "labels" / f"{n}.xml").decode(), targets))
    labels = {n: parse_label(x) for n, x in zip(targets, xmls)}

    # --- 1. SUM / WIN meaning ----------------------------------------------------------
    say("## 1. SUM / WIN")
    for season in ("sum", "win"):
        d = labels[f"pcp_avg_tbol_pols_{season}_slon01_240"]["description"]
        say(f"- {season.upper()} label: \"...{re.search(r'with subsolar latitude[^.]*', d)[0]}\"")
    samples = {n: sample_records(n, labels[n]) for n in SAMPLED}
    for n in (1, 25, 49, 73):
        s, w = samples[f"pcp_avg_tbol_pols_sum_slon{n:02d}_240"], samples[f"pcp_avg_tbol_pols_win_slon{n:02d}_240"]
        key = lambda d: {(round(x, 6), round(y, 6)): t for x, y, t in zip(d["x"], d["y"], d["tbol"])}
        ks, kw = key(s), key(w)
        common = ks.keys() & kw.keys()
        diff = np.array([ks[c] - kw[c] for c in common])
        say(f"- SLON{n:02d}: mean SUM {s['tbol'].mean():.1f} K, WIN {w['tbol'].mean():.1f} K; "
            f"on {len(common)} shared pixels SUM - WIN = {diff.mean():+.1f} K (SUM warmer at {np.mean(diff > 0):.0%})")
    say()

    # --- 2 & 3. Columns and units ------------------------------------------------------
    say("## 2-3. Columns and units (from the labels)")
    for kind, n in (("diurnal", "pcp_avg_tbol_pols_sum_slon01_240"), ("seasonal", "pcp_avg_tbol_pols_ls030_slon01_240")):
        lab = labels[n]
        cols = ", ".join(f"{f['name']} [{f['unit']}]" for f in lab["fields"])
        say(f"- {kind}: {len(lab['fields'])} columns: {cols}; header {lab['offset']} B, record {lab['record_length']} B")
    x = labels["pcp_avg_tbol_pols_sum_slon01_240"]["fields"][0]
    say(f"- x is labeled '{x['unit']}' but ranges {x['min']}..{x['max']} and is described as "
        f"\"{x['description']}\": it is dimensionless, not degrees")
    say()

    # --- 4. Grid -----------------------------------------------------------------------
    say("## 4. Grid")
    xs = np.concatenate([d["x"] for d in samples.values()]) * MOON_RADIUS
    ys = np.concatenate([d["y"] for d in samples.values()]) * MOON_RADIUS
    for axis, v in (("x", xs), ("y", ys)):
        step, phase, res = fit_axis(v)
        say(f"- {axis}: step {step:.4f} m, origin phase {phase:.3f} (0 = bin centred on the pole, 0.5 = edge), "
            f"max residual {res:.2f} m")
    say(f"- 6-decimal coordinates quantize positions to {MOON_RADIUS * 1e-6:.2f} m")
    all_rows = {k: np.concatenate([d[k] for d in samples.values()]) for k in ("x", "y", "clon", "clat")}
    to_lonlat = Transformer.from_crs(SOUTH_POLAR, "+proj=longlat +R=1737400 +no_defs", always_xy=True)
    lon, lat = to_lonlat.transform(all_rows["x"] * MOON_RADIUS, all_rows["y"] * MOON_RADIUS)
    dlon = (lon - all_rows["clon"] + 180) % 360 - 180
    far = np.abs(all_rows["clat"]) < 89.9  # longitude is meaningless right at the pole
    say(f"- pyproj stereographic x/y -> lat/lon vs file columns: max |dlat| {np.abs(lat - all_rows['clat']).max():.2e}°, "
        f"max |dlon| {np.abs(dlon[far]).max():.2e}° (|lat| < 89.9°)")
    r = np.hypot(all_rows["x"], all_rows["y"])
    lat_eqd = np.degrees(r) - 90
    say(f"- if x/y were azimuthal equidistant instead: max |dlat| {np.abs(lat_eqd - all_rows['clat']).max():.3f}°")
    say()

    # --- 5. Time ranges ----------------------------------------------------------------
    say("## 5. Time ranges")
    for kind, group in (("diurnal SLON", diurnal_slon), ("seasonal", seasonal)):
        spans = {(labels[n]["start"], labels[n]["stop"]) for n in group}
        say(f"- {kind}: {sorted(spans)}")
    say()

    # --- 6. Ls definition --------------------------------------------------------------
    say("## 6. Ls definition")
    d = labels["pcp_avg_tbol_pols_ls030_slon01_240"]["description"]
    say(f"- label: \"...{re.search(r'with ecliptic longitude[^.]*', d)[0]}\"")
    hits = [n for n in seasonal if re.search(r"ecliptic longitude \(L_s\) is|L_s is defined|defined as", labels[n]["description"])]
    say(f"- labels that define the reference of Ls: {len(hits)} of {len(seasonal)}")
    for ls in ls_bins:
        dd = labels[f"pcp_avg_tbol_pols_ls{ls:03d}_slon01_240"]["description"]
        say(f"  - ls{ls:03d}: {re.search(r'L_s\) [^ ]+ to [^ ]+ degrees', dd)[0]}")
    say()

    # --- 7. SLON bin edges -------------------------------------------------------------
    say("## 7. SLON bins")
    for n in (1, 2, 96):
        dd = labels[f"pcp_avg_tbol_pols_sum_slon{n:02d}_240"]["description"]
        m = re.search(r"subsolar longitude[^.]*?(\d[\d.]* to [\d.]+ degrees)", dd)
        say(f"- diurnal SLON{n:02d}: label says {m[1] if m else 'no bin range; only ' + re.search(r'[\d.]+ deg of subsolar longitude', dd)[0]}")
    for n in (1, 13):
        name = f"pcp_avg_tbol_pols_ls030_slon{n:02d}_240"
        dd = labels[name]["description"]
        say(f"- seasonal SLON{n:02d}: label says {re.search(r'subsolar longitude ([\d.]+ to [\d.]+) degrees', dd)[1]}°")
        s = samples[name]
        # Local time = 12 h + (lon - subsolar lon) / 15°, so the data itself gives the subsolar longitude.
        slon = (s["clon"] - (s["ltim"] - 12) * 15) % 360
        ok = np.abs(s["clat"]) < 89.5
        say(f"  - from ltim and clon: subsolar longitude median {np.median(slon[ok]):.2f}°, "
            f"5-95% {np.percentile(slon[ok], 5):.2f}..{np.percentile(slon[ok], 95):.2f}°, "
            f"formula (NUM-0.5)*15 gives centre {(n - 0.5) * 15:g}°")
    say()

    # --- Acceptance: TBOL range and empty bins from the labels -------------------------
    say("## Acceptance: TBOL range and empty bins (all SLON files, from label statistics)")
    step, _, _ = fit_axis(xs)
    rmax = labels[diurnal_slon[0]]["fields"][0]["max"] * MOON_RADIUS
    n_pixels = math.pi * rmax**2 / step**2
    for kind, group in (("diurnal SUM", [n for n in diurnal_slon if "_sum_" in n]),
                        ("diurnal WIN", [n for n in diurnal_slon if "_win_" in n]), ("seasonal", seasonal)):
        tmin = [next(f["min"] for f in labels[n]["fields"] if f["name"] == "tbol") for n in group]
        tmax = [next(f["max"] for f in labels[n]["fields"] if f["name"] == "tbol") for n in group]
        empty = [1 - labels[n]["records"] / n_pixels for n in group]
        low = sum(t < 20 for t in tmin)
        say(f"- {kind}: TBOL {min(tmin):.1f}..{max(tmax):.1f} K, {low} of {len(group)} files below 20 K; "
            f"empty bins {min(empty):.1%}..{max(empty):.1%} of the ~{n_pixels / 1e6:.2f} M pixels to 80°S")
    cold = np.concatenate([d["tbol"] for d in samples.values()])
    say(f"- sampled records: {len(cold)}, TBOL {cold.min():.1f}..{cold.max():.1f} K, "
        f"{np.mean(cold < ICE_THRESHOLD_K):.0%} below {ICE_THRESHOLD_K} K")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(out) + "\n")
    print(f"\nReport saved to {REPORT}")


if __name__ == "__main__":
    main()
