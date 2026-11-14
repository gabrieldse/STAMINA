
import type { LandingSite, MissionConfig } from "./MissionTypes";

type Props = {
  mission: MissionConfig;
  site: LandingSite;
  onBack: () => void;
  onContinue: () => void;
};

export default function MissionEvaluation({
  mission,
  site,
  onBack,
  onContinue,
}: Props) {
  const landingDate = new Date(`${mission.date}T12:00:00Z`);

  const endDate = new Date(landingDate);
  endDate.setUTCDate(endDate.getUTCDate() + mission.duration);

  const formatDate = (date: Date) =>
    date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });

  return (
    <main className="mission evaluation-page">
      <p className="eyebrow">STAMINA / STEP 3 OF 6</p>
      <h1>Mission Evaluation</h1>

      <p>
        Evaluate environmental conditions before committing
        to a lunar landing site.
      </p>

      <div className="evaluation-summary">
        <div className="summary-item">
          <span>Mission</span>
          <strong>{mission.name}</strong>
        </div>

        <div className="summary-item">
          <span>Landing site</span>
          <strong>{site.name}</strong>
        </div>

        <div className="summary-item">
          <span>Landing date</span>
          <strong>{formatDate(landingDate)}</strong>
        </div>

        <div className="summary-item">
          <span>End of mission</span>
          <strong>{formatDate(endDate)}</strong>
        </div>
      </div>

      <h2>Environmental assessment</h2>

      <div className="evaluation-metrics">
        <div className="metric-card">
          <span>☀️ Solar illumination</span>
          <strong>—</strong>
          <small>Required: {mission.sunlight}%</small>
          <p>Awaiting scientific data</p>
        </div>

        <div className="metric-card">
          <span>🌍 Earth visibility</span>
          <strong>—</strong>
          <small>Required: {mission.earth}%</small>
          <p>Awaiting scientific data</p>
        </div>
      </div>

      <h2>Visibility over time</h2>

      <div className="timeline-panel">
        <p>
          This timeline will display sunlight and direct-to-Earth
          visibility throughout the mission.
        </p>

        <div className="timeline-label">
          <span>Solar illumination</span>
          <span>Data pending</span>
        </div>

        <div className="timeline-empty" />

        <div className="timeline-label">
          <span>Earth visibility</span>
          <span>Data pending</span>
        </div>

        <div className="timeline-empty" />

        <div className="timeline-dates">
          <span>{formatDate(landingDate)}</span>
          <span>{formatDate(endDate)}</span>
        </div>
      </div>

      <div className="science-note">
        <strong>Scientific note</strong>
        <p>
          Visibility depends on the positions of the Sun and Earth
          relative to the local lunar terrain horizon.
          This interface does not yet contain computed results.
        </p>
      </div>

      <div className="navigation">
        <button className="secondary-button" onClick={onBack}>
          ← Change site
        </button>

        <button onClick={onContinue}>
          Continue scenario →
        </button>
      </div>
    </main>
  );
}
