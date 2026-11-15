
import { useRef, useState } from "react";
import MissionTimeline from "./MissionTimeline";

import FilterPanel from "./FilterPanel";
import MapTimeline from "./MapTimeline";
import AdvancedFilters from "./AdvancedFilters";

import { createInitialFilters } from "../../filters/filterRegistry";
import { analyzeLunarSite } from "../../services/scientificApi";

import type {
  LunarSite,
  FilterStates,
  ScientificResult,
} from "../../types/explorer";

import type {
  CustomFilterRule,
} from "../../types/customFilters";

import { DEFAULT_TEMPERATURE_CONFIG } from "../../types/temperature";

import type { LandingSite } from "../../types/sites";

import type {
  TemperatureConfig,
  TemperatureSelectionStats,
} from "../../types/temperature";

import "./LunarExplorer.css";

// Rows and columns of the surface temperature table
const TEMPERATURE_STATS = [
  ["avg", "Average"],
  ["min", "Minimum"],
  ["max", "Maximum"],
  ["amplitude", "Amplitude"],
] as const;

const TEMPERATURE_SEASONS = ["summer", "winter", "annual"] as const;

function formatKelvin(value: number | null | undefined) {
  return value != null && Number.isFinite(value)
    ? value.toFixed(1)
    : "—";
}

