
import { useState } from "react";

import {
  KELVIN_SLIDER,
  TEMPERATURE_SEASONS,
  TEMPERATURE_STATISTICS,
} from "../../types/temperature";

import type {
  KelvinRange,
  TemperatureConfig,
  TemperatureSelectionStats,
} from "../../types/temperature";

import "./TemperatureFilter.css";

type Props = {
  config: TemperatureConfig;
  onChange: (config: TemperatureConfig) => void;
  selectionStats: TemperatureSelectionStats | null;
};

// Data products not wired in yet (Diviner PCP time slices, SPICE).
const TODO_LAYERS = [
  "Diurnal cycle by local time (PCP)",
  "Seasonal Ls bins (PCP)",
  "Mission window from SPICE ephemeris",
];

// Two thumbs on one track; the interval between them is highlighted.
function RangeSlider({
  label,
  range,
  onChange,
}: {
  label: string;
  range: KelvinRange;
  onChange: (range: KelvinRange) => void;
}) {
  const span = KELVIN_SLIDER.max - KELVIN_SLIDER.min;
  const left = (100 * (range.min - KELVIN_SLIDER.min)) / span;
  const right = (100 * (range.max - KELVIN_SLIDER.min)) / span;

  return (
    <div className="temperature-range">
      <div className="temperature-range-heading">
        <span>{label}</span>
        <strong>{range.min}–{range.max} K</strong>
      </div>

      <div className="temperature-dual">
        <div className="temperature-dual-track" />
        <div
          className="temperature-dual-fill"
          style={{ left: `${left}%`, width: `${right - left}%` }}
        />

        {/* The thumbs can't cross: each stops at the other. */}
        <input
          type="range"
          min={KELVIN_SLIDER.min}
          max={KELVIN_SLIDER.max}
          value={range.min}
          aria-label={`${label} minimum`}
          style={{ zIndex: range.min > span / 2 ? 2 : 1 }}
          onChange={(e) =>
            onChange({
              ...range,
              min: Math.min(Number(e.target.value), range.max),
            })
          }
        />
        <input
          type="range"
          min={KELVIN_SLIDER.min}
          max={KELVIN_SLIDER.max}
          value={range.max}
          aria-label={`${label} maximum`}
          onChange={(e) =>
            onChange({
              ...range,
              max: Math.max(Number(e.target.value), range.min),
            })
          }
        />
      </div>
    </div>
  );
}

export default function TemperatureFilter({
  config,
  onChange,
  selectionStats,
}: Props) {
  const [isOpen, setIsOpen] = useState(true);
  const [isLayerOpen, setIsLayerOpen] = useState(true);

  function update(changes: Partial<TemperatureConfig>) {
    onChange({ ...config, ...changes });
  }

  return (
    <div className="filter-item temperature-filter">

      {/* SECTION HEADER */}
      <button
        type="button"
        className="temperature-fold"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <strong>Temperature</strong>
        <span>{isOpen ? "−" : "+"}</span>
      </button>

      <small>Diviner surface temperature, 80°S to the pole</small>

      {isOpen && (
        <div className="temperature-content">

          {/* LAYER SHOWN ON THE MAP */}
          <button
            type="button"
            className="temperature-subfold"
            onClick={() => setIsLayerOpen(!isLayerOpen)}
            aria-expanded={isLayerOpen}
          >
            <span>Layer</span>
            <span>{isLayerOpen ? "▾" : "▸"}</span>
          </button>

          {isLayerOpen && (
            <div className="temperature-layer">

              <div
                className="temperature-segmented"
                role="radiogroup"
                aria-label="Season"
              >
                {TEMPERATURE_SEASONS.map((season) => (
                  <label key={season.value}>
                    <input
                      type="radio"
                      name="temperature-season"
                      checked={config.season === season.value}
                      onChange={() => update({ season: season.value })}
                    />
                    <span>{season.label}</span>
                  </label>
                ))}
              </div>

              <div
                className="temperature-segmented"
                role="radiogroup"
                aria-label="Statistic"
              >
                {TEMPERATURE_STATISTICS.map((statistic) => (
                  <label key={statistic.value}>
                    <input
                      type="radio"
                      name="temperature-statistic"
                      checked={config.statistic === statistic.value}
                      onChange={() =>
                        update({ statistic: statistic.value })
                      }
                    />
                    <span>{statistic.label}</span>
                  </label>
                ))}
              </div>

              <ul className="temperature-todo">
                {TODO_LAYERS.map((layer) => (
                  <li key={layer}>
                    <span>[todo]</span> {layer}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ICE STABILITY THRESHOLD */}
          <div className="filter-control">
            <div className="temperature-range-heading">
              <span>Ice stability threshold</span>
              <strong>{config.iceStabilityThresholdK} K</strong>
            </div>

            <input
              type="range"
              min={40}
              max={200}
              step={5}
              value={config.iceStabilityThresholdK}
              aria-label="Ice stability threshold"
              onChange={(e) =>
                update({
                  iceStabilityThresholdK: Number(e.target.value),
                })
              }
            />
          </div>

          {/* INTERVAL SELECTION */}
          <label className="filter-heading temperature-selection-toggle">
            <input
              type="checkbox"
              checked={config.selectionEnabled}
              onChange={(e) =>
                update({ selectionEnabled: e.target.checked })
              }
            />
            <span>Highlight areas inside the intervals</span>
          </label>

          {config.selectionEnabled && (
            <>
              <RangeSlider
                label="Temperature"
                range={config.temperatureK}
                onChange={(temperatureK) => update({ temperatureK })}
              />

              <RangeSlider
                label={`Amplitude (${config.season})`}
                range={config.amplitudeK}
                onChange={(amplitudeK) => update({ amplitudeK })}
              />

              <p className="temperature-stats">
                {selectionStats
                  ? `${Math.round(selectionStats.areaKm2).toLocaleString("en")} km² selected · ${selectionStats.percentOfCap.toFixed(1)}% of the cap`
                  : "Waiting for the map…"}
              </p>
            </>
          )}

        </div>
      )}
    </div>
  );
}
