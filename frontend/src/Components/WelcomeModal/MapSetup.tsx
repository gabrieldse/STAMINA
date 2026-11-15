import { useState } from "react";
import type { InitialMapSite } from "../../types/sites";
import "./WelcomeModal.css";
import "./MapSetup.css";

export default function MapSetup({ onChoose, onCancel }: { onChoose: (site: InitialMapSite | null) => void; onCancel?: () => void }) {
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  return <div className="welcome-overlay">
    <section className="welcome-modal" role="dialog" aria-modal="true" aria-labelledby="map-setup-title">
      <p className="welcome-eyebrow">STAMINA · LUNAR EXPLORER</p>
      <h2 id="map-setup-title">Choose the center of your circular map</h2>
      <p className="welcome-description">Enter a site anywhere on the Moon, or start with the default south-pole map.</p>
      <div className="welcome-options">
        <form className="welcome-option featured map-setup-form" noValidate onSubmit={event => {
          event.preventDefault();
          const latitude = Number(lat), longitude = Number(lon);
          if (!lat.trim() || !lon.trim()) return setError("Enter both latitude and longitude.");
          if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) return setError("Latitude must be between -90 and 90.");
          if (!Number.isFinite(longitude) || longitude < -180 || longitude > 360) return setError("Longitude must be between -180 and 360.");
          onChoose({ latitude, longitude: longitude > 180 ? longitude-360 : longitude, name: name.trim() || "My site" });
        }}>
          <h3>Your coordinates</h3>
          <label>Latitude (°)<input autoFocus type="number" step="any" value={lat} onChange={e => setLat(e.target.value)} placeholder="e.g. 12.3" /></label>
          <label>Longitude (°)<input type="number" step="any" value={lon} onChange={e => setLon(e.target.value)} placeholder="e.g. 45.6" /></label>
          <label>Site name (optional)<input value={name} onChange={e => setName(e.target.value)} maxLength={60} /></label>
          <small>North and east are positive. The chosen point will be at the center of a circular 2D map.</small>
          {error && <p role="alert">{error}</p>}
          <button type="submit" className="welcome-primary">Create circular map</button>
        </form>
        <div className="welcome-option">
          <h3>Default south pole</h3>
          <p>Use the existing circular map centered on the lunar south pole, with LOLA relief and the polar scientific layers.</p>
          <button type="button" className="welcome-secondary" onClick={() => onChoose(null)}>Use default south pole</button>
        </div>
      </div>
      {onCancel && <button type="button" className="welcome-secondary map-setup-cancel" onClick={onCancel}>Cancel</button>}
    </section>
  </div>;
}