export default function LunarExplorer() {
  const [leftPanelOpen, setLeftPanelOpen] = useState(true);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const analysisVersion = useRef(0);
  // Selected lunar landing site
  const [selectedSite, setSelectedSite] =
    useState<LunarSite | null>(null);

  // Standard filters
  const [filters, setFilters] =
    useState<FilterStates>(createInitialFilters);

  // Custom filters (manual or uploaded JSON)
  const [customRules, setCustomRules] =
    useState<CustomFilterRule[]>([]);

  // South pole temperature layer and selection shown on the map
  const [temperature, setTemperature] =
    useState<TemperatureConfig>(DEFAULT_TEMPERATURE_CONFIG);

  const [temperatureSelection, setTemperatureSelection] =
    useState<TemperatureSelectionStats | null>(null);

  // Analysis parameters
  const [date, setDate] = useState("2032-11-01");
  const [durationDays, setDurationDays] = useState(14);

  // Scientific results
  const [result, setResult] =
    useState<ScientificResult | null>(null);

  // API status
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Validate selected lunar coordinates
  const validSite =
    selectedSite !== null &&
    selectedSite.latitude != null &&
    selectedSite.longitude != null &&
    Number.isFinite(selectedSite.latitude) &&
    Number.isFinite(selectedSite.longitude) &&
    selectedSite.latitude >= -90 &&
    selectedSite.latitude <= 90 &&
    selectedSite.longitude >= -180 &&
    selectedSite.longitude <= 360;

  // Validate duration
  const instantMode = filters.analysisMode?.value === "instant";
  const validDuration =
    instantMode || (Number.isInteger(durationDays) &&
    durationDays >= 1 &&
    durationDays <= 365);

  // Check if scientific analysis can run
  const canAnalyze =
    validSite &&
    validDuration &&
    Boolean(date) &&
    !loading;

  // Count enabled standard filters
  const activeFilterCount = Object.entries(filters)
    .filter(([id, filter]) => id !== "analysisMode" && filter.enabled).length;

  // Count enabled custom filters
  const activeCustomFilterCount = customRules
    .filter((rule) => rule.enabled).length;

  const isComputed = result?.status === "computed";

  // Format scientific metrics
  function formatMetric(
    value: number | undefined,
    unit: string
  ) {
    return isComputed &&
      value != null &&
      Number.isFinite(value)
      ? `${value}${unit}`
      : "—";
  }

  // Clear previous scientific results
  function clearResults() {
    analysisVersion.current += 1;
    setResult(null);
    setError("");
  }

  // Pick a named landing site from the list
  function selectLandingSite(site: LandingSite) {
    changeSite({
      id: site.id,
      name: site.name,
      latitude: site.latitude,
      longitude: site.longitude,
      details: site,
    });
  }

  // Change selected lunar site
  function changeSite(site: LunarSite) {
    setSelectedSite(site);
    clearResults();
  }

  // Change standard filters
  function changeFilters(nextFilters: FilterStates) {
    setFilters(nextFilters);
    clearResults();
  }

  // Change manually created or imported custom filters
  function changeCustomRules(
    nextRules: CustomFilterRule[]
  ) {
    setCustomRules(nextRules);
    clearResults();
  }

  // Request scientific calculations from Python
  async function runAnalysis() {
    if (!selectedSite || !canAnalyze) {
      return;
    }

    setLoading(true);
    clearResults();

    const version = analysisVersion.current;
    try {
      // Send all analysis parameters to backend
      const data = await analyzeLunarSite(
        selectedSite,
        date,
        durationDays,
        filters,
        customRules
      );

      // Store backend response
      if (version === analysisVersion.current) setResult(data);

    } catch (error) {
      console.error(
        "STAMINA scientific analysis error:",
        error
      );

      if (version === analysisVersion.current) setError(
        error instanceof Error
          ? error.message
          : "Scientific engine unavailable."
      );

    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={`lunar-explorer${leftPanelOpen ? "" : " left-panel-hidden"}${rightPanelOpen ? "" : " right-panel-hidden"}`}>

      {/* =====================================
          LEFT SIDEBAR — FILTERS
      ===================================== */}
      <aside id="explorer-filters-panel" className="explorer-left-panel" hidden={!leftPanelOpen}>

        <div className="explorer-pane-caption">
          <span>ENVIRONMENTAL LAYERS</span>

          <span>
            {activeFilterCount + activeCustomFilterCount}
            {" "}active
          </span>
        </div>

        {/* STANDARD FILTERS */}
        <FilterPanel
          filters={filters}
          onChange={changeFilters}
          temperature={temperature}
          onTemperatureChange={setTemperature}
          temperatureSelection={temperatureSelection}
        />

        {/* ADVANCED / UPLOADED FILTERS */}
        <AdvancedFilters
          filters={filters}
          onImport={(configuration) => {
            if (configuration.filters) setFilters(configuration.filters);
            if (configuration.temperature) setTemperature(configuration.temperature);
            setCustomRules(configuration.rules);
            clearResults();
          }}
          rules={customRules}
          onChange={changeCustomRules}
          evaluations={
            result?.customFilterResults ?? []
          }
          durationDays={durationDays}
          temperature={temperature}
        />

      </aside>

      {/* =====================================
          CENTER — LUNAR MAP
      ===================================== */}
      <section className="explorer-center-panel">

        {/* MAP TOOLBAR */}
        <div className="explorer-map-toolbar">

          <button type="button" className="explorer-panel-toggle" aria-controls="explorer-filters-panel" aria-expanded={leftPanelOpen}
            title={`${leftPanelOpen ? "Hide" : "Show"} filters panel`} onClick={() => setLeftPanelOpen(open => !open)}>
            <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="2" y="3" width="16" height="14" rx="3" stroke="currentColor" strokeWidth="1.5" /><path d="M7 3v14" stroke="currentColor" strokeWidth="1.5" /><path d={leftPanelOpen ? "m12 7-3 3 3 3" : "m10 7 3 3-3 3"} stroke="currentColor" strokeWidth="1.5" /></svg>
            <span>{leftPanelOpen ? "Hide filters" : "Show filters"}</span>
          </button>

          <div>
            <strong>Lunar Surface Explorer</strong>
            <span>South Pole Region</span>
          </div>

          <span className="explorer-map-context">
            {selectedSite
              ? `Selected: ${selectedSite.name}`
              : "No site selected"}
          </span>

          <button type="button" className="explorer-panel-toggle" aria-controls="explorer-inspector-panel" aria-expanded={rightPanelOpen}
            title={`${rightPanelOpen ? "Hide" : "Show"} site details panel`} onClick={() => setRightPanelOpen(open => !open)}>
            <span>{rightPanelOpen ? "Hide details" : "Show details"}</span>
            <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="2" y="3" width="16" height="14" rx="3" stroke="currentColor" strokeWidth="1.5" /><path d="M13 3v14" stroke="currentColor" strokeWidth="1.5" /><path d={rightPanelOpen ? "m8 7 3 3-3 3" : "m10 7-3 3 3 3"} stroke="currentColor" strokeWidth="1.5" /></svg>
          </button>

        </div>

        {/* INTERACTIVE MAP */}
        <MapTimeline
            date={date}
            durationDays={durationDays}
            selectedSite={selectedSite}
            filters={filters}
            onSiteSelect={changeSite}
            onLandingSiteSelect={selectLandingSite}
            temperature={temperature}
            onTemperatureSelection={setTemperatureSelection}
          />

      </section>

      {/* =====================================
          RIGHT SIDEBAR — SCIENTIFIC ANALYSIS
      ===================================== */}
      <aside id="explorer-inspector-panel" className="explorer-right-panel" hidden={!rightPanelOpen}>

        {/* PANEL HEADER */}
        <div className="explorer-inspector-heading">

          <p className="explorer-panel-kicker">
            STAMINA / SITE INSPECTOR
          </p>

          <h2>Scientific Analysis</h2>

          <p>
            Analyze environmental conditions
            at your selected lunar location.
          </p>

        </div>

        {/* SELECTED LANDING SITE */}
        <div className="explorer-selected-site">

          <span>SELECTED LANDING SITE</span>

          <strong>
            {selectedSite?.name ??
              "No location selected"}
          </strong>

          {validSite && selectedSite && (
            <small>
              Lat: {selectedSite.latitude?.toFixed(4)}°
              {" / "}
              Lon: {selectedSite.longitude?.toFixed(4)}°
              {selectedSite.elevationM != null &&
                ` · Elevation: ${selectedSite.elevationM.toLocaleString("en")} m`}
            </small>
          )}

          {selectedSite && !validSite && (
            <small>
              Coordinates not yet available or invalid.
            </small>
          )}

        </div>

        {/* SURFACE TEMPERATURE (from the lunar map) */}
        {selectedSite?.temperatures && (
          <div className="explorer-inspector-section">

            <h3>Surface Temperature</h3>

            <table className="explorer-temperature-table">
              <thead>
                <tr>
                  <th>Kelvin</th>
                  <th>Summer</th>
                  <th>Winter</th>
                  <th>Annual</th>
                </tr>
              </thead>
              <tbody>
                {TEMPERATURE_STATS.map(([stat, label]) => (
                  <tr key={stat}>
                    <td>{label}</td>
                    {TEMPERATURE_SEASONS.map((season) => (
                      <td key={season}>
                        {formatKelvin(
                          selectedSite.temperatures?.[season][stat]
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="explorer-data-note explorer-secondary">
              Diviner season summaries (Williams et al. 2019).
              Water ice is stable where the annual maximum
              stays below 110 K.
            </p>

          </div>
        )}

        {/* MISSION PARAMETERS */}
        <div className="explorer-inspector-section">

          <h3>Mission Parameters</h3>

          <div className="explorer-analysis-form">

            {/* START DATE */}
            <label>
              {instantMode ? "Observation date (00:00 UTC)" : "Start date (UTC)"}

              <input
                type="date"
                value={date}
                onChange={(e) => {
                  setDate(e.target.value);
                  clearResults();
                }}
              />
            </label>

            {/* MISSION DURATION */}
            {!instantMode && <label>
              Analysis duration (Earth days)

              <input
                type="number"
                min={1}
                max={365}
                step={1}
                value={durationDays}
                onChange={(e) => {
                  setDurationDays(
                    Number(e.target.value)
                  );

                  clearResults();
                }}
              />
            </label>}

            {/* ANALYSIS BUTTON */}
            <button
              type="button"
              disabled={!canAnalyze}
              onClick={runAnalysis}
            >
              {loading
                ? "Analyzing..."
                : "Run Scientific Analysis →"}
            </button>

          </div>

        </div>

        {/* ACTIVE FILTER SUMMARY */}
        <div className="explorer-inspector-section">

          <h3>Active Filters</h3>

          <p className="explorer-data-note">
            Standard: {activeFilterCount}
            {" · "}
            Custom: {activeCustomFilterCount}
          </p>

          {activeCustomFilterCount > 0 && (
            <p className="explorer-data-note">
              Custom requirements will be submitted
              to the scientific engine during analysis.
            </p>
          )}

        </div>

        {/* SCIENTIFIC METRICS */}
        <div className="explorer-inspector-section">

          <h3>Environmental Results</h3>

          <div className="explorer-result-grid">

            {/* SOLAR AVAILABILITY */}
            <div>
              <span>{instantMode ? "Sun at observation time" : "Solar availability"}</span>

              <strong>
                {instantMode && isComputed ? (result?.sunlightPercent === 100 ? "Above threshold" : "Below threshold") : formatMetric(
                  result?.sunlightPercent,
                  "%"
                )}
              </strong>
            </div>

            {/* EARTH VISIBILITY */}
            <div>
              <span>{instantMode ? "Earth at observation time" : "Earth visibility"}</span>

              <strong>
                {instantMode && isComputed ? (result?.earthVisibilityPercent === 100 ? "Above threshold" : "Below threshold") : formatMetric(
                  result?.earthVisibilityPercent,
                  "%"
                )}
              </strong>
            </div>

            {/* MAXIMUM DARKNESS */}
            {!instantMode && <div>
              <span>Maximum darkness</span>

              <strong>
                {formatMetric(
                  result?.maxDarknessHours,
                  " h"
                )}
              </strong>
            </div>}

            {/* COMMUNICATION BLACKOUT */}
            {!instantMode && <div>
              <span>Communication blackout</span>

              <strong>
                {formatMetric(
                  result?.maxCommunicationBlackoutHours,
                  " h"
                )}
              </strong>
            </div>}

          </div>

        </div>

        {result?.timeline && <details className="explorer-inspector-section">
          <summary>Selected site analysis · 10-minute detail</summary>
          <MissionTimeline key={`${selectedSite?.id}-${date}-${durationDays}-${loading}`} data={result.timeline} loading={loading} />
        </details>}

        {/* SCIENTIFIC ENGINE STATUS */}
        <div className="explorer-engine-status">
          {result?.status === "computed" && result.message && <p>{result.message}</p>}

          {/* API ERRORS */}
          {error && (
            <p
              className="explorer-error"
              role="alert"
            >
              {error}
            </p>
          )}

          {/* BACKEND UNAVAILABLE */}
          {result?.status === "unavailable" && (
            <p>
              {result.message ??
                "Scientific data unavailable."}
            </p>
          )}

          {/* NO SELECTED LOCATION */}
          {!selectedSite && (
            <p>
              Select a location on the lunar map
              to begin an analysis.
            </p>
          )}

          {/* INVALID COORDINATES */}
          {selectedSite && !validSite && (
            <p>
              Scientific analysis requires
              valid lunar coordinates.
            </p>
          )}

          <small>
            Scientific metrics require validated
            ephemeris and terrain data.
          </small>

        </div>

      </aside>

    </main>
  );
}
