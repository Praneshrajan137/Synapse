/**
 * Multi-city domain (Sprint 6 — Bengaluru + Mumbai).
 *
 * City travels with every decision and scopes the digital twin, Feast
 * feature store, OSRM routing and Neo4j queries. The UI carries it as a
 * global selector in the StatusBar.
 */

export const CITIES = ["bengaluru", "mumbai"] as const;
export type City = (typeof CITIES)[number];

export const CITY_LABEL: Record<City, string> = {
  bengaluru: "Bengaluru",
  mumbai: "Mumbai",
};

/** IANA timezone — both cities share Asia/Kolkata. */
export const CITY_TIMEZONE: Record<City, string> = {
  bengaluru: "Asia/Kolkata",
  mumbai: "Asia/Kolkata",
};

export function isCity(value: string): value is City {
  return (CITIES as readonly string[]).includes(value);
}
