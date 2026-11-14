
export const CUSTOM_METRICS = {
  sunlightPercent: {
    label: "Sunlight availability",
    unit: "%",
    defaultThreshold: 65,
    defaultOperator: "gte",
  },
  earthVisibilityPercent: {
    label: "Earth visibility",
    unit: "%",
    defaultThreshold: 50,
    defaultOperator: "gte",
  },
  maxDarknessHours: {
    label: "Maximum darkness",
    unit: "h",
    defaultThreshold: 24,
    defaultOperator: "lte",
  },
  maxCommunicationBlackoutHours: {
    label: "Communication blackout",
    unit: "h",
    defaultThreshold: 24,
    defaultOperator: "lte",
  },
} as const;

export type CustomMetric = keyof typeof CUSTOM_METRICS;
export type CustomOperator = "gte" | "lte";

export type CustomFilterRule = {
  id: string;
  label: string;
  metric: CustomMetric;
  operator: CustomOperator;
  threshold: number;
  enabled: boolean;
};

export type CustomFilterEvaluation = {
  id: string;
  actualValue: number | null;
  passed: boolean | null;
  message?: string;
};
