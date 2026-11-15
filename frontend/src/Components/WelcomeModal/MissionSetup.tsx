import { useState } from "react";
import "./WelcomeModal.css";
import "./MapSetup.css";

type Mission = { date: string; durationDays: number };

export default function MissionSetup({ initial, onStart, onBack }: {
  initial: Mission; onStart: (mission: Mission) => void; onBack: () => void;
}) {
  const [date, setDate] = useState(initial.date);
  const [duration, setDuration] = useState(String(initial.durationDays));
  const [error, setError] = useState("");
  return <div className="welcome-overlay">
    <section className="welcome-modal" role="dialog" aria-modal="true" aria-labelledby="mission-setup-title">
      <img className="welcome-logo" src="/brand/stamina-logo.png" alt="STAMINA" />
      <p className="welcome-eyebrow">PLAN YOUR MISSION</p>
      <h2 id="mission-setup-title">Choose your mission window</h2>
      <p className="welcome-description">Set the departure date and mission duration to explore sunlight and Earth visibility on the default lunar south-pole map.</p>
      <form className="welcome-option featured map-setup-form" noValidate onSubmit={event => {
        event.preventDefault();
        const days = Number(duration);
        const start = new Date(`${date}T00:00:00Z`);
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(start.getTime()) || start.toISOString().slice(0,10) !== date) return setError("Enter a valid departure date.");
        if (!Number.isInteger(days) || days < 1 || days > 365) return setError("Choose a duration from 1 to 365 days.");
        const end = new Date(start.getTime() + days * 86400000);
        if (date < "1850-01-01" || end.toISOString().slice(0,10) > "2150-01-01") return setError("The entire mission must fall between 1 January 1850 and 1 January 2150.");
        onStart({ date, durationDays: days });
      }}>
        <label>Departure date (year, month, day)<input autoFocus type="date" min="1850-01-01" max="2150-01-01" required value={date} onChange={e => setDate(e.target.value)} /></label>
        <label>Mission duration (days)<input type="number" min="1" max="365" step="1" required value={duration} onChange={e => setDuration(e.target.value)} /></label>
        <small>Dates use UTC. You can adjust the mission window later in the explorer.</small>
        {error && <p role="alert">{error}</p>}
        <button type="submit" className="welcome-primary">Explore the south pole</button>
      </form>
      <button type="button" className="welcome-secondary map-setup-cancel" onClick={onBack}>Back</button>
    </section>
  </div>;
}
