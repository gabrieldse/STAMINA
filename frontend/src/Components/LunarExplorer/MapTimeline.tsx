import { useEffect, useMemo, useState } from "react";
import MapPanel from "./MapPanel";
import type { ComponentProps } from "react";
import { LANDING_SITES, isOnPolarMap } from "../../types/sites";

export type BodyPositions = { sun: number[]; earth: number[]; utc: string };
type PositionSeries = { times: string[]; sun: number[][]; earth: number[][] };
type Props = Omit<ComponentProps<typeof MapPanel>, "positions" | "positionStatus"> & { durationDays: number };
const utc = (value: string) => value.replace("T", " ").replace(":00Z", " UTC");

function elevation(vector: number[], latitude: number, longitude: number) {
  const lat = latitude * Math.PI / 180, lon = longitude * Math.PI / 180;
  const up = [Math.cos(lat) * Math.cos(lon), Math.cos(lat) * Math.sin(lon), Math.sin(lat)];
  const relative = vector.map((v, i) => v - 1737.4 * up[i]);
  return Math.asin(Math.max(-1, Math.min(1, relative.reduce((sum, v, i) => sum + v * up[i], 0) / Math.hypot(...relative)))) * 180 / Math.PI;
}

// Remount on mission-window changes: old frames can never leak into a new date range.
export default function MapTimeline(props: Props) {
  return <TimelineWindow key={`${props.date}-${props.durationDays}`} {...props} />;
}

