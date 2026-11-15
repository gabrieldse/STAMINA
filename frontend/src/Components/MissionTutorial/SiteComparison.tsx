
import { useState } from "react";

import {
  LANDING_SITES,
  type LandingSite,
  type MissionConfig,
} from "./MissionTypes";

type Props = {
  mission: MissionConfig;
  originalSite: LandingSite;
  delayDays: number;
  onBack: () => void;
  onContinue: (site: LandingSite) => void;
};

export default function SiteComparison({
  mission,
  originalSite,
  delayDays,
  onBack,
  onContinue,
}: Props) {
  const [selectedId, setSelectedId] = useState(originalSite.id);

  const selectedSite = LANDING_SITES.find(
    (site) => site.id === selectedId
  );

  return (
    <main className="mission evaluation-page">
      <p className="eyebrow">STAMINA / FINAL DECISION</p>

      <h1>Compare Landing Sites</h1>

      <p>
        Your mission has been delayed by {delayDays} days.
        Select the landing site you want to use for the
        revised mission.
      </p>

      <div className="science-note">
        <strong>Mission requirements</strong>
        <p>
          Minimum sunlight: {mission.sunlight}% ·
          Minimum Earth visibility: {mission.earth}%
        </p>
        <p>
          Scientific visibility results are not yet available.
          Your selection is provisional.
        </p>
      </div>

      <div className="site-list">
        {LANDING_SITES.map((site) => (
          <button
            type="button"
            key={site.id}
            className={
              selectedId === site.id
                ? "site-card selected"
                : "site-card"
            }
            onClick={() => setSelectedId(site.id)}
          >
            <strong>
              {site.name}
              {site.id === originalSite.id
                ? " · Original site"
                : ""}
            </strong>

            <span>{site.description}</span>

            <span>
              Sunlight: Not computed ·
              Earth visibility: Not computed
            </span>
          </button>
        ))}
      </div>

      <div className="navigation">
        <button className="secondary-button" onClick={onBack}>
          ← Back
        </button>

        <button
          disabled={!selectedSite}
          onClick={() => {
            if (selectedSite) onContinue(selectedSite);
          }}
        >
          Confirm provisional selection →
        </button>
      </div>
    </main>
  );
}
