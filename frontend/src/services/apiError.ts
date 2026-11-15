// FastAPI validation errors use an array of field errors, not a detail string.
export function apiErrorMessage(body: unknown, status: number): string {
  if (status === 404) return "Terrain visibility endpoint unavailable. Restart the scientific API with the updated backend.";
  const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const fields = detail.map(item => {
      const path = Array.isArray(item?.loc) ? item.loc.filter((part: unknown) => part !== "body").join(".") : "Request";
      return `${path}: ${typeof item?.msg === "string" ? item.msg : "Invalid value"}`;
    });
    const outdated = detail.some(item => item?.type === "extra_forbidden" &&
      item?.loc?.some((part: unknown) => part === "sunVisibility" || part === "earthVisibility"));
    return outdated
      ? "The scientific API is running an older version. Restart the backend to enable terrain visibility."
      : fields.join("; ") || `Scientific API error: ${status}.`;
  }
  return `Scientific API error: ${status}.`;
}
