import { useEffect, useRef, useState } from "react";

import type {
  FilterStates,
  LunarSite,
  SiteTemperatures,
} from "../../types/explorer";

import type {
  TemperatureConfig,
  TemperatureSelectionStats,
} from "../../types/temperature";

type Props = {
  selectedSite: LunarSite | null;
  filters: FilterStates;
  onSiteSelect: (site: LunarSite) => void;
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
  selectedSite,
  filters,
  onSiteSelect,
  temperature,
  onTemperatureSelection,
}: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [viewerReady, setViewerReady] = useState(false);

  // Messages from the map: readiness, clicked sites and selection area.
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
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
        const { latitude, longitude, temperatures } = message;

        onSiteSelect({
          id: `map-${latitude.toFixed(4)}-${longitude.toFixed(4)}`,
          name: `Map point ${formatCoordinates(latitude, longitude)}`,
          latitude,
          longitude,
          temperatures,
        });
      }

      if (message.type === "stamina:selection-stats") {
        onTemperatureSelection(message.stats);
      }
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [onSiteSelect, onTemperatureSelection]);

  // The Temperature filter drives the layer and selection on the map.
  useEffect(() => {
    if (!viewerReady) return;

    frameRef.current?.contentWindow?.postMessage(
      { type: "stamina:temperature-config", config: temperature },
      window.location.origin
    );
  }, [viewerReady, temperature]);

  const activeFilters = Object.entries(filters)
    .filter(([, state]) => state.enabled)
    .map(([id]) => id);

  return (
    <section className="explorer-map">
      <div className="map-header">
        <strong>Lunar South Pole</strong>
        <span>Diviner surface temperature · 80°S to the pole</span>
      </div>

      <div className="map-workspace map-workspace-embed">
        <iframe
          ref={frameRef}
          className="lunar-map-frame"
          src="/lunar-map/index.html?embed=1"
          title="South pole surface temperature map"
        />
      </div>

      <div className="map-footer">
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
