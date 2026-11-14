
import type {
  FilterDefinition,
  FilterStates,
} from "../types/explorer";

export const filterRegistry: FilterDefinition[] = [
  {
    id: "sunElevation",
    label: "Sun elevation",
    description: "Minimum solar elevation angle",
    type: "slider",
    min: -10,
    max: 30,
    step: 1,
    unit: "°",
    defaultValue: 5,
  },

  {
    id: "earthElevation",
    label: "Earth elevation",
    description: "Minimum Earth elevation angle",
    type: "slider",
    min: -10,
    max: 30,
    step: 1,
    unit: "°",
    defaultValue: 0,
  },

  {
    id: "terrain",
    label: "Terrain overlay",
    description: "Display lunar topography",
    type: "toggle",
    defaultValue: false,
  },

  {
    id: "analysisMode",
    label: "Analysis mode",
    description: "Choose how to analyze the site",
    type: "select",
    defaultValue: "instant",
    options: [
      { label: "Single instant", value: "instant" },
      { label: "Mission duration", value: "period" },
    ],
  },
];

export function createInitialFilters(): FilterStates {
  return Object.fromEntries(
    filterRegistry.map((filter) => [
      filter.id,
      {
        enabled: false,
        value: filter.defaultValue,
      },
    ])
  );
}
