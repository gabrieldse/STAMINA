import { useEffect, useRef, useState } from "react";
import "./SiteDemo.css";

const steps = [
  { target: ".explorer-map-area", title: "Explore the lunar map", text: "Scroll to zoom, drag to move, and click the surface to select a location. You can also choose a named landing region from the map’s site list. Try it here—the map is live." },
  { target: ".explorer-left-panel", title: "Try the environmental filters", text: "Enable Sun visibility or Earth visibility to show only areas where that body clears the LOLA terrain horizon. Both enabled keeps their intersection. Terrain overlay adds elevation contours; Temperature displays the Diviner layers." },
  { target: ".explorer-analysis-form", title: "Set up your analysis", text: "Choose Single instant or Mission duration in Analysis mode on the left. Set the date on the right, and a duration for a mission. Single instant checks visibility at 00:00 UTC; mission mode covers the entire selected period." },
  { target: ".explorer-analysis-form", title: "Run a real analysis", text: "With a location selected, click Run Scientific Analysis. The site calculates Sun and Earth visibility for your settings. You can wait for it to finish before moving on; changing the site, date or filters clears the previous results." },
  { target: ".explorer-result-grid", title: "Read the results", text: "Mission mode reports solar availability, Earth visibility and the longest outages. Single instant shows whether each body center clears the LOLA terrain horizon. Terrain obstruction and lunar curvature are included." },
  { target: ".explorer-timeline", title: "Inspect the timeline", text: "After a mission analysis, gold bands show Sun visibility and blue bands show Earth visibility. Click a band or drag the slider to inspect a time in UTC. You’re ready to explore—your selections stay in place when you finish." },
];

export default function SiteDemo({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const current = steps[step];
  useEffect(() => {
    const previous = document.activeElement;
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("keydown", escape);
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, [onClose]);
  useEffect(() => {
    const target = document.querySelector(current.target);
    target?.classList.add("site-demo-highlight");
    target?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    titleRef.current?.focus({ preventScroll: true });
    return () => target?.classList.remove("site-demo-highlight");
  }, [current]);
  return <section className={`site-demo-card ${step === 5 ? "site-demo-card-top" : ""}`} aria-label="Site demo">
    <div className="site-demo-heading"><span>STAMINA · SITE DEMO · {step + 1}/{steps.length}</span>
      <button type="button" onClick={onClose} aria-label="Close site demo">×</button></div>
    <progress max={steps.length} value={step + 1} aria-label="Demo progress" />
    <h2 tabIndex={-1} ref={titleRef}>{current.title}</h2>
    <p>{current.text}</p>
    <div className="site-demo-actions">
      <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
      <button type="button" onClick={() => step === steps.length - 1 ? onClose() : setStep(step + 1)}>
        {step === steps.length - 1 ? "Finish demo" : "Next →"}
      </button>
    </div>
  </section>;
}
