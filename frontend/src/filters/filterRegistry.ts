
import type {
  FilterDefinition,
  FilterStates,
} from "../types/explorer";

export const filterRegistry: FilterDefinition[] = [
  {
    id: "sunVisibility",
    label: "Sun visibility",
    description: "Sun center above the LOLA terrain horizon",
    type: "visibility",
    defaultValue: true,
  },
  {
    id: "earthVisibility",
    label: "Earth visibility",
    description: "Earth center above the LOLA terrain horizon",
    type: "visibility",
    defaultValue: true,
  },

  {
    id: "terrain",
    label: "Terrain overlay",
    description: "LOLA terrain relief; elevation contours on the default map and shaded relief around any chosen site",
    type: "toggle",
    defaultValue: true,
  },

  {
    id: "analysisMode",
    label: "Analysis mode",
    description: "Choose how to analyze the site",
    type: "select",
    defaultValue: "period",
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
        enabled: filter.id === "analysisMode",
        value: filter.defaultValue,
      },
    ])
  );
}
