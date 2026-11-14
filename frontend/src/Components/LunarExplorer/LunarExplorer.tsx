
import { useState } from "react";

import FilterPanel from "./FilterPanel";
import MapPanel from "./MapPanel";
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

import { COMPARE_LIMIT } from "../../types/sites";
import type { CompareSite } from "../../types/sites";


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
  // Selected lunar landing site
  const [selectedSite, setSelectedSite] =
    useState<LunarSite | null>(null);

  // Comparison grid over the map, and the sites it can show
  const [comparing, setComparing] = useState(false);
  const [compareSites, setCompareSites] = useState<CompareSite[]>([]);
  const compareCount = compareSites.length;
  const canCompare = compareCount > 0 && compareCount <= COMPARE_LIMIT;

  // Right panel (site inspector) folded to a thin strip
  const [inspectorOpen, setInspectorOpen] = useState(true);

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
  const validDuration =
    Number.isInteger(durationDays) &&
    durationDays >= 1 &&
    durationDays <= 365;

  // Check if scientific analysis can run
  const canAnalyze =
    validSite &&
    validDuration &&
    Boolean(date) &&
    !loading;

  // Count enabled standard filters
  const activeFilterCount = Object.values(filters)
    .filter((filter) => filter.enabled).length;

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
    setResult(null);
    setError("");
  }

  // Deselect the site (e.g. when it is switched off on the map)
  function clearSite() {
    setSelectedSite(null);
    clearResults();
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
      setResult(data);

    } catch (error) {
      console.error(
        "STAMINA scientific analysis error:",
        error
      );

      setError(
        error instanceof Error
          ? error.message
          : "Scientific engine unavailable."
      );

    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      className={
        "lunar-explorer" +
        (inspectorOpen ? "" : " inspector-collapsed")
      }
    >

      {/* =====================================
          LEFT SIDEBAR — FILTERS
      ===================================== */}
      <aside className="explorer-left-panel">

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

        {/* INTERACTIVE MAP */}
        <div className="explorer-map-area">
          <MapPanel
            selectedSite={selectedSite}
            onSiteSelect={changeSite}
            onSiteClear={clearSite}
            temperature={temperature}
            onTemperatureSelection={setTemperatureSelection}
            comparing={comparing}
            onCompareClose={() => setComparing(false)}
            onCompareSitesChange={setCompareSites}
          />
        </div>

        {/* MISSION TIMELINE */}
        <div className="explorer-timeline">

          <div className="explorer-timeline-heading">
            <strong>Mission Timeline</strong>
            <span>Visibility data pending</span>
          </div>

          <div className="explorer-timeline-track" />

          <div className="explorer-timeline-labels">
            <span>Start: {date}</span>
            <span>{durationDays} Earth days</span>
          </div>

        </div>

      </section>

      {/* =====================================
          RIGHT SIDEBAR — SCIENTIFIC ANALYSIS
      ===================================== */}
      <aside className="explorer-right-panel">

        {/* FOLD / UNFOLD THE PANEL */}
        <button
          type="button"
          className="inspector-toggle"
          onClick={() => setInspectorOpen(!inspectorOpen)}
          aria-expanded={inspectorOpen}
          title={inspectorOpen ? "Hide the site inspector" : "Show the site inspector"}
        >
          <span>Site inspector</span>
          <span aria-hidden="true">{inspectorOpen ? "›" : "‹"}</span>
        </button>

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
              Start date (UTC)

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
            <label>
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
            </label>

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

          {/* COMPARE: the switched-on polar sites side by side over the map */}
          <button
            type="button"
            className={"explorer-compare-button" + (comparing ? " active" : "")}
            disabled={!comparing && !canCompare}
            aria-pressed={comparing}
            onClick={() => setComparing(!comparing)}
          >
            {comparing
              ? "Close comparison ✕"
              : `Compare ${compareCount} site${compareCount === 1 ? "" : "s"} ▦`}
          </button>

          {!comparing && !canCompare && (
            <p className="explorer-data-note">
              {compareCount === 0
                ? "Switch on 1 to 6 polar sites in the map's site menu to compare them."
                : `At most ${COMPARE_LIMIT} sites: switch off ${compareCount - COMPARE_LIMIT} in the map's site menu.`}
            </p>
          )}

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
              <span>Solar availability</span>

              <strong>
                {formatMetric(
                  result?.sunlightPercent,
                  "%"
                )}
              </strong>
            </div>

            {/* EARTH VISIBILITY */}
            <div>
              <span>Earth visibility</span>

              <strong>
                {formatMetric(
                  result?.earthVisibilityPercent,
                  "%"
                )}
              </strong>
            </div>

            {/* MAXIMUM DARKNESS */}
            <div>
              <span>Maximum darkness</span>

              <strong>
                {formatMetric(
                  result?.maxDarknessHours,
                  " h"
                )}
              </strong>
            </div>

            {/* COMMUNICATION BLACKOUT */}
            <div>
              <span>Communication blackout</span>

              <strong>
                {formatMetric(
                  result?.maxCommunicationBlackoutHours,
                  " h"
                )}
              </strong>
            </div>

          </div>

        </div>

        {/* SCIENTIFIC ENGINE STATUS */}
        <div className="explorer-engine-status">

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
