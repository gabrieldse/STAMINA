import "./MissionTutorial.css";
import { useState } from "react";

import MissionSetup from "./MissionSetup";
import SiteSelection from "./SiteSelection";
import MissionEvaluation from "./MissionEvaluation";
import MissionDelay from "./MissionDelay";
import MissionReassessment from "./MissionReassessment";
import SiteComparison from "./SiteComparison";
import MissionReport from "./MissionReport";

import type {
  MissionConfig,
  LandingSite,
} from "./MissionTypes";

export default function MissionTutorial() {
  const [step, setStep] = useState(1);

  const [mission, setMission] =
    useState<MissionConfig | null>(null);

  const [originalSite, setOriginalSite] =
    useState<LandingSite | null>(null);

  const [finalSite, setFinalSite] =
    useState<LandingSite | null>(null);

  const [delayDays, setDelayDays] = useState(12);

  function startMission(config: MissionConfig) {
    setMission(config);
    setOriginalSite(null);
    setFinalSite(null);
    setDelayDays(12);
    setStep(2);
  }

  function selectInitialSite(site: LandingSite) {
    setOriginalSite(site);
    setFinalSite(null);
    setStep(3);
  }

  function selectDelay(days: number) {
    setDelayDays(days);
    setStep(5);
  }

  function selectFinalSite(site: LandingSite) {
    setFinalSite(site);
    setStep(7);
  }

  function restart() {
    setMission(null);
    setOriginalSite(null);
    setFinalSite(null);
    setDelayDays(12);
    setStep(1);
  }

  if (step === 1) {
    return <MissionSetup onContinue={startMission} />;
  }

  if (step === 2 && mission) {
    return (
      <SiteSelection
        mission={mission}
        onBack={() => setStep(1)}
        onContinue={selectInitialSite}
      />
    );
  }

  if (step === 3 && mission && originalSite) {
    return (
      <MissionEvaluation
        mission={mission}
        site={originalSite}
        onBack={() => setStep(2)}
        onContinue={() => setStep(4)}
      />
    );
  }

  if (step === 4 && mission && originalSite) {
    return (
      <MissionDelay
        mission={mission}
        site={originalSite}
        onBack={() => setStep(3)}
        onContinue={selectDelay}
      />
    );
  }

  if (step === 5 && mission && originalSite) {
    return (
      <MissionReassessment
        mission={mission}
        site={originalSite}
        delayDays={delayDays}
        onBack={() => setStep(4)}
        onContinue={() => setStep(6)}
      />
    );
  }

  if (step === 6 && mission && originalSite) {
    return (
      <SiteComparison
        mission={mission}
        originalSite={originalSite}
        delayDays={delayDays}
        onBack={() => setStep(5)}
        onContinue={selectFinalSite}
      />
    );
  }

  if (
    step === 7 &&
    mission &&
    originalSite &&
    finalSite
  ) {
    return (
      <MissionReport
        mission={mission}
        originalSite={originalSite}
        finalSite={finalSite}
        delayDays={delayDays}
        onBack={() => setStep(6)}
        onRestart={restart}
      />
    );
  }

  return null;
}
