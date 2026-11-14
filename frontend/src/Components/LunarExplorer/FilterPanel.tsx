
import { filterRegistry } from "../../filters/filterRegistry";
import type {
  FilterStates,
  FilterValue,
} from "../../types/explorer";

type Props = {
  filters: FilterStates;
  onChange: (filters: FilterStates) => void;
};

export default function FilterPanel({
  filters,
  onChange,
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

      {filterRegistry.map((filter) => {
        const state = filters[filter.id];

        if (!state) return null;

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
    </aside>
  );
}
