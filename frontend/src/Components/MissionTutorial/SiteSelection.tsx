
import { useState } from "react";
import {
  LANDING_SITES,
  type LandingSite,
  type MissionConfig,
} from "./MissionTypes";

type Props = {
  mission: MissionConfig;
  onBack: () => void;
  onContinue: (site: LandingSite) => void;
};

export default function SiteSelection({
  mission,
  onBack,
  onContinue,
}: Props) {
  const [selectedSite, setSelectedSite] = useState<string>("");

  return (
    <main className="mission">
      <p className="eyebrow">STAMINA / STEP 2 OF 6</p>

      <h1>Choose your landing site</h1>

      <p>
        Mission: <strong>{mission.name}</strong>
      </p>

      <p>
        Select a candidate location to begin your lunar
        environmental assessment.
      </p>

      <div className="site-list">
        {LANDING_SITES.map((site) => (
          <button
            type="button"
            key={site.id}
            className={
              selectedSite === site.id
                ? "site-card selected"
                : "site-card"
            }
            onClick={() => setSelectedSite(site.id)}
          >
            <strong>{site.name}</strong>
            <span>{site.description}</span>
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
            const site = LANDING_SITES.find(
              (item) => item.id === selectedSite
            );

            if (site) onContinue(site);
          }}
        >
          Analyze this site →
        </button>
      </div>
    </main>
  );
}
