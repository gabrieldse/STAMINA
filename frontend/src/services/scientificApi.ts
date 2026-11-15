
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
  "";

export async function analyzeLunarSite(
  site: LunarSite,
  date: string,
  durationDays: number,
  filters: FilterStates,
  customRules: CustomFilterRule[]
): Promise<ScientificResult> {
  const mode = filters.analysisMode?.value === "instant" ? "instant" : "period";
  const analysisDuration = mode === "instant" ? 1 : durationDays;
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
    !Number.isInteger(analysisDuration) ||
    analysisDuration < 1 ||
    analysisDuration > 365
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
  activeFilters.analysisMode = mode;
  const activeCustomRules = customRules.filter(
    (rule) => rule.enabled
  );

  const requestBody = {
    site,
    date,
    durationDays: analysisDuration,
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
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string" ? body.detail : `Scientific API error: ${response.status}. Check the site, date and filters.`
    );
  }

  return (await response.json()) as ScientificResult;
}
