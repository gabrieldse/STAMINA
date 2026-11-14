
import { useRef, useState } from "react";
import type { ChangeEvent } from "react";

import {
  CUSTOM_METRICS,
} from "../../types/customFilters";

import type {
  CustomMetric,
  CustomOperator,
  CustomFilterRule,
  CustomFilterEvaluation,
} from "../../types/customFilters";

import type {
  TemperatureConfig,
} from "../../types/temperature";

import "./AdvancedFilters.css";

type Props = {
  rules: CustomFilterRule[];
  onChange: (rules: CustomFilterRule[]) => void;
  evaluations: CustomFilterEvaluation[];
  durationDays: number;
  temperature: TemperatureConfig;
};

// Configuration file: the temperature settings and, when present,
// the custom rules (same format as the upload).
function buildConfiguration(
  temperature: TemperatureConfig,
  rules: CustomFilterRule[]
) {
  return {
    version: 1,
    exportedAt: new Date().toISOString(),
    southPoleTemperatures: {
      layer: {
        season: temperature.season,
        statistic: temperature.statistic,
      },
      iceStabilityThresholdK: temperature.iceStabilityThresholdK,
      selection: {
        enabled: temperature.selectionEnabled,
        temperatureK: temperature.temperatureK,
        amplitudeK: temperature.amplitudeK,
      },
    },
    ...(rules.length > 0 ? { rules } : {}),
  };
}

