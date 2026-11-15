
import { useState } from "react";

import LunarExplorer from "./Components/LunarExplorer/LunarExplorer";
import SiteDemo from "./Components/SiteDemo/SiteDemo";
import WelcomeModal from "./Components/WelcomeModal/WelcomeModal";

import "./App.css";

type AppMode = "explore" | "tutorial";

export default function App() {
  const [mode, setMode] = useState<AppMode>("explore");
  const [showWelcome, setShowWelcome] = useState(true);

  function startTutorial() {
    setShowWelcome(false);
    setMode("tutorial");
  }

  function exploreFreely() {
    setShowWelcome(false);
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
            Lunar South Pole
          </span>

          <button
            type="button"
            onClick={() => setShowWelcome(true)}
          >
            Help
          </button>

          <button
            type="button"
            className="stamina-app-tutorial-button"
            onClick={startTutorial}
          >
            Site Demo ↗
          </button>

        </div>
      </header>

      {/* MAIN SCIENTIFIC WORKSPACE */}
      <div className="stamina-workspace">
        <LunarExplorer />
      </div>

      {/* APPLICATION STATUS BAR */}
      <footer className="stamina-statusbar">
        <span>STAMINA · Lunar Landing Site Navigator</span>

        <span>
          NASA Space Apps Challenge 2026
        </span>
      </footer>

      {/* WELCOME MODAL */}
      {mode === "tutorial" && !showWelcome && <SiteDemo onClose={exploreFreely} />}
      {showWelcome && (
        <WelcomeModal
          onStartTutorial={startTutorial}
          onExplore={exploreFreely}
        />
      )}

    </div>
  );
}
