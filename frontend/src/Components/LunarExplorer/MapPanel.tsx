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

import { LANDING_SITES, isOnPolarMap } from "../../types/sites";

import SiteInfoCard from "./SiteInfoCard";

// Named sites inside the 80°S map, drawn as markers on it.
const MAP_SITES = LANDING_SITES.filter(isOnPolarMap).map(
  ({ id, name, color, latitude, longitude }) => ({ id, name, color, latitude, longitude })
);

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
  selectedSite,
  filters,
  onSiteSelect,
  temperature,
  onTemperatureSelection,
}: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [viewerReady, setViewerReady] = useState(false);
  // Site whose info card the user closed; it reopens for the next site.
  const [closedInfoId, setClosedInfoId] = useState<string | null>(null);
  const infoSite = selectedSite?.details;

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
        const { latitude, longitude, temperatures, siteId } = message;
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
              }
            : {
                id: `map-${latitude.toFixed(4)}-${longitude.toFixed(4)}`,
                name: `Map point ${formatCoordinates(latitude, longitude)}`,
                latitude,
                longitude,
                temperatures,
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

        {infoSite && closedInfoId !== infoSite.id && (
          <SiteInfoCard
            site={infoSite}
            onClose={() => setClosedInfoId(infoSite.id)}
          />
        )}
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
