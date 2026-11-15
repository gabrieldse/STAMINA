import { useEffect, useRef, useState } from "react";
import { apiErrorMessage } from "../../services/apiError";

import type {
  FilterStates,
  LunarSite,
  SiteTemperatures,
} from "../../types/explorer";

import type {
  TemperatureConfig,
  TemperatureSelectionStats,
} from "../../types/temperature";

import { LANDING_SITES, isOnPolarMap } from "../../types/sites";

import type { BodyPositions } from "./MapTimeline";

import SiteInfoCard from "./SiteInfoCard";
import SiteList from "./SiteList";
import type { LandingSite } from "../../types/sites";

// Named sites inside the 80°S map, drawn as markers on it.
const MAP_SITES = LANDING_SITES.filter(isOnPolarMap).map(
  ({ id, name, color, latitude, longitude, region }) => ({ id, name, color, latitude, longitude, region })
);

type Props = {
  date: string;
  positions: BodyPositions | null;
  positionStatus: string;
  onVisibilityReady?: (ready: boolean) => void;
  playing?: boolean;
  selectedSite: LunarSite | null;
  filters: FilterStates;
  onSiteSelect: (site: LunarSite) => void;
  onLandingSiteSelect: (site: LandingSite) => void;
  temperature: TemperatureConfig;
  onTemperatureSelection: (stats: TemperatureSelectionStats | null) => void;
};

// Messages posted by the lunar map viewer (public/lunar-map).
type ViewerMessage =
  | { type: "stamina:viewer-ready" }
  | {
      type: "stamina:site-selected";
      latitude: number;
      longitude: number;
      temperatures: SiteTemperatures;
      elevationM: number | null;
      // Set when a named site marker was clicked or focused.
      siteId?: string;
    }
  | {
      type: "stamina:selection-stats";
      stats: TemperatureSelectionStats | null;
    };

function isViewerMessage(data: unknown): data is ViewerMessage {
  const type = (data as { type?: unknown } | null)?.type;
  return typeof type === "string" && type.startsWith("stamina:");
}

function formatCoordinates(latitude: number, longitude: number) {
  const lat = `${Math.abs(latitude).toFixed(3)}°${latitude < 0 ? "S" : "N"}`;
  const lon = `${Math.abs(longitude).toFixed(2)}°${longitude < 0 ? "W" : "E"}`;
  return `${lat}, ${lon}`;
}

