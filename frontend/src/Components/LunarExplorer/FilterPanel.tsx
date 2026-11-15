
import { filterRegistry } from "../../filters/filterRegistry";
import TemperatureFilter from "./TemperatureFilter";
import type {
  FilterStates,
  FilterValue,
} from "../../types/explorer";
import type {
  TemperatureConfig,
  TemperatureSelectionStats,
} from "../../types/temperature";

type Props = {
  filters: FilterStates;
  onChange: (filters: FilterStates) => void;
  temperature: TemperatureConfig;
  onTemperatureChange: (config: TemperatureConfig) => void;
  temperatureSelection: TemperatureSelectionStats | null;
};

export default function FilterPanel({
  filters,
  onChange,
  temperature,
  onTemperatureChange,
  temperatureSelection,
}: Props) {
  function updateFilter(
    id: string,
    changes: Partial<FilterStates[string]>
  ) {
    onChange({
      ...filters,
      [id]: {
        ...filters[id],
        ...changes,
      },
    });
  }

  return (
    <aside className="explorer-filters">
      <h2>Analysis Filters</h2>

      <p>
        Customize the environmental constraints
        for your lunar site.
      </p>
      <p>Enable Sun or Earth visibility to show only visible areas on the map at the displayed time, accounting for LOLA terrain. With both enabled, only their intersection remains. Run Analysis for mission percentages and outages.</p>

      {filterRegistry.map((filter) => {
        const state = filters[filter.id];

        if (!state) return null;

        if (filter.id === "analysisMode") return (
          <div className="filter-item" key={filter.id}>
            <label className="filter-heading" htmlFor="analysis-mode"><strong>{filter.label}</strong></label>
            <select id="analysis-mode" value={String(state.value)}
              onChange={event => updateFilter(filter.id, { enabled: true, value: event.target.value })}>
              {filter.options?.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <small>{state.value === "instant"
              ? "Visibility at 00:00 UTC on the selected date. No mission duration or outage lengths."
              : "Visibility and outages over the selected mission duration."}</small>
          </div>
        );

        return (
          <div className="filter-item" key={filter.id}>
            <label className="filter-heading">
              <input
                type="checkbox"
                checked={state.enabled}
                onChange={(e) =>
                  updateFilter(filter.id, {
                    enabled: e.target.checked,
                  })
                }
              />

              <strong>{filter.label}</strong>
            </label>

            <small>{filter.description}</small>

            {state.enabled && filter.type === "slider" && (
              <div className="filter-control">
                <div className="filter-value">
                  {state.value}{filter.unit}
                </div>

                <input
                  type="range"
                  aria-label={`${filter.label} minimum`}
                  min={filter.min}
                  max={filter.max}
                  step={filter.step ?? 1}
                  value={Number(state.value)}
                  onChange={(e) =>
                    updateFilter(filter.id, {
                      value: Number(e.target.value),
                    })
                  }
                />
              </div>
            )}

            {state.enabled && filter.type === "toggle" && (
              <label className="filter-toggle">
                <input
                  type="checkbox"
                  checked={Boolean(state.value)}
                  onChange={(e) =>
                    updateFilter(filter.id, {
                      value: e.target.checked,
                    })
                  }
                />
                Show overlay
              </label>
            )}

            {state.enabled && filter.type === "select" && (
              <select
                value={String(state.value)}
                onChange={(e) =>
                  updateFilter(filter.id, {
                    value: e.target.value as FilterValue,
                  })
                }
              >
                {filter.options?.map((option) => (
                  <option
                    key={option.value}
                    value={option.value}
                  >
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </div>
        );
      })}

      {/* SOUTH POLE TEMPERATURE LAYER (drives the map) */}
      <TemperatureFilter
        config={temperature}
        onChange={onTemperatureChange}
        selectionStats={temperatureSelection}
      />
    </aside>
  );
}
