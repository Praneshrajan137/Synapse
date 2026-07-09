// Posture → DegradedBanner derivation (FE-INV-035, Req 10.5).
//
// Extracted as a PURE, TOTAL function so the honesty rule — "a posture-fetch
// failure is NEVER healthy, and any brownout shedding / open breaker is named"
// — is unit- and property-testable (Property 32) away from React, and so the
// banner and any other consumer classify posture identically.

import type { SystemPosture } from "@transport/synapse-api";

/**
 * What the banner asserts about system posture:
 *   - "healthy"  → orchestrator affirmatively reports no degradation → no banner
 *   - "degraded" → brownout shedding and/or an open dependency breaker
 *   - "unknown"  → the posture fetch failed / no posture is available
 *
 * A fetch failure maps to "unknown", NEVER "healthy" — the banner never fails
 * silently green.
 */
export type PostureBannerKind = "healthy" | "degraded" | "unknown";

export interface PostureBannerState {
  readonly kind: PostureBannerKind;
  /** [city, level] pairs whose brownout level is not "NONE". */
  readonly brownout: ReadonlyArray<readonly [string, string]>;
  /** [name, state] pairs whose breaker is not "closed". */
  readonly openBreakers: ReadonlyArray<readonly [string, string]>;
}

export interface PostureBannerInput {
  /** The posture query errored (fetch failed). */
  readonly isError: boolean;
  /** The last successful posture payload, if any. */
  readonly data: SystemPosture | undefined;
}

/**
 * Derive the banner state from a posture query result.
 *
 * Precedence: a fetch error (or absent posture with no error) is "unknown" —
 * we do not know the posture, so we must not claim health. Otherwise the banner
 * is "degraded" when the orchestrator flags `degraded` OR when any brownout is
 * shedding OR any breaker is open — the presence of a named degradation drives
 * the banner even if the aggregate `degraded` flag lags. Only an affirmative,
 * fully-quiet posture is "healthy".
 */
export function derivePostureBanner(i: PostureBannerInput): PostureBannerState {
  if (i.isError || !i.data) {
    return { kind: "unknown", brownout: [], openBreakers: [] };
  }
  const brownout = Object.entries(i.data.brownout).filter(([, level]) => level !== "NONE");
  const openBreakers = Object.entries(i.data.breakers).filter(([, state]) => state !== "closed");
  const degraded = i.data.degraded || brownout.length > 0 || openBreakers.length > 0;
  return { kind: degraded ? "degraded" : "healthy", brownout, openBreakers };
}
