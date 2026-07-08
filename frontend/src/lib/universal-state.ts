// Universal-state resolver — the single pure function every data-bearing
// Surface consumes to decide which of the six canonical render conditions to
// show (Req 10.1). Centralizing the decision here guarantees every surface
// classifies loading/empty/error/degraded/offline/populated identically and
// that "no data yet" (empty) is never confused with "failed to load" (error)
// (Req 10.8).
//
// The resolver is TOTAL (every possible input maps to exactly one state) and
// PURE (no I/O, no clock, no randomness), which is what lets Property 30 verify
// totality and distinctness across all inputs.

/** The six canonical render conditions a data-bearing Surface must define. */
export type UniversalState =
  | "loading"
  | "empty"
  | "error"
  | "degraded"
  | "offline"
  | "populated";

export interface UniversalStateInput {
  readonly isLoading: boolean;
  readonly isError: boolean;
  readonly isOffline: boolean;
  readonly isDegraded: boolean; // posture brownout / open breaker
  readonly itemCount: number;
}

/**
 * Resolve the render condition for a data-bearing Surface.
 *
 * Priority order is fixed and exhaustive:
 *   offline > error > degraded > loading > empty > populated
 *
 * The order encodes honesty precedence: a dropped connection or a failed
 * request must never be masked by stale/degraded/loading affordances, and a
 * degraded posture is surfaced ahead of an in-flight refresh. Once none of the
 * higher-priority conditions hold, an item count of 0 is `empty` (distinct from
 * `error`, per Req 10.8) and any positive count is `populated`.
 */
export function resolveUniversalState(i: UniversalStateInput): UniversalState {
  if (i.isOffline) return "offline";
  if (i.isError) return "error";
  if (i.isDegraded) return "degraded";
  if (i.isLoading) return "loading";
  if (i.itemCount === 0) return "empty";
  return "populated";
}
