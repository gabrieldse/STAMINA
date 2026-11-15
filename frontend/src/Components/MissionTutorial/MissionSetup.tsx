
import { useState } from "react";
import type { MissionConfig } from "./MissionTypes";

type Props = {
  onContinue: (config: MissionConfig) => void;
};

export default function MissionSetup({ onContinue }: Props) {
  const [name, setName] = useState("Operation Polar Light");
  const [date, setDate] = useState("2028-02-08");
  const [duration, setDuration] = useState(20);
  const [sunlight, setSunlight] = useState(65);
  const [earth, setEarth] = useState(50);

  function handleContinue() {
    onContinue({
      name,
      date,
      duration,
      sunlight,
      earth,
    });
  }

  return (
    <main className="mission">
      <p className="eyebrow">STAMINA / STEP 1 OF 6</p>
      <h1>Plan your lunar mission</h1>
      <p>Configure your expedition to the lunar south pole.</p>

      <label>Mission name</label>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
      />

      <label>Landing date</label>
      <input
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
      />

      <label>Mission duration (Earth days)</label>
      <input
        type="number"
        min={1}
        max={365}
        value={duration}
        onChange={(e) => setDuration(Number(e.target.value))}
      />

      <label>Minimum sunlight: {sunlight}%</label>
      <input
        type="range"
        min={0}
        max={100}
        value={sunlight}
        onChange={(e) => setSunlight(Number(e.target.value))}
      />

      <label>Minimum Earth visibility: {earth}%</label>
      <input
        type="range"
        min={0}
        max={100}
        value={earth}
        onChange={(e) => setEarth(Number(e.target.value))}
      />

      <button
        disabled={!name.trim() || !date || duration < 1}
        onClick={handleContinue}
      >
        Choose landing site →
      </button>
    </main>
  );
}
