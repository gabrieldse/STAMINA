import { useEffect } from "react";

import type {
  FilterStates,
  LunarSite,
  SiteTemperatures,
} from "../../types/explorer";

type Props = {
  selectedSite: LunarSite | null;
  filters: FilterStates;
  onSiteSelect: (site: LunarSite) => void;
};

// Message posted by the lunar map viewer (public/lunar-map) when a point is clicked.
type SiteSelectedMessage = {
  type: "stamina:site-selected";
  latitude: number;
  longitude: number;
  temperatures: SiteTemperatures;
};

function isSiteSelectedMessage(data: unknown): data is SiteSelectedMessage {
  const message = data as SiteSelectedMessage | null;
  return (
    message?.type === "stamina:site-selected" &&
    Number.isFinite(message.latitude) &&
    Number.isFinite(message.longitude)
  );
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
}: Props) {
  // Clicking the map selects that point as the landing site.
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      if (!isSiteSelectedMessage(event.data)) return;

      const { latitude, longitude, temperatures } = event.data;
      onSiteSelect({
        id: `map-${latitude.toFixed(4)}-${longitude.toFixed(4)}`,
        name: `Map point ${formatCoordinates(latitude, longitude)}`,
        latitude,
        longitude,
        temperatures,
      });
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [onSiteSelect]);

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
          className="lunar-map-frame"
          src="/lunar-map/index.html?embed=1"
          title="Lunar south pole surface temperature map"
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
