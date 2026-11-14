
import type {
  FilterStates,
  LunarSite,
  ScientificResult,
} from "../types/explorer";

import type {
  CustomFilterRule,
} from "../types/customFilters";

const API_URL =
  import.meta.env.VITE_API_URL ??
  "http://localhost:8000";

export async function analyzeLunarSite(
  site: LunarSite,
  date: string,
  durationDays: number,
  filters: FilterStates,
  customRules: CustomFilterRule[]
): Promise<ScientificResult> {
  // Validate lunar coordinates
  if (
    site.latitude == null ||
    site.longitude == null ||
    !Number.isFinite(site.latitude) ||
    !Number.isFinite(site.longitude)
  ) {
    throw new Error(
      "A georeferenced lunar site is required."
    );
  }

  // Validate analysis duration
  if (
    !Number.isInteger(durationDays) ||
    durationDays < 1 ||
    durationDays > 365
  ) {
    throw new Error("Invalid analysis duration.");
  }

  // Collect enabled standard filters
  const activeFilters = Object.fromEntries(
    Object.entries(filters)
      .filter(([, state]) => state.enabled)
      .map(([id, state]) => [
        id,
        state.value,
      ])
  );

  // Collect enabled user-defined filters
  const activeCustomRules = customRules.filter(
    (rule) => rule.enabled
  );

  const requestBody = {
    site,
    date,
    durationDays,
    filters: activeFilters,
    customFilters: activeCustomRules,
  };

  const response = await fetch(
    `${API_URL}/api/analyze`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    }
  );

  if (!response.ok) {
    throw new Error(
      `Scientific API error: ${response.status}`
    );
  }

  return (await response.json()) as ScientificResult;
}
