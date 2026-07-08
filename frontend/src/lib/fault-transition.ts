// Fault-transition resolution — the single pure function every harness fault
// and connectivity transition is routed through so each transition renders the
// correct DISTINCT Universal_State and NEVER a false-healthy screen (Req 8).
//
// This module does not decide render conditions on its own: it maps each
// FaultEvent to a `UniversalStateInput` and delegates to the inherited
// `resolveUniversalState` resolver, guaranteeing every fault classifies through
// exactly the same honesty-precedence order the rest of the Console uses
// (offline > error > degraded > loading > empty > populated).
//
// `resolveFault` is TOTAL (every FaultEvent maps to exactly one UniversalState)
// and PURE (no I/O, no clock, no randomness). Crucially it derives its result
// solely from the event, so a chained sequence renders the correct distinct
// state at every step and NEVER latches on the prior state (Req 8.6). A fault
// event (offline, an error/unavailable HTTP status, a schema violation, an
// unresolved 401 storm, or a not-live WebSocket flap) never resolves to
// `populated` — there is no false-healthy render (Req 8.1). Only genuine
// recovery events (return to online, a live WebSocket, or a successful HTTP
// response) restore the healthy `populated` state.

import {
  resolveUniversalState,
  type UniversalState,
  type UniversalStateInput,
} from "./universal-state";

/**
 * A backend fault or connectivity transition driven by the Effectiveness
 * Harness (or observed at runtime):
 *
 * - `http`            — a response carrying an HTTP status code.
 * - `schema-violation`— a payload that failed Domain_Schema validation (Req 8.2).
 * - `auth-401`        — a 401 during a 401 storm; `consecutive` is how many 401s
 *                       have occurred in the storm so far, driving the
 *                       single-flight refresh vs. session-clear decision (Req 8.3).
 * - `ws-flap`         — a WebSocket connectivity flap; `live` is whether the
 *                       socket is currently live (Req 8.4).
 * - `offline`/`online`— the browser connectivity transition (Req 8.5).
 */
export type FaultEvent =
  | { readonly kind: "http"; readonly status: number }
  | { readonly kind: "schema-violation" }
  | { readonly kind: "auth-401"; readonly consecutive: number }
  | { readonly kind: "ws-flap"; readonly live: boolean }
  | { readonly kind: "offline" }
  | { readonly kind: "online" };

/** HTTP 503 Service Unavailable — an open-breaker / brownout degradation signal. */
const HTTP_SERVICE_UNAVAILABLE = 503;
/** Below this status a response is a success/informational/redirect, not a fault. */
const HTTP_ERROR_FLOOR = 400;
/** A single-flight token refresh is attempted while the storm is at/under this
 *  count; a subsequent 401 (or refresh failure) clears the session (Req 8.3). */
const REFRESH_ATTEMPT_THRESHOLD = 2;

/** All-clear input: no adverse flag set and a non-zero item count so the resolver
 *  yields `populated` (used only for genuine recovery events). */
const HEALTHY_INPUT: UniversalStateInput = {
  isLoading: false,
  isError: false,
  isOffline: false,
  isDegraded: false,
  itemCount: 1,
};

/** Build a resolver input with a single adverse flag raised (or none, on recovery). */
function inputFor(e: FaultEvent): UniversalStateInput {
  switch (e.kind) {
    case "offline":
      // Connectivity lost — surface offline, never stale-as-live (Req 8.5).
      return { ...HEALTHY_INPUT, isOffline: true };

    case "online":
      // Connectivity restored — recover to the populated state (Req 8.5).
      return HEALTHY_INPUT;

    case "schema-violation":
      // The unvalidated payload is never rendered; take the error path (Req 8.2).
      return { ...HEALTHY_INPUT, isError: true };

    case "auth-401":
      // A single-flight token refresh is in flight while the storm is under the
      // threshold; a second 401 (or refresh failure) clears the session and
      // routes to login, surfaced here as the error state (Req 8.3).
      return e.consecutive < REFRESH_ATTEMPT_THRESHOLD
        ? { ...HEALTHY_INPUT, isLoading: true }
        : { ...HEALTHY_INPUT, isError: true };

    case "ws-flap":
      // A not-live / reconnecting socket is a brownout (degraded); a live socket
      // recovers to the populated state (Req 8.4).
      return e.live ? HEALTHY_INPUT : { ...HEALTHY_INPUT, isDegraded: true };

    case "http": {
      // 503 is an open-breaker / brownout — degraded; any other error/unavailable
      // status is the error state; a success (<400) recovers to populated (Req 8.1).
      if (e.status === HTTP_SERVICE_UNAVAILABLE) {
        return { ...HEALTHY_INPUT, isDegraded: true };
      }
      if (e.status >= HTTP_ERROR_FLOOR) {
        return { ...HEALTHY_INPUT, isError: true };
      }
      return HEALTHY_INPUT;
    }
  }
}

/**
 * Resolve the Universal_State a Surface must render after a fault or
 * connectivity transition.
 *
 * Total: every `FaultEvent` maps to exactly one `UniversalState`. The result is
 * derived solely from the event and routed through `resolveUniversalState`, so
 * it never latches on `prev` and a fault never resolves to `populated`
 * (no false-healthy render) — only recovery events do (Req 8.1, 8.6).
 *
 * `_prev` is accepted for API generality and to document that the transition is
 * applied from a prior state; the correct non-latching resolution derives solely
 * from the event and deliberately does not depend on it.
 */
export function resolveFault(_prev: UniversalState, e: FaultEvent): UniversalState {
  return resolveUniversalState(inputFor(e));
}