export default function MapPanel({
  positions,
  positionStatus,
  onVisibilityReady,
  playing = false,
  selectedSite,
  filters,
  onSiteSelect,
  onLandingSiteSelect,
  temperature,
  onTemperatureSelection,
}: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [viewerReady, setViewerReady] = useState(false);
  const [visibilityStatus, setVisibilityStatus] = useState("");
  const sunVisible = Boolean(filters.sunVisibility?.enabled);
  const earthVisible = Boolean(filters.earthVisibility?.enabled);
  const terrainEnabled = Boolean(filters.terrain?.enabled && filters.terrain.value);
  useEffect(() => {
    if (viewerReady) postToViewer({ type: "stamina:terrain-overlay", enabled: terrainEnabled });
  }, [viewerReady, terrainEnabled]);
  useEffect(() => {
    if (!viewerReady) return;
    if (!sunVisible && !earthVisible) {
      onVisibilityReady?.(true);
      postToViewer({ type: "stamina:visibility-mask", config: null });
      setVisibilityStatus("");
      return;
    }
    const controller = new AbortController();
    onVisibilityReady?.(false);
    postToViewer({ type: "stamina:visibility-mask", config: { pending: true } });
    setVisibilityStatus("Calculating visible areas from LOLA terrain...");
    const timer = window.setTimeout(async () => {
      if (!positions) return;
      try {
        // Show a quick result, then refine without blanking the preview.
        for (const size of playing ? [768] : [384, 1536]) {
          if (controller.signal.aborted) return;
          const response = await fetch(`${import.meta.env.VITE_API_URL ?? ""}/api/visibility-map`, {
            method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
            body: JSON.stringify({ sun: sunVisible ? positions.sun : null, earth: earthVisible ? positions.earth : null, size, encoding: "bitset" }),
          });
          const data = await response.json();
          if (!response.ok) throw new Error(apiErrorMessage(data, response.status));
          if (!Number.isInteger(data.size) || data.size < 32 || data.size > size || data.encoding !== "bitset-msb" ||
            typeof data.visiblePacked !== "string" || atob(data.visiblePacked).length !== Math.ceil(data.size*data.size/8)) throw new Error("Incomplete visibility map.");
          if (controller.signal.aborted) return;
          postToViewer({ type: "stamina:visibility-mask", config: data });
          setVisibilityStatus(`${sunVisible && earthVisible ? "Sun AND Earth" : sunVisible ? "Sun" : "Earth"} visible areas only | LOLA terrain | ${Math.round(data.resolutionM)} m / cell${!playing && size === 384 ? " | Refining..." : ""}`);
        }
        onVisibilityReady?.(true);
      } catch (cause) {
        if (!controller.signal.aborted) setVisibilityStatus(cause instanceof Error ? cause.message : "Visibility map unavailable.");
      }
    }, 150);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [viewerReady, positions, sunVisible, earthVisible, onVisibilityReady, playing]);
  const elevationStatus = [positions?.utc.replace("T", " ").replace("Z", " UTC"), visibilityStatus, positionStatus].filter(Boolean).join(" | ");
  // Site whose info card the user closed; it reopens for the next site.
  const [closedInfoId, setClosedInfoId] = useState<string | null>(null);
  const infoSite = selectedSite?.details;

  // Messages from the map: readiness, clicked sites and selection area.
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin || event.source !== frameRef.current?.contentWindow) return;
      if (!isViewerMessage(event.data)) return;

      const message = event.data;

      if (message.type === "stamina:viewer-ready") {
        setViewerReady(true);
      }

      if (
        message.type === "stamina:site-selected" &&
        Number.isFinite(message.latitude) &&
        Number.isFinite(message.longitude)
      ) {
        const { latitude, longitude, temperatures, elevationM, siteId } = message;
        const named = LANDING_SITES.find((site) => site.id === siteId);

        onSiteSelect(
          named
            ? {
                id: named.id,
                name: named.name,
                latitude: named.latitude,
                longitude: named.longitude,
                details: named,
                temperatures,
                elevationM,
              }
            : {
                id: `map-${latitude.toFixed(4)}-${longitude.toFixed(4)}`,
                name: `Map point ${formatCoordinates(latitude, longitude)}`,
                latitude,
                longitude,
                temperatures,
                elevationM,
              }
        );
      }

      if (message.type === "stamina:selection-stats") {
        onTemperatureSelection(message.stats);
      }
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [onSiteSelect, onTemperatureSelection]);

  function postToViewer(message: object) {
    frameRef.current?.contentWindow?.postMessage(
      message,
      window.location.origin
    );
  }

  // Draw the named landing sites once the map is ready.
  useEffect(() => {
    if (viewerReady) postToViewer({ type: "stamina:sites", sites: MAP_SITES });
  }, [viewerReady]);

  // The Temperature filter drives the layer and selection on the map.
  useEffect(() => {
    if (viewerReady) postToViewer({ type: "stamina:temperature-config", config: temperature });
  }, [viewerReady, temperature]);

  // A site picked from the list: pin it on the map, which replies with its
  // temperatures. Sites outside the map just clear the pin.
  const focusId =
    selectedSite?.details && !selectedSite.temperatures
      ? selectedSite.details.id
      : null;
  const focusOnMap = selectedSite?.details ? isOnPolarMap(selectedSite.details) : false;

  useEffect(() => {
    if (!viewerReady || !focusId) return;
    postToViewer({ type: "stamina:focus-site", siteId: focusOnMap ? focusId : null });
  }, [viewerReady, focusId, focusOnMap]);

  const activeFilters = Object.entries(filters)
    .filter(([id, state]) => id !== "analysisMode" && state.enabled)
    .map(([id]) => id);

  return (
    <section className="explorer-map">
      <div className="map-header">
        <strong>Lunar South Pole</strong>
        <span>
          {temperature.enabled
            ? "Diviner surface temperature"
            : "LOLA relief"}
          {" · 80°S to the pole"}
        </span>
      </div>

      <div className="map-workspace map-workspace-embed">
        <iframe
          ref={frameRef}
          className="lunar-map-frame"
          src="/lunar-map/index.html?embed=1"
          title="South pole surface temperature map"
        />

        <SiteList
          selectedId={infoSite?.id ?? null}
          onSelect={onLandingSiteSelect}
        />

        {infoSite && closedInfoId !== infoSite.id && (
          <SiteInfoCard
            site={infoSite}
            onClose={() => setClosedInfoId(infoSite.id)}
          />
        )}
      </div>

      <div className="map-footer">
        {terrainEnabled && <span>LOLA contours: 500 m intervals · Bold: 1,000 m · Heights relative to the lunar reference sphere</span>}
        {elevationStatus && <span role="status">{elevationStatus}</span>}
        <span>
          Selected: {selectedSite?.name ?? "None (click the map)"}
        </span>

        <span>
          {activeFilters.length} active filters
        </span>
      </div>
    </section>
  );
}
