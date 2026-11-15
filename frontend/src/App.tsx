
import { useState } from "react";

import LunarExplorer from "./Components/LunarExplorer/LunarExplorer";
import SiteDemo from "./Components/SiteDemo/SiteDemo";
import MapSetup from "./Components/WelcomeModal/MapSetup";
import MissionSetup from "./Components/WelcomeModal/MissionSetup";
import WelcomeModal from "./Components/WelcomeModal/WelcomeModal";
import type { InitialMapSite } from "./types/sites";

import "./App.css";

type AppMode = "explore" | "tutorial";

export default function App() {
  const [mode, setMode] = useState<AppMode>("explore");
  const [dialog, setDialog] = useState<"map" | "mission" | "help" | null>("help");
  const [mission, setMission] = useState({ date: "2028-02-08", durationDays: 20 });
  const [mapChoice, setMapChoice] = useState<{ site: InitialMapSite | null; generation: number } | null>(null);

  function startTutorial() {
    setDialog(mapChoice ? null : "mission");
    setMode("tutorial");
  }

  function exploreFreely() {
    setDialog(mapChoice ? null : "mission");
    setMode("explore");
  }

  // SCIENTIFIC WORKSPACE
  return (
    <div className="stamina-app">

      {/* APPLICATION HEADER */}
      <header className="stamina-app-header">

        <div className="stamina-app-brand">
          <img
            className="stamina-app-logo"
            src="/brand/stamina-logo.png"
            alt="STAMINA"
          />

          <span className="stamina-app-logo-separator">x</span>

          <img
            className="stamina-app-logo stamina-app-logo-partner"
            src="/brand/space-apps-logo.png"
            alt="NASA Space Apps Challenge"
          />

          <span className="stamina-app-separator">/</span>

          <span className="stamina-app-product">
            Lunar Explorer
          </span>
        </div>

        <div className="stamina-app-actions">

          <span className="stamina-app-mode">
            Lunar surface
          </span>

          <button
            type="button"
            onClick={() => setDialog("help")}
          >
            Help
          </button>

          <button
            type="button"
            className="stamina-app-tutorial-button"
            onClick={startTutorial}
            disabled={!mapChoice}
          >
            Site Demo
          </button>

        </div>
      </header>

      {/* MAIN SCIENTIFIC WORKSPACE */}
      <div className="stamina-workspace">
        {mapChoice && <LunarExplorer key={mapChoice.generation} initialSite={mapChoice.site ?? undefined} initialDate={mission.date} initialDurationDays={mission.durationDays} onMapArea={() => setDialog("map")} />}
      </div>

      {/* APPLICATION STATUS BAR */}
      <footer className="stamina-statusbar">
        <span>STAMINA · Lunar Landing Site Navigator</span>

        <span>
          NASA Space Apps Challenge 2026
        </span>
      </footer>

      {/* WELCOME MODAL */}
      {mode === "tutorial" && !dialog && <SiteDemo onClose={exploreFreely} />}
      {dialog === "help" && <WelcomeModal onStartTutorial={startTutorial} onExplore={exploreFreely} />}
      {dialog === "mission" && <MissionSetup initial={mission} onStart={value => {
        setMission(value);
        setMapChoice({ site: null, generation: 1 });
        setDialog(null);
      }} onBack={() => setDialog("help")} />}
      {dialog === "map" && (
        <MapSetup onChoose={site => {
          setMapChoice(previous => ({ site, generation: (previous?.generation ?? 0)+1 }));
          setDialog(null);
        }} onCancel={mapChoice ? () => setDialog(null) : undefined} />
      )}

    </div>
  );
}