function TimelineWindow({ durationDays, ...props }: Props) {
  const [series, setSeries] = useState<PositionSeries | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(6);
  const sunThreshold = props.filters.sunElevation?.enabled ? Number(props.filters.sunElevation.value) : null;
  const earthThreshold = props.filters.earthElevation?.enabled ? Number(props.filters.earthElevation.value) : null;
  const enabled = sunThreshold !== null || earthThreshold !== null;

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const base = import.meta.env.VITE_API_URL ?? "";
        const response = await fetch(`${base}/api/position-timeline?date=${encodeURIComponent(props.date)}&durationDays=${durationDays}`, { signal: controller.signal });
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(typeof body?.detail === "string" ? body.detail : "Timeline unavailable. Check the date, duration and scientific API.");
        }
        const data: PositionSeries = await response.json();
        if (!data.times?.length || data.sun?.length !== data.times.length || data.earth?.length !== data.times.length) throw new Error("Incomplete ephemeris response.");
        if (!controller.signal.aborted) setSeries(data);
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Timeline unavailable.");
      }
    }
    void load();
    return () => controller.abort();
  }, [props.date, durationDays, attempt]);

  const last = (series?.times.length ?? 1) - 1;
  useEffect(() => {
    if (!playing || !series || index >= last) return;
    const timer = window.setInterval(() => setIndex(previous => Math.min(previous + 1, last)), 1000 / speed);
    return () => window.clearInterval(timer);
  }, [playing, series, last, speed, index]);
  const positions = useMemo(() => series ? { sun: series.sun[index], earth: series.earth[index], utc: series.times[index] } : null, [series, index]);
  const sites = useMemo(() => {
    const named = LANDING_SITES.filter(isOnPolarMap);
    const selected = props.selectedSite;
    return selected?.latitude != null && selected.longitude != null && !named.some(site => site.id === selected.id)
      ? [...named, { id: selected.id, name: selected.name, latitude: selected.latitude, longitude: selected.longitude }]
      : named;
  }, [props.selectedSite]);
  const rows = useMemo(() => sites.map(site => {
    const sun = series?.sun.map(vector => elevation(vector, site.latitude, site.longitude)) ?? [];
    const earth = series?.earth.map(vector => elevation(vector, site.latitude, site.longitude)) ?? [];
    const passes = sun.map((angle, i) => (sunThreshold === null || angle > sunThreshold) && (earthThreshold === null || earth[i] > earthThreshold));
    const runs: { start: number; end: number; pass: boolean }[] = [];
    passes.forEach((pass, i) => {
      if (runs.length && runs[runs.length - 1].pass === pass) runs[runs.length - 1].end = i + 1;
      else runs.push({ start: i, end: i + 1, pass });
    });
    return { site, sun, earth, passes, runs };
  }), [sites, series, sunThreshold, earthThreshold]);

  function seek(next: number) { setPlaying(false); setIndex(next); }
  return <>
    <div className="explorer-map-area"><MapPanel {...props} positions={positions} positionStatus={error || (!series ? "Loading ephemeris…" : "")} /></div>
    <div className="explorer-timeline map-timeline">
      <div className="explorer-timeline-heading"><strong>Landing sites · time explorer</strong><span>SPICE · 1-hour samples · UTC</span></div>
      {error ? <p role="alert">{error} <button type="button" onClick={() => { setError(""); setAttempt(value => value + 1); }}>Retry</button></p> : !series ? <p role="status">Loading Sun and Earth positions…</p> : <>
        <div className="map-time-controls">
          <button type="button" onClick={() => { if (index === last) setIndex(0); setPlaying(!playing || index === last); }}>{playing && index < last ? "Pause" : "Play"}</button>
          <button type="button" aria-label="Previous hour" disabled={index === 0} onClick={() => seek(index - 1)}>−1 h</button>
          <button type="button" aria-label="Next hour" disabled={index === last} onClick={() => seek(index + 1)}>+1 h</button>
          <label>Speed <select value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={1}>1 h / s</option><option value={6}>6 h / s</option><option value={12}>12 h / s</option></select></label>
          <strong>{utc(series.times[index])}</strong>
        </div>
        <label className="mission-scrubber">Observation time
          <input type="range" min={0} max={last} step={1} value={index} onChange={event => seek(Number(event.target.value))} aria-valuetext={utc(series.times[index])} />
        </label>
        <div className="explorer-timeline-labels"><span>{utc(series.times[0])}</span><span>{utc(series.times[last])}</span></div>
        <details className="map-timeline-details">
          <summary>Landing site visibility & details</summary>
        <p>{enabled ? "Green: all enabled elevation thresholds met · Dark: at least one threshold fails" : "Enable Sun elevation or Earth elevation to highlight matching areas and time windows."}</p>
        <div className="map-site-timelines">
          {rows.map(({ site, sun, earth, passes, runs }) => <div className="map-site-time-row" key={site.id}>
            <button type="button" className={props.selectedSite?.id === site.id ? "selected" : ""} onClick={() => props.onSiteSelect({ ...site, details: LANDING_SITES.find(item => item.id === site.id) })}>{site.name}</button>
            <div className="mission-visibility-bar" aria-label={`${site.name} elevation windows`}>
              {runs.map(run => <button type="button" key={run.start} className={`mission-segment ${enabled && run.pass ? "matching" : "unavailable"}`} style={{ width: `${100 * (run.end - run.start) / series.times.length}%` }} title={`${utc(series.times[run.start])}: ${!enabled ? "No elevation filter" : run.pass ? "Matches" : "Outside thresholds"}`} onClick={() => seek(run.start)} aria-label={`Inspect ${site.name} at ${utc(series.times[run.start])}`} />)}
              <span className="mission-time-cursor" style={{ left: `${100 * (index + .5) / series.times.length}%` }} />
            </div>
            <span className={enabled && passes[index] ? "site-time-match" : ""}>{enabled ? passes[index] ? "✓ Match" : "Outside" : "No filter"} · Sun {sun[index].toFixed(1)}° · Earth {earth[index].toFixed(1)}°</span>
          </div>)}
        </div>
        <small>Animated ephemeris preview, not live telemetry. Elevation filters only; terrain shadows excluded. Window follows mission start and duration.</small>
        </details>
      </>}
    </div>
  </>;
}
