
// Diviner south pole temperature layer shown on the map, and the
// interval selection applied to it. Exported under
// "southPoleTemperatures" in the configuration JSON.

export type TemperatureSeason = "summer" | "winter";

export type TemperatureStatistic =
  | "avg"
  | "min"
  | "max"
  | "amplitude";

export type KelvinRange = {
  min: number;
  max: number;
};

export type TemperatureConfig = {
  season: TemperatureSeason;
  statistic: TemperatureStatistic;
  iceStabilityThresholdK: number;
  // Highlight pixels whose layer value and seasonal amplitude
  // are both inside these ranges.
  selectionEnabled: boolean;
  temperatureK: KelvinRange;
  amplitudeK: KelvinRange;
};

// Selected area reported back by the map.
export type TemperatureSelectionStats = {
  areaKm2: number;
  percentOfCap: number;
};

export const TEMPERATURE_SEASONS: {
  value: TemperatureSeason;
  label: string;
}[] = [
  { value: "summer", label: "Summer" },
  { value: "winter", label: "Winter" },
];

export const TEMPERATURE_STATISTICS: {
  value: TemperatureStatistic;
  label: string;
}[] = [
  { value: "avg", label: "Avg" },
  { value: "min", label: "Min" },
  { value: "max", label: "Max" },
  { value: "amplitude", label: "Amplitude" },
];

// Slider limits, in kelvin
export const KELVIN_SLIDER = { min: 0, max: 450 };

export const DEFAULT_TEMPERATURE_CONFIG: TemperatureConfig = {
  season: "summer",
  statistic: "max",
  iceStabilityThresholdK: 110,
  selectionEnabled: false,
  temperatureK: { min: 0, max: 110 },
  amplitudeK: { min: 0, max: 300 },
};
