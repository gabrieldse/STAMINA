import { useEffect, useMemo, useState } from "react";
import MapPanel from "./MapPanel";
import type { ComponentProps } from "react";
import { LANDING_SITES } from "../../types/sites";
import type { VisiblePolarSite } from "../../types/sites";
import { apiErrorMessage } from "../../services/apiError";

export type BodyPositions = { sun: number[]; earth: number[]; utc: string };
type PositionSeries = { times: string[]; sun: number[][]; earth: number[][] };
type Props = Omit<ComponentProps<typeof MapPanel>, "positions" | "positionStatus" | "onVisibleSitesChange"> & { durationDays: number };
const utc = (value: string) => value.replace("T", " ").replace(":00Z", " UTC");

type Horizon = { observerM: number[]; horizonRadians: number[] };
function visible(vector: number[], latitude: number, longitude: number, horizon: Horizon) {
  const lat = latitude*Math.PI/180, lon = longitude*Math.PI/180;
  const up = [Math.cos(lat)*Math.cos(lon), Math.cos(lat)*Math.sin(lon), Math.sin(lat)];
  const east = [-Math.sin(lon), Math.cos(lon), 0];
  const north = [-Math.sin(lat)*Math.cos(lon), -Math.sin(lat)*Math.sin(lon), Math.cos(lat)];
  const v = vector.map((x, i) => x*1000-horizon.observerM[i]);
  const dot = (axis: number[]) => v.reduce((sum, x, i) => sum+x*axis[i], 0);
  const e = dot(east), n = dot(north);
  const az = (Math.atan2(e,n)+2*Math.PI)%(2*Math.PI);
  return Math.atan2(dot(up),Math.hypot(e,n)) > horizon.horizonRadians[Math.min(719,Math.floor(az*720/(2*Math.PI)))];
}

// Keep the map/menu mounted when changing mission dates, preserving custom sites and center.
export default function MapTimeline(props: Props) {
  return <TimelineWindow {...props} />;
}

