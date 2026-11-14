
import "./WelcomeModal.css";

type WelcomeModalProps = {
  onStartTutorial: () => void;
  onExplore: () => void;
};

export default function WelcomeModal({
  onStartTutorial,
  onExplore,
}: WelcomeModalProps) {
  return (
    <div className="welcome-overlay">
      <div
        className="welcome-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="welcome-title"
      >
        <div className="welcome-symbol">☾</div>

        <p className="welcome-eyebrow">
          WELCOME TO STAMINA
        </p>

        <h2 id="welcome-title">
          Ready to explore the Moon?
        </h2>

        <p className="welcome-description">
          Discover how sunlight, lunar terrain, and
          Earth visibility shape the future of lunar exploration.
        </p>

        <div className="welcome-options">
          <div className="welcome-option featured">
            <div className="welcome-option-icon">🚀</div>

            <h3>Guided Mission Experience</h3>

            <p>
              Take the role of a mission planner.
              Configure a lunar expedition, face an
              unexpected launch delay, and explore
              possible landing site alternatives.
            </p>

            <button
              type="button"
              className="welcome-primary"
              onClick={onStartTutorial}
            >
              Begin Tutorial →
            </button>
          </div>

          <div className="welcome-option">
            <div className="welcome-option-icon">🌕</div>

            <h3>Free Exploration</h3>

            <p>
              Skip the tutorial and discover the
              STAMINA platform at your own pace.
            </p>

            <button
              type="button"
              className="welcome-secondary"
              onClick={onExplore}
            >
              Explore Freely →
            </button>
          </div>
        </div>

        <p className="welcome-footer">
          STAMINA · NASA Space Apps Challenge 2026
        </p>
      </div>
    </div>
  );
}
