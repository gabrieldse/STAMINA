
import siteData from "../data/landing-sites.json";

// Historic and candidate landing sites (src/data/landing-sites.json).
// Latitude/longitude in degrees, east-positive.
export type LandingSite = {
  id: string;
  name: string;
  program: "Apollo" | "Artemis";
  color: string;
  latitude: number;
  longitude: number;
  site: string;
  landingDate?: string;
  terrain: string;
  goal: string;
  facts: [string, string][];
  story: string;
  // Official region outline as [lat, lon] corners (Artemis, when known).
  region?: [number, number][];
};

export const LANDING_SITES = siteData.sites as LandingSite[];

// The temperature map covers 80°S to the pole.
export const MAP_LATITUDE_LIMIT = -80;

// Sites the comparison grid can show (switched on, inside the 80°S map)
export type CompareSite = { id: string; name: string };
export type VisiblePolarSite = CompareSite & { latitude: number; longitude: number };
export type InitialMapSite = { latitude: number; longitude: number; name: string };
export const COMPARE_LIMIT = 6;

export function isOnPolarMap(site: LandingSite) {
  return site.latitude <= MAP_LATITUDE_LIMIT;
}

export function formatLatLon(latitude: number, longitude: number) {
  const lat = `${Math.abs(latitude).toFixed(2)}°${latitude < 0 ? "S" : "N"}`;
  const lon = `${Math.abs(longitude).toFixed(2)}°${longitude < 0 ? "W" : "E"}`;
  return `${lat}, ${lon}`;
}
