
import type { LandingSite, MissionConfig } from "./MissionTypes";

type Props = {
  mission: MissionConfig;
  originalSite: LandingSite;
  finalSite: LandingSite;
  delayDays: number;
  onBack: () => void;
  onRestart: () => void;
};

function addDays(dateString: string, days: number) {
  const date = new Date(`${dateString}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export default function MissionReport({
  mission,
  originalSite,
  finalSite,
  delayDays,
  onBack,
  onRestart,
}: Props) {
  const revisedDate = addDays(mission.date, delayDays);
  const changedSite = originalSite.id !== finalSite.id;

  const report = [
    "STAMINA — MISSION DECISION REPORT",
    "",
    `Mission: ${mission.name}`,
    `Original landing date: ${mission.date}`,
    `Revised landing date: ${revisedDate}`,
    `Launch delay: ${delayDays} days`,
    `Duration: ${mission.duration} Earth days`,
    "",
    `Original site: ${originalSite.name}`,
    `Selected site: ${finalSite.name}`,
    `Site changed: ${changedSite ? "Yes" : "No"}`,
    "",
    `Required sunlight: ${mission.sunlight}%`,
    `Required Earth visibility: ${mission.earth}%`,
    "",
    "Scientific assessment: NOT COMPUTED",
    "Mission feasibility: NOT VERIFIED",
    "Decision status: PROVISIONAL",
  ].join("\n");

  return (
    <main className="mission evaluation-page">
      <p className="eyebrow">STAMINA / MISSION REPORT</p>

      <h1>Mission Decision Report</h1>

      <div className="science-note">
        <strong>Provisional decision recorded</strong>
        <p>
          You have completed the guided mission scenario.
          Your choice requires scientific validation.
        </p>
      </div>

      <div className="evaluation-summary">
        <div className="summary-item">
          <span>Mission</span>
          <strong>{mission.name}</strong>
        </div>

        <div className="summary-item">
          <span>Final selected site</span>
          <strong>{finalSite.name}</strong>
        </div>

        <div className="summary-item">
          <span>Revised landing date</span>
          <strong>{revisedDate}</strong>
        </div>

        <div className="summary-item">
          <span>Mission duration</span>
          <strong>{mission.duration} days</strong>
        </div>
      </div>

      <h2>Your decision</h2>

      <div className="decision-panel">
        <h3>
          {changedSite
            ? "Alternative landing site selected"
            : "Original landing site retained"}
        </h3>

        <p>
          {changedSite
            ? `You changed the landing site from ${originalSite.name} to ${finalSite.name}.`
            : `You decided to keep ${originalSite.name} after the schedule change.`}
        </p>
      </div>

      <h2>Engineering verification</h2>

      <div className="comparison-grid">
        <div className="comparison-card">
          <h3>Solar illumination</h3>
          <p>Required: {mission.sunlight}%</p>
          <strong>Not computed</strong>
        </div>

        <div className="comparison-card">
          <h3>Earth visibility</h3>
          <p>Required: {mission.earth}%</p>
          <strong>Not computed</strong>
        </div>
      </div>

      <p>
        The selection is not a verified landing recommendation.
        Real ephemeris, terrain, power and communication
        assessments are needed before determining feasibility.
      </p>

      <button
        onClick={() => {
          const blob = new Blob([report], {
            type: "text/plain;charset=utf-8",
          });

          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");

          link.href = url;
          link.download = "STAMINA_Mission_Report.txt";
          link.click();

          URL.revokeObjectURL(url);
        }}
      >
        Download mission report
      </button>

      <div className="navigation">
        <button className="secondary-button" onClick={onBack}>
          ← Change decision
        </button>

        <button onClick={onRestart}>
          Start new mission →
        </button>
      </div>
    </main>
  );
}