function TimelineWindow({ durationDays, ...props }: Props) {
  const windowKey = `${props.date}-${durationDays}`;
  const [loadedSeries, setLoadedSeries] = useState<{ key: string; value: PositionSeries } | null>(null);
  const series = loadedSeries?.key === windowKey ? loadedSeries.value : null;
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [visibilityReady, setVisibilityReady] = useState(false);
  const [speed, setSpeed] = useState(6);
  const sunThreshold = props.filters.sunVisibility?.enabled ?? false;
  const earthThreshold = props.filters.earthVisibility?.enabled ?? false;
  const enabled = sunThreshold || earthThreshold;
  const [horizons, setHorizons] = useState<Record<string, Horizon>>({});
  const [horizonErrors, setHorizonErrors] = useState<Record<string, string>>({});
  const [sites, setSites] = useState<VisiblePolarSite[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    setIndex(0);
    setPlaying(false);
    setError("");
    async function load() {
      try {
        const base = import.meta.env.VITE_API_URL ?? "";
        const response = await fetch(`${base}/api/position-timeline?date=${encodeURIComponent(props.date)}&durationDays=${durationDays}`, { signal: controller.signal });
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(apiErrorMessage(body, response.status));
        }
        const data: PositionSeries = await response.json();
        if (!data.times?.length || data.sun?.length !== data.times.length || data.earth?.length !== data.times.length) throw new Error("Incomplete ephemeris response.");
        if (!controller.signal.aborted) setLoadedSeries({ key: windowKey, value: data });
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Timeline unavailable.");
      }
    }
    void load();
    return () => controller.abort();
  }, [props.date, durationDays, attempt, windowKey]);

  const last = (series?.times.length ?? 1) - 1;
  useEffect(() => {
    if (!playing || !series || index >= last || (enabled && !visibilityReady)) return;
    const timer = window.setInterval(() => setIndex(previous => Math.min(previous + 1, last)), 1000 / speed);
    return () => window.clearInterval(timer);
  }, [playing, series, last, speed, index, enabled, visibilityReady]);
  const positions = useMemo(() => series ? { sun: series.sun[index], earth: series.earth[index], utc: series.times[index] } : null, [series, index]);
  useEffect(() => {
    const controller = new AbortController();
    // Publish each result immediately. One unavailable site must not hide all others.
    // Keep DEM calculations sequential to bound server memory during initial loading.
    async function loadHorizons() {
      const selectedId = props.selectedSite?.id;
      const ordered = [...sites].sort((a, b) => Number(b.id === selectedId) - Number(a.id === selectedId));
      for (const site of ordered) {
        if (controller.signal.aborted) return;
        try {
          const response = await fetch(`${import.meta.env.VITE_API_URL ?? ""}/api/horizon?latitude=${site.latitude}&longitude=${site.longitude}`, { signal: controller.signal });
          const data = await response.json();
          if (!response.ok) throw new Error(apiErrorMessage(data, response.status));
          if (!Array.isArray(data.observerM) || data.observerM.length !== 3 ||
            !Array.isArray(data.horizonRadians) || data.horizonRadians.length !== 720) {
            throw new Error("Incomplete terrain horizon response.");
          }
          if (!controller.signal.aborted) {
            setHorizons(previous => ({ ...previous, [site.id]: data }));
            setHorizonErrors(previous => ({ ...previous, [site.id]: "" }));
          }
        } catch (cause) {
          if (!controller.signal.aborted) setHorizonErrors(previous => ({ ...previous, [site.id]: cause instanceof Error ? cause.message : "Terrain horizon unavailable." }));
        }
      }
    }
    void loadHorizons();
    return () => controller.abort();
  }, [sites, props.selectedSite?.id, attempt]);
  const rows = useMemo(() => sites.map(site => {
    const horizon = horizons[site.id];
    const sun = series?.sun.map(vector => horizon ? visible(vector, site.latitude, site.longitude, horizon) : null) ?? [];
    const earth = series?.earth.map(vector => horizon ? visible(vector, site.latitude, site.longitude, horizon) : null) ?? [];
    const passes = sun.map((angle, i) => Boolean(horizon) && (!sunThreshold || angle === true) && (!earthThreshold || earth[i] === true));
    const runs: { start: number; end: number; pass: boolean }[] = [];
    passes.forEach((pass, i) => {
      if (runs.length && runs[runs.length - 1].pass === pass) runs[runs.length - 1].end = i + 1;
      else runs.push({ start: i, end: i + 1, pass });
    });
    return { site, sun, earth, passes, runs, ready: Boolean(horizon) };
  }), [sites, series, sunThreshold, earthThreshold, horizons]);

  const selectedRow = rows.find(row => row.site.id === props.selectedSite?.id);
  const visibilityStatus = enabled && selectedRow
    ? `${selectedRow.site.name}: ${!selectedRow.ready
      ? horizonErrors[selectedRow.site.id] || "calculating terrain horizon..."
      : [sunThreshold ? `Sun ${selectedRow.sun[index] ? "visible" : "obstructed"}` : "",
        earthThreshold ? `Earth ${selectedRow.earth[index] ? "visible" : "obstructed"}` : ""].filter(Boolean).join(" · ")}`
    : "";
  function seek(next: number) { setPlaying(false); setIndex(next); }
  return <>
    <div className="explorer-map-area"><MapPanel {...props} positions={positions} playing={playing && index < last} onVisibilityReady={setVisibilityReady} onVisibleSitesChange={setSites} positionStatus={error || (!series ? "Loading ephemeris…" : visibilityStatus)} /></div>
    <div className="explorer-timeline map-timeline">
      <div className="explorer-timeline-heading"><strong>Landing sites · time explorer</strong><span>SPICE · 1-hour samples · UTC</span></div>
      {error ? <p role="alert">{error} <button type="button" onClick={() => { setError(""); setAttempt(value => value + 1); }}>Retry</button></p> : !series ? <p role="status">Loading Sun and Earth positions…</p> : <>
        <div className="map-time-controls">
          <button type="button" onClick={() => { if (index === last) setIndex(0); setPlaying(!playing || index === last); }}>{playing && index < last ? "Pause" : "Play"}</button>
          <button type="button" aria-label="Previous hour" disabled={index === 0} onClick={() => seek(index - 1)}>−1 h</button>
          <button type="button" aria-label="Next hour" disabled={index === last} onClick={() => seek(index + 1)}>+1 h</button>
          <label>Speed <select value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={1}>1 h / s</option><option value={6}>6 h / s</option><option value={12}>12 h / s</option></select>{enabled && " (visibility: waits for terrain map)"}</label>
          <strong>{utc(series.times[index])}</strong>
        </div>
        <label className="mission-scrubber">Observation time
          <input type="range" min={0} max={last} step={1} value={index} onChange={event => seek(Number(event.target.value))} aria-valuetext={utc(series.times[index])} />
        </label>
        <div className="explorer-timeline-labels"><span>{utc(series.times[0])}</span><span>{utc(series.times[last])}</span></div>
        <details className="map-timeline-details" open={enabled || undefined}>
          <summary>Landing site visibility & details</summary>
        <p>{enabled ? "Green: all enabled bodies clear the terrain horizon · Dark: obstructed or unavailable" : "Enable Sun visibility or Earth visibility to highlight site time windows."}</p>
        {sites.length === 0 && <p>No polar sites enabled. Switch on a site in the Landing sites menu.</p>}
        {sites.some(site => Boolean(horizonErrors[site.id])) && <button type="button" onClick={() => { setHorizonErrors({}); setAttempt(value => value + 1); }}>Retry terrain horizons</button>}
        {sites.some(site => !horizons[site.id] && !horizonErrors[site.id]) && <p role="status">Calculating LOLA terrain horizons...</p>}
        <div className="map-site-timelines">
          {rows.map(({ site, sun, earth, passes, runs, ready }) => <div className="map-site-time-row" key={site.id}>
            <button type="button" className={props.selectedSite?.id === site.id ? "selected" : ""} onClick={() => props.onSiteSelect({ ...site, details: LANDING_SITES.find(item => item.id === site.id) })}>{site.name}</button>
            <div className="mission-visibility-bar" aria-label={`${site.name} terrain visibility windows`}>
              {runs.map(run => <button type="button" key={run.start} className={`mission-segment ${enabled && run.pass ? "matching" : "unavailable"}`} style={{ width: `${100 * (run.end - run.start) / series.times.length}%` }} title={`${utc(series.times[run.start])}: ${!enabled ? "No visibility filter" : run.pass ? "Matches" : "Obstructed or unavailable"}`} onClick={() => seek(run.start)} aria-label={`Inspect ${site.name} at ${utc(series.times[run.start])}`} />)}
              <span className="mission-time-cursor" style={{ left: `${100 * (index + .5) / series.times.length}%` }} />
            </div>
            <span className={ready && enabled && passes[index] ? "site-time-match" : ""}>{!ready ? horizonErrors[site.id] ? "Unavailable" : "Calculating..." : enabled ? passes[index] ? "Match" : "Obstructed" : "No filter"} · Sun {sun[index] == null ? "pending" : sun[index] ? "visible" : "hidden"} · Earth {earth[index] == null ? "pending" : earth[index] ? "visible" : "hidden"}</span>
            {horizonErrors[site.id] && <small role="alert">{horizonErrors[site.id]}</small>}
          </div>)}
        </div>
        <small>Animated ephemeris preview, not live telemetry. LOLA 240 m terrain horizons, 0.5-degree azimuth sectors; body centers at surface height. Window follows mission start and duration.</small>
        </details>
      </>}
    </div>
  </>;
}
