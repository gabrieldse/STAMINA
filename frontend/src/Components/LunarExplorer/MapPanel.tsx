
import type {
  FilterStates,
  LunarSite,
} from "../../types/explorer";

type Props = {
  selectedSite: LunarSite | null;
  filters: FilterStates;
  onSiteSelect: (site: LunarSite) => void;
};

export default function MapPanel({
  selectedSite,
  filters,
  onSiteSelect,
}: Props) {
  // Temporary test sites, not georeferenced.
  const testSites: LunarSite[] = [
    { id: "alpha", name: "Site Alpha" },
    { id: "beta", name: "Site Beta" },
    { id: "gamma", name: "Site Gamma" },
  ];

  const activeFilters = Object.entries(filters)
    .filter(([, state]) => state.enabled)
    .map(([id]) => id);

  return (
    <section className="explorer-map">
      <div className="map-header">
        <strong>Lunar South Pole</strong>
        <span>Map integration pending</span>
      </div>

      <div className="map-workspace">
        <div className="map-empty-content">
          <span className="map-placeholder-icon">☾</span>

          <h2>Interactive Lunar Map</h2>

          <p>
            Gabriel's lunar map will be mounted here.
          </p>

          <small>
            The site buttons below are temporary
            integration controls, not map coordinates.
          </small>

          <div className="map-test-sites">
            {testSites.map((site) => (
              <button
                key={site.id}
                type="button"
                className={
                  selectedSite?.id === site.id
                    ? "active"
                    : ""
                }
                onClick={() => onSiteSelect(site)}
              >
                {site.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="map-footer">
        <span>
          Selected: {selectedSite?.name ?? "None"}
        </span>

        <span>
          {activeFilters.length} active filters
        </span>
      </div>
    </section>
  );
}
