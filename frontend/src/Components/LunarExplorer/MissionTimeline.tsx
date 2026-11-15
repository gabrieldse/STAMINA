import { useState } from "react";
import type { MissionTimelineData } from "../../types/explorer";

const utc = (value: number) => new Date(value).toISOString().slice(0, 16).replace("T", " ") + " UTC";

export default function MissionTimeline({ data, loading }: { data?: MissionTimelineData; loading: boolean }) {
  const [index, setIndex] = useState(0);
  if (!data) return <div className="explorer-timeline">
    <strong>Mission Timeline</strong>
    <p role="status">{loading ? "Calculating mission visibility…" : "Select a site and run analysis to see the mission timeline."}</p>
  </div>;
  const start = Date.parse(data.startUtc);
  const end = Date.parse(data.endUtc);
  const selected = Math.min(index, data.sampleCount - 1);
  const timeAt = (position: number) => start + (end - start) * position / data.sampleCount;
  const status = (kind: "sun" | "earth") => data[kind].find(s => selected >= s.start && selected < s.end)?.visible;
  return <div className="explorer-timeline">
    <div className="explorer-timeline-heading"><strong>Mission Timeline</strong><span>{data.instant ? "Single instant" : "10-minute resolution"}</span></div>
    {(["sun", "earth"] as const).map(kind => <div className="mission-visibility-row" key={kind}>
      <span>{kind === "sun" ? "Sun" : "Earth"}</span>
      <div className="mission-visibility-bar" role="group" aria-label={`${kind === "sun" ? "Sun" : "Earth"} visibility intervals`}>
        {data[kind].map(segment => <button type="button" key={segment.start}
          className={`mission-segment ${segment.visible ? kind : "unavailable"}`}
          style={{ width: `${100 * (segment.end - segment.start) / data.sampleCount}%` }}
          title={`${segment.visible ? "Visible" : "Not visible"}: ${utc(timeAt(segment.start))}${data.instant ? "" : ` – ${utc(timeAt(segment.end))}`}`}
          aria-label={`${kind}: ${segment.visible ? "visible" : "not visible"} from ${utc(timeAt(segment.start))}`}
          onClick={() => setIndex(segment.start)} />)}
        {!data.instant && <span className="mission-time-cursor" style={{ left: `${100 * (selected + .5) / data.sampleCount}%` }} />}
      </div>
    </div>)}
    {!data.instant && <label className="mission-scrubber">Inspect mission time
      <input type="range" min={0} max={data.sampleCount - 1} step={1} value={selected}
        onChange={event => setIndex(Number(event.target.value))} aria-valuetext={utc(timeAt(selected + .5))} />
    </label>}
    <div className="explorer-timeline-labels"><span>{utc(start)}</span>{!data.instant && <span>{utc(end)}</span>}</div>
    <p aria-live="polite">{utc(timeAt(data.instant ? 0 : selected + .5))} · Sun: {status("sun") ? "visible" : "not visible"} · Earth: {status("earth") ? "visible" : "not visible"}</p>
    <small>Gold: Sun visible · Blue: Earth visible · Dark: below the selected elevation threshold. Terrain shadows excluded.</small>
  </div>;
}