function downloadJson(data: unknown, fileName: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

const metricKeys = Object.keys(
  CUSTOM_METRICS
) as CustomMetric[];

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
    data.rules.length === 0 ||
    data.rules.length > 30
  ) {
    throw new Error(
      "A filter file must contain 1 to 30 rules."
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
        ? entry.label.trim()
        : entry.id;

    if (!label || label.length > 100) {
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

export default function AdvancedFilters({
  rules,
  onChange,
  evaluations,
  durationDays,
  temperature,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [fileName, setFileName] = useState("");
  const [uploadError, setUploadError] = useState("");

  const nextId = useRef(1);

  function addRule() {
    const id = `manual-${Date.now()}-${nextId.current++}`;

    onChange([
      ...rules,
      {
        id,
        label: "New Custom Filter",
        metric: "sunlightPercent",
        operator: "gte",
        threshold: 65,
        enabled: true,
      },
    ]);
  }

  function updateRule(
    id: string,
    patch: Partial<CustomFilterRule>
  ) {
    onChange(
      rules.map((rule) =>
        rule.id === id
          ? { ...rule, ...patch }
          : rule
      )
    );
  }

  function removeRule(id: string) {
    onChange(
      rules.filter((rule) => rule.id !== id)
    );
  }

  async function handleUpload(
    event: ChangeEvent<HTMLInputElement>
  ) {
    const file = event.currentTarget.files?.[0];

    // Allow uploading the same file again.
    event.currentTarget.value = "";

    if (!file) return;

    setUploadError("");

    try {
      if (!file.name.toLowerCase().endsWith(".json")) {
        throw new Error("Please upload a JSON file.");
      }

      if (file.size > 64 * 1024) {
        throw new Error(
          "File is too large. Maximum size: 64 KB."
        );
      }

      const text = await file.text();
      const parsed: unknown = JSON.parse(text);
      const importedRules = parseFilterFile(parsed);

      // Replace existing custom rules with imported ones.
      onChange(importedRules);
      setFileName(file.name);

    } catch (error) {
      setUploadError(
        error instanceof Error
          ? error.message
          : "Unable to import filter file."
      );
    }
  }

  return (
    <section className="advanced-filters">
      <button
        type="button"
        className="advanced-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span>⚙ Advanced Options</span>
        <span>{isOpen ? "−" : "+"}</span>
      </button>

      {isOpen && (
        <div className="advanced-content">
          <p className="advanced-description">
            Add custom requirements manually or
            import a JSON filter configuration.
          </p>

          {/* CONFIGURATION EXPORT */}
          <div className="advanced-upload">
            <strong>Export Configuration</strong>

            <button
              type="button"
              className="advanced-add"
              onClick={() =>
                downloadJson(
                  buildConfiguration(temperature, rules),
                  "stamina-configuration.json"
                )
              }
            >
              ⤓ Download JSON
            </button>

            <small>
              South pole temperatures: layer, ice stability
              threshold, temperature and amplitude intervals.
              Custom rules are included when present.
            </small>
          </div>

          {/* FILE UPLOAD */}
          <div className="advanced-upload">
            <label htmlFor="stamina-filter-upload">
              <strong>Upload Custom Filter File</strong>
            </label>

            <input
              id="stamina-filter-upload"
              type="file"
              accept=".json,application/json"
              onChange={handleUpload}
            />

            <small>
              Accepted format: JSON · Maximum 64 KB
            </small>

            {fileName && (
              <p className="advanced-upload-success">
                Loaded: {fileName}
              </p>
            )}

            {uploadError && (
              <p
                className="explorer-error"
                role="alert"
              >
                {uploadError}
              </p>
            )}

            <p className="advanced-disclaimer">
              Importing a file replaces the current
              custom rules. The rules will be sent
              to the engine when you run an analysis.
            </p>
          </div>

          {/* IMPORTED OR MANUALLY CREATED RULES */}
          {rules.map((rule) => {
            const metric = CUSTOM_METRICS[rule.metric];

            const maxSlider =
              metric.unit === "%"
                ? 100
                : Math.max(
                    24,
                    durationDays * 24,
                    rule.threshold
                  );

            const evaluation = evaluations.find(
              (item) => item.id === rule.id
            );

            return (
              <div
                className="advanced-filter-card"
                key={rule.id}
              >
                <div className="advanced-filter-heading">
                  <label className="advanced-switch">
                    <input
                      type="checkbox"
                      checked={rule.enabled}
                      onChange={(e) =>
                        updateRule(rule.id, {
                          enabled: e.target.checked,
                        })
                      }
                    />
                    <span>Enabled</span>
                  </label>

                  <button
                    type="button"
                    className="advanced-remove"
                    onClick={() =>
                      removeRule(rule.id)
                    }
                    aria-label={`Remove ${rule.label}`}
                  >
                    ✕
                  </button>
                </div>

                <label className="advanced-field">
                  Filter name
                  <input
                    type="text"
                    value={rule.label}
                    onChange={(e) =>
                      updateRule(rule.id, {
                        label: e.target.value,
                      })
                    }
                  />
                </label>

                <label className="advanced-field">
                  Scientific metric
                  <select
                    value={rule.metric}
                    onChange={(e) => {
                      const key =
                        e.target.value as CustomMetric;

                      const selected =
                        CUSTOM_METRICS[key];

                      updateRule(rule.id, {
                        metric: key,
                        threshold:
                          selected.defaultThreshold,
                        operator:
                          selected.defaultOperator,
                      });
                    }}
                  >
                    {metricKeys.map((key) => (
                      <option
                        key={key}
                        value={key}
                      >
                        {CUSTOM_METRICS[key].label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="advanced-field">
                  Requirement
                  <select
                    value={rule.operator}
                    onChange={(e) =>
                      updateRule(rule.id, {
                        operator:
                          e.target.value as CustomOperator,
                      })
                    }
                  >
                    <option value="gte">
                      At least (≥)
                    </option>

                    <option value="lte">
                      At most (≤)
                    </option>
                  </select>
                </label>

                <div className="advanced-threshold">
                  <span>Threshold</span>
                  <strong>
                    {rule.threshold} {metric.unit}
                  </strong>
                </div>

                <input
                  type="range"
                  min={0}
                  max={maxSlider}
                  step={1}
                  disabled={!rule.enabled}
                  value={rule.threshold}
                  onChange={(e) =>
                    updateRule(rule.id, {
                      threshold: Number(e.target.value),
                    })
                  }
                />

                <label className="advanced-field">
                  Exact threshold
                  <input
                    type="number"
                    min={0}
                    max={metric.unit === "%" ? 100 : 8760}
                    value={rule.threshold}
                    disabled={!rule.enabled}
                    onChange={(e) => {
                      const max =
                        metric.unit === "%" ? 100 : 8760;

                      const value = Number(e.target.value);

                      updateRule(rule.id, {
                        threshold: Math.max(
                          0,
                          Math.min(max, value)
                        ),
                      });
                    }}
                  />
                </label>

                <div className="advanced-filter-status">
                  {evaluation ? (
                    <>
                      <span>
                        {evaluation.passed === true
                          ? "Requirement satisfied"
                          : evaluation.passed === false
                          ? "Requirement not satisfied"
                          : "Metric unavailable"}
                      </span>

                      <small>
                        {evaluation.actualValue == null
                          ? evaluation.message ??
                            "No calculated value"
                          : `Calculated: ${evaluation.actualValue} ${metric.unit}`}
                      </small>
                    </>
                  ) : (
                    <span>
                      {rule.enabled
                        ? "Awaiting engine analysis"
                        : "Disabled"}
                    </span>
                  )}
                </div>
              </div>
            );
          })}

          <button
            type="button"
            className="advanced-add"
            onClick={addRule}
            disabled={rules.length >= 30}
          >
            + Add Custom Filter
          </button>
        </div>
      )}
    </section>
  );
}
