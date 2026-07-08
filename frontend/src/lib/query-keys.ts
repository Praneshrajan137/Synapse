import type { City } from "@domain/primitives";

// FE-INV-016 — every metric query key carries the active city discriminator so
// switching cities invalidates stale data cleanly (Req 13.4). Using a single
// named builder makes the invariant mechanical: a metric key CANNOT be
// constructed without a city, and the city always sits at a fixed position, so
// React Query's structural cache key changes the instant the city changes.

/**
 * Build a React Query key for a city-scoped metric surface. The active `city`
 * is always embedded as a dedicated discriminator at index 1, ahead of any
 * additional cache-varying params. Extra params are normalized to a stable,
 * plain object so key equality stays structural and deterministic.
 *
 * @example
 *   metricQueryKey("system-calibration", city, { windowHours, includeSynthetic })
 *   // => ["system-calibration", "bengaluru", { includeSynthetic: false, windowHours: 168 }]
 */
export function metricQueryKey(
  scope: string,
  city: City,
  params: Readonly<Record<string, unknown>> = {},
): readonly [string, City, Record<string, unknown>] {
  // Drop `undefined` entries so an omitted optional param does not fork the
  // cache key from a param explicitly set to undefined.
  const normalized: Record<string, unknown> = {};
  for (const key of Object.keys(params)) {
    if (params[key] !== undefined) normalized[key] = params[key];
  }
  return [scope, city, normalized];
}
