
import { Fragment } from "react";

import { formatLatLon } from "../../types/sites";
import type { LandingSite } from "../../types/sites";

import "./SiteInfoCard.css";

type Props = {
  site: LandingSite;
  onClose: () => void;
};

// Floating info panel over the map, like the Website draft's mission info.
export default function SiteInfoCard({ site, onClose }: Props) {
  const facts: [string, string][] = [
    ["Coordinates", formatLatLon(site.latitude, site.longitude)],
    ["Terrain", site.terrain],
    ["Goal", site.goal],
    ...site.facts,
  ];

  return (
    <section className="site-info-card" aria-live="polite">
      <button
        type="button"
        className="site-info-close"
        onClick={onClose}
        aria-label="Close site information"
      >
        ×
      </button>

      <div className="site-info-title">
        <i style={{ background: site.color }} />
        <h2>{site.name}</h2>
      </div>

      <div className="site-info-sub">{site.site}</div>

      <dl className="site-info-facts">
        {facts.map(([label, value]) => (
          <Fragment key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </Fragment>
        ))}
      </dl>

      <div className="site-info-story">
        <h4>{site.program === "Apollo" ? "What happened" : "About"}</h4>
        <p>{site.story}</p>
      </div>
    </section>
  );
}
