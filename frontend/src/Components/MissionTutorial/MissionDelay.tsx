
import { useState } from "react";
import type { LandingSite, MissionConfig } from "./MissionTypes";
import "./MissionDelay.css";

type Props = {
  mission: MissionConfig;
  site: LandingSite;
  onBack: () => void;
  onContinue: (delayDays: number) => void;
};

function addDays(dateString: string, days: number): string {
  const date = new Date(`${dateString}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function formatDate(dateString: string): string {
  return new Date(`${dateString}T12:00:00Z`).toLocaleDateString(
    "en-GB",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }
  );
}

export default function MissionDelay({
  mission,
  site,
  onBack,
  onContinue,
}: Props) {
  const [delay, setDelay] = useState(12);
  const [briefingOpen, setBriefingOpen] = useState(false);

  const revisedDate = addDays(mission.date, delay);

  return (
    <main className="mission delay-page">
      <div className="delay-topbar">
        <div>
          <span className="delay-brand">STAMINA</span>
          <span className="delay-divider"> / </span>
          <span>MISSION CONTROL</span>
        </div>

        <span className="delay-status">
          ● CRITICAL UPDATE
        </span>
      </div>

      <p className="eyebrow">MISSION ECLIPSE / ACT IV</p>

      <h1>Unexpected Schedule Change</h1>

      <p className="delay-intro">
        Your mission was ready for its scheduled landing.
        But an unexpected event has changed the plan.
      </p>

      <section className="delay-alert" role="alert">
        <div className="delay-alert-heading">
          <span className="delay-warning-icon">⚠</span>

          <div>
            <span className="delay-alert-label">
              INCOMING TRANSMISSION
            </span>
            <h2>Launch schedule disrupted</h2>
          </div>
        </div>

        <p>
          Mission Control has detected an integration
          anomaly involving the launch vehicle.
          The mission must be postponed.
        </p>

        <p>
          Your original Sun and Earth visibility
          assessment may no longer represent the
          revised mission period.
        </p>

        <span className="delay-fiction">
          Fictional mission event
        </span>
      </section>

      <div className="delay-mission-id">
        <div>
          <span>ACTIVE MISSION</span>
          <strong>{mission.name}</strong>
        </div>

        <div>
          <span>SELECTED SITE</span>
          <strong>{site.name}</strong>
        </div>
      </div>

      <h2 className="delay-section-title">
        Updated landing schedule
      </h2>

      <div className="delay-date-grid">
        <div className="delay-date-card">
          <span>ORIGINAL LANDING</span>
          <strong>{formatDate(mission.date)}</strong>
          <small>Previously planned</small>
        </div>

        <div className="delay-date-card revised">
          <span>REVISED LANDING</span>
          <strong>{formatDate(revisedDate)}</strong>
          <small>After schedule adjustment</small>
        </div>
      </div>

      <div className="delay-control">
        <div className="delay-control-header">
          <label htmlFor="mission-delay-slider">
            Launch delay
          </label>

          <strong>+{delay} days</strong>
        </div>

        <input
          id="mission-delay-slider"
          type="range"
          min={0}
          max={30}
          step={1}
          value={delay}
          onChange={(e) =>
            setDelay(Number(e.target.value))
          }
        />

        <div className="delay-slider-labels">
          <span>No delay</span>
          <span>30 days</span>
        </div>
      </div>

      <section className="delay-analysis">
        <div className="delay-analysis-header">
          <span className="delay-analysis-icon">◉</span>
          <h2>Why does this matter?</h2>
        </div>

        <p>
          At the lunar south pole, the Sun remains close
          to the local horizon. Even small changes in
          time can modify illumination windows because
          nearby crater rims may obstruct sunlight.
        </p>

        <p>
          Earth visibility also evolves. The lander
          could experience different direct-to-Earth
          communication windows after the delay.
        </p>
      </section>

      <button
        type="button"
        className="delay-briefing-toggle"
        onClick={() => setBriefingOpen(!briefingOpen)}
        aria-expanded={briefingOpen}
      >
        {briefingOpen
          ? "− Hide engineering briefing"
          : "+ Read engineering briefing"}
      </button>

      {briefingOpen && (
        <div className="delay-briefing">
          <p>
            STAMINA must compare the new mission interval
            with the original one, using:
          </p>

          <ul>
            <li>Solar elevation and terrain obstruction</li>
            <li>Earth elevation and communication windows</li>
            <li>Longest continuous darkness period</li>
            <li>Longest communication blackout</li>
          </ul>

          <p>
            A delay does not automatically make the
            initial landing site unsuitable.
          </p>
        </div>
      )}

      <div className="delay-director-message">
        <span>MESSAGE TO FLIGHT DIRECTOR</span>

        <p>
          "The launch window has shifted.
          Before we authorize the revised mission,
          we need a new environmental assessment."
        </p>
      </div>

      <div className="delay-actions">
        <button
          type="button"
          className="delay-back"
          onClick={onBack}
        >
          ← Back to assessment
        </button>

        <button
          type="button"
          className="delay-primary"
          onClick={() => onContinue(delay)}
        >
          Reassess with STAMINA →
        </button>
      </div>
    </main>
  );
}
