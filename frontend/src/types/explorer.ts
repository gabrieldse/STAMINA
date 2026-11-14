import type {
  CustomFilterEvaluation,
} from "./customFilters";

export type FilterDefinition = {
  id: string;
  label: string;
  description: string;

  type: "slider" | "toggle" | "select";

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

export type LunarSite = {
  id: string;
  name: string;
  latitude?: number;
  longitude?: number;
};

export type ScientificResult = {
  status: "computed" | "unavailable";
  siteId: string;
  sunlightPercent?: number;
  earthVisibilityPercent?: number;
  maxDarknessHours?: number;
  maxCommunicationBlackoutHours?: number;
  message?: string;
  customFilterResults?: CustomFilterEvaluation[];
};
