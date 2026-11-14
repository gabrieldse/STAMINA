
import type { LandingSite, MissionConfig } from "./MissionTypes";

type Props = {
  mission: MissionConfig;
  site: LandingSite;
  delayDays: number;
  onBack: () => void;
  onContinue: () => void;
};

function addDays(dateString: string, days: number) {
  const date = new Date(`${dateString}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export default function MissionReassessment({
  mission,
  site,
  delayDays,
  onBack,
  onContinue,
}: Props) {
  const revisedDate = addDays(mission.date, delayDays);

  return (
    <main className="mission evaluation-page">
      <p className="eyebrow">STAMINA / STEP 5 OF 6</p>

      <h1>Mission Reassessment</h1>

      <p>
        Your landing date has shifted by {delayDays} days.
        STAMINA must now evaluate whether the original
        landing site remains suitable.
      </p>

      <div className="comparison-grid">
        <div className="comparison-card">
          <h2>Original mission</h2>

          <p>Landing site: <strong>{site.name}</strong></p>
          <p>Landing date: <strong>{mission.date}</strong></p>

          <div className="comparison-metric">
            <span>Sunlight availability</span>
            <strong>—</strong>
          </div>

          <div className="comparison-metric">
            <span>Earth visibility</span>
            <strong>—</strong>
          </div>

          <small>Scientific data pending</small>
        </div>

        <div className="comparison-card">
          <h2>Delayed mission</h2>

          <p>Landing site: <strong>{site.name}</strong></p>
          <p>Landing date: <strong>{revisedDate}</strong></p>

          <div className="comparison-metric">
            <span>Sunlight availability</span>
            <strong>—</strong>
          </div>

          <div className="comparison-metric">
            <span>Earth visibility</span>
            <strong>—</strong>
          </div>

          <small>Scientific data pending</small>
        </div>
      </div>

      <div className="science-note">
        <strong>Mission planning decision</strong>
        <p>
          Without calculated illumination and communication
          windows, it is not yet possible to determine
          whether your original site remains suitable.
        </p>
        <p>
          You may investigate alternative locations,
          but a new site should only be recommended
          after scientific evaluation.
        </p>
      </div>

      <div className="navigation">
        <button className="secondary-button" onClick={onBack}>
          ← Change delay
        </button>

        <button onClick={onContinue}>
          Explore alternatives →
        </button>
      </div>
    </main>
  );
}
