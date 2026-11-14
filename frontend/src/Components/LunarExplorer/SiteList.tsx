
import { LANDING_SITES, isOnPolarMap } from "../../types/sites";
import type { LandingSite } from "../../types/sites";

import "./SiteList.css";

type Props = {
  selectedId: string | null;
  onSelect: (site: LandingSite) => void;
};

const GROUPS = [
  {
    title: "Artemis III candidates",
    note: "On the south polar map",
    sites: LANDING_SITES.filter(isOnPolarMap),
  },
  {
    title: "Apollo",
    note: "Near the equator, outside the polar map",
    sites: LANDING_SITES.filter((site) => !isOnPolarMap(site)),
  },
];

export default function SiteList({ selectedId, onSelect }: Props) {
  return (
    <div className="explorer-inspector-section site-list">
      <h3>Landing Sites</h3>

      {GROUPS.map((group) => (
        <div className="site-list-group" key={group.title}>
          <div className="site-list-heading">
            <span>{group.title}</span>
            <small>{group.note}</small>
          </div>

          <div className="site-list-items">
            {group.sites.map((site) => (
              <button
                key={site.id}
                type="button"
                className={
                  "site-list-item" +
                  (site.id === selectedId ? " active" : "")
                }
                aria-pressed={site.id === selectedId}
                onClick={() => onSelect(site)}
              >
                <i style={{ background: site.color, color: site.color }} />
                <span>{site.name}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
