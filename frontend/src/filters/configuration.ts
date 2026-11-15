import { CUSTOM_METRICS } from "../types/customFilters";
import type { CustomMetric, CustomOperator, CustomFilterRule } from "../types/customFilters";
import type { FilterStates } from "../types/explorer";
import type { TemperatureConfig } from "../types/temperature";
import { filterRegistry } from "./filterRegistry";

export type ImportedConfiguration = {
  rules: CustomFilterRule[];
  filters?: FilterStates;
  temperature?: TemperatureConfig;
};

export function parseConfiguration(data: unknown): ImportedConfiguration {
  if (!isObject(data) || data.version !== 1) throw new Error("Unsupported configuration version.");
  const result: ImportedConfiguration = {
    // Older temperature-only exports omitted the rules array.
    rules: parseFilterFile({ ...data, rules: data.rules ?? (data.southPoleTemperatures ? [] : undefined) }),
  };
  if (data.filters !== undefined) {
    if (!isObject(data.filters)) throw new Error("Invalid built-in filters.");
    const filters: FilterStates = {};
    if (Object.keys(data.filters).some(id => !filterRegistry.some(filter => filter.id === id))) {
      throw new Error("Configuration contains an unsupported built-in filter.");
    }
    for (const definition of filterRegistry) {
      const state = data.filters[definition.id];
      if (!isObject(state) || typeof state.enabled !== "boolean") throw new Error(`Missing or invalid ${definition.label} settings.`);
      const value = state.value;
      const valid = definition.type === "toggle" ? typeof value === "boolean"
        : definition.type === "select" ? definition.options?.some(option => option.value === value)
        : typeof value === "number" && Number.isFinite(value) && value >= (definition.min ?? -Infinity) && value <= (definition.max ?? Infinity);
      if (!valid) throw new Error(`Invalid value for ${definition.label}.`);
      filters[definition.id] = { enabled: state.enabled, value: value as FilterStates[string]["value"] };
    }
    result.filters = filters;
  }
  if (data.southPoleTemperatures !== undefined) {
    const t = data.southPoleTemperatures;
    if (!isObject(t) || typeof t.enabled !== "boolean" || !isObject(t.layer) || !isObject(t.selection)
      || typeof t.selection.enabled !== "boolean"
      || (t.layer.season !== "summer" && t.layer.season !== "winter")
      || !["avg", "min", "max", "amplitude"].includes(String(t.layer.statistic))
      || typeof t.iceStabilityThresholdK !== "number" || !Number.isFinite(t.iceStabilityThresholdK)
      || t.iceStabilityThresholdK < 40 || t.iceStabilityThresholdK > 200) throw new Error("Invalid temperature settings.");
    function range(value: unknown) {
      if (!isObject(value) || typeof value.min !== "number" || typeof value.max !== "number"
        || !Number.isFinite(value.min) || !Number.isFinite(value.max)
        || value.min < 0 || value.max > 450 || value.min > value.max) throw new Error("Invalid temperature interval.");
      return { min: value.min, max: value.max };
    }
    result.temperature = {
      enabled: t.enabled, season: t.layer.season, statistic: t.layer.statistic as TemperatureConfig["statistic"],
      iceStabilityThresholdK: t.iceStabilityThresholdK, selectionEnabled: t.selection.enabled,
      temperatureK: range(t.selection.temperatureK), amplitudeK: range(t.selection.amplitudeK),
    };
  }
  return result;
}

// Snapshot every filter, including disabled values and empty custom rules.
export function buildConfiguration(
  temperature: TemperatureConfig,
  rules: CustomFilterRule[],
  filters: FilterStates
) {
  return {
    version: 1,
    exportedAt: new Date().toISOString(),
    southPoleTemperatures: {
      enabled: temperature.enabled,
      layer: {
        season: temperature.season,
        statistic: temperature.statistic,
      },
      iceStabilityThresholdK: temperature.iceStabilityThresholdK,
      selection: {
        enabled: temperature.selectionEnabled,
        temperatureK: { ...temperature.temperatureK },
        amplitudeK: { ...temperature.amplitudeK },
      },
    },
    filters: structuredClone(filters),
    rules: structuredClone(rules),
  };
}

function isObject(
  value: unknown
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

// Check uploaded JSON before accepting its rules.
function parseFilterFile(
  data: unknown
): CustomFilterRule[] {
  if (
    !isObject(data) ||
    data.version !== 1 ||
    !Array.isArray(data.rules)
  ) {
    throw new Error(
      "Invalid file format. Expected version 1 and a rules array."
    );
  }

  if (
    data.rules.length > 30
  ) {
    throw new Error(
      "A filter file must contain 0 to 30 rules."
    );
  }

  const parsed = data.rules.map((entry, index) => {
    if (!isObject(entry)) {
      throw new Error(`Invalid rule at index ${index}.`);
    }

    if (
      typeof entry.id !== "string" ||
      !/^[a-zA-Z0-9_-]{1,64}$/.test(entry.id)
    ) {
      throw new Error(`Invalid rule ID at index ${index}.`);
    }

    if (
      typeof entry.metric !== "string" ||
      !Object.prototype.hasOwnProperty.call(
        CUSTOM_METRICS,
        entry.metric
      )
    ) {
      throw new Error(
        `Unsupported metric in rule ${entry.id}.`
      );
    }

    const metric = entry.metric as CustomMetric;
    const info = CUSTOM_METRICS[metric];

    if (
      entry.operator !== "gte" &&
      entry.operator !== "lte"
    ) {
      throw new Error(
        `Invalid operator in rule ${entry.id}.`
      );
    }

    const maxValue = info.unit === "%" ? 100 : 8760;

    if (
      typeof entry.threshold !== "number" ||
      !Number.isFinite(entry.threshold) ||
      entry.threshold < 0 ||
      entry.threshold > maxValue
    ) {
      throw new Error(
        `Invalid threshold in rule ${entry.id}.`
      );
    }

    if (
      entry.enabled !== undefined &&
      typeof entry.enabled !== "boolean"
    ) {
      throw new Error(
        `Invalid enabled value in rule ${entry.id}.`
      );
    }

    const label =
      typeof entry.label === "string"
        ? entry.label
        : entry.id;

    if (label.length > 100) {
      throw new Error(
        `Invalid label in rule ${entry.id}.`
      );
    }

    return {
      id: entry.id,
      label,
      metric,
      operator: entry.operator as CustomOperator,
      threshold: entry.threshold,
      enabled: entry.enabled ?? true,
    };
  });

  const ids = parsed.map((rule) => rule.id);

  if (new Set(ids).size !== ids.length) {
    throw new Error("Duplicate rule IDs are not allowed.");
  }

  return parsed;
}

