import type {
  CustomFilterEvaluation,
} from "./customFilters";

import type { LandingSite } from "./sites";

export type FilterDefinition = {
  id: string;
  label: string;
  description: string;

  type: "slider" | "toggle" | "select" | "visibility";

  min?: number;
  max?: number;
  step?: number;
  unit?: string;

  defaultValue: number | boolean | string;

  options?: {
    label: string;
    value: string;
  }[];
};

export type FilterValue = number | boolean | string;

export type FilterState = {
  enabled: boolean;
  value: FilterValue;
};

export type FilterStates = Record<string, FilterState>;

// Diviner surface temperature at a site, in kelvin (null = no data), per season
// ("annual" combines both) and statistic. Comes from the lunar map viewer.
export type SiteTemperatures = Record<
  "summer" | "winter" | "annual",
  Record<"avg" | "min" | "max" | "amplitude", number | null>
>;

export type LunarSite = {
  id: string;
  name: string;
  latitude?: number;
  longitude?: number;
  temperatures?: SiteTemperatures;
  // LOLA elevation relative to 1737.4 km, from the map.
  elevationM?: number | null;
  // Set when the site is one of the named landing sites.
  details?: LandingSite;
};

export type ScientificResult = {
  timeline?: MissionTimelineData;
  status: "computed" | "unavailable";
  siteId: string;
  sunlightPercent?: number;
  earthVisibilityPercent?: number;
  maxDarknessHours?: number;
  maxCommunicationBlackoutHours?: number;
  message?: string;
  customFilterResults?: CustomFilterEvaluation[];
};

export type MissionTimelineData = {
  startUtc: string;
  endUtc: string;
  sampleCount: number;
  instant: boolean;
  sun: VisibilitySegment[];
  earth: VisibilitySegment[];
};
export type VisibilitySegment = { start: number; end: number; visible: boolean };
