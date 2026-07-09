/**
 * Resilience_Scenarios — fault-transition state correctness (Req 8).
 *
 * These scenarios drive every backend fault and connectivity transition
 * through the Console and assert each renders the correct DISTINCT
 * Universal_State — never a false-healthy screen during a disruption. They map
 * one-to-one onto the pure `resolveFault` resolver (`src/lib/fault-transition.ts`,
 * task 9.1) so the E2E's rendered-output assertions and the model-level property
 * test (task 9.2) prove the same guarantees at both ends:
 *
 *   - 503 for a data request → the `degraded` state (open-breaker / brownout),
 *     never a populated-healthy render — Req 8.1.
 *   - a schema-violating payload → the `error` state via the schema-violation
 *     path, never the unvalidated payload — Req 8.2.
 *   - a 401 storm → a single-flight token refresh, then (on failure / a second
 *     401) session clear and a route to `/login` without a full page reload —
 *     Req 8.3.
 *   - a repeated WebSocket flap → the not-live / reconnecting (`degraded`) state
 *     through a non-color channel, recovering to `populated` when the flap ends
 *     — Req 8.4.
 *   - an offline↔online transition → the `offline` state while offline (never
 *     stale-as-live), restoring `populated` on return — Req 8.5.
 *   - a chained sequence → the correct distinct state at every step, never
 *     latching on a prior state — Req 8.6.
 *
 * Each descriptor's `faultChain` is the transport-free single source of truth
 * the `fault-transition.resilience.spec.ts` E2E drives against, so the adverse
 * conditions and their expected rendered outcomes stay named and testable
 * rather than hand-kept per test (same pattern as `firehose-stress.ts`'s
 * `rates`). The seeded Mission Control channels (`DecisionEnvelope`,
 * `DisruptionAlert`, `RoutePlan`) match the firehose scenario so a fault is
 * injected against a surface that would otherwise be populated.
 */

import { WEB_VITALS_BUDGET, type ResilienceScenario } from "./resilience-types";

/** The Mission Control channels every fault-transition scenario seeds before a
 *  fault is injected, so the healthy baseline is a populated surface. */
const MISSION_CONTROL_SCHEMA_IDS = ["DecisionEnvelope", "DisruptionAlert", "RoutePlan"] as const;

/** 503 for a data request → `degraded`, recovering to `populated` (Req 8.1). */
export const FAULT_503: ResilienceScenario = {
  id: "resilience.fault.http-503",
  kind: "fault-transition",
  seed: 80101,
  title: "503 for a data request renders degraded, not false-healthy",
  narrative:
    "The harness returns a 503 for a Mission Control data request; the Console renders the degraded (open-breaker/brownout) Universal_State — never a populated-healthy screen — and recovers to populated when the next request succeeds.",
  budget: WEB_VITALS_BUDGET,
  seedSchemaIds: [...MISSION_CONTROL_SCHEMA_IDS],
  faultChain: [
    { label: "503 for a data request", event: "http-503", expected: "degraded" },
    { label: "request succeeds again", event: "recover", expected: "populated" },
  ],
};

/** A schema-violating payload → `error` via the schema path (Req 8.2). */
export const FAULT_SCHEMA_VIOLATION: ResilienceScenario = {
  id: "resilience.fault.schema-violation",
  kind: "fault-transition",
  seed: 80202,
  title: "Schema-violating payload renders error, never the unvalidated payload",
  narrative:
    "The harness delivers a schema-violating payload on a schema-bound channel; the Console renders the error Universal_State through the schema-violation path — never the unvalidated payload — and recovers to populated once valid data resumes.",
  budget: WEB_VITALS_BUDGET,
  seedSchemaIds: [...MISSION_CONTROL_SCHEMA_IDS],
  faultChain: [
    { label: "schema-violating payload", event: "schema-violation", expected: "error" },
    { label: "valid data resumes", event: "recover", expected: "populated" },
  ],
};

/** A 401 storm → session clear + route to `/login` (Req 8.3). */
export const FAULT_401_STORM: ResilienceScenario = {
  id: "resilience.fault.auth-401-storm",
  kind: "fault-transition",
  seed: 80303,
  title: "401 storm clears the session and routes to login without a full reload",
  narrative:
    "The harness drives a 401 storm; the Console attempts a single-flight token refresh and, when it fails or a second 401 arrives, clears the session and routes to /login without a full page reload.",
  budget: WEB_VITALS_BUDGET,
  seedSchemaIds: [...MISSION_CONTROL_SCHEMA_IDS],
  faultChain: [{ label: "401 storm exhausts refresh", event: "auth-401-storm", expected: "login" }],
};

/** A repeated WebSocket flap → not-live/reconnecting (`degraded`), recovering (Req 8.4). */
export const FAULT_WS_FLAP: ResilienceScenario = {
  id: "resilience.fault.ws-flap",
  kind: "fault-transition",
  seed: 80404,
  title: "WebSocket flap renders not-live/reconnecting and recovers to live",
  narrative:
    "The harness flaps the WebSocket connection repeatedly; the Console renders the not-live/reconnecting (degraded) state through a non-color channel and recovers to the live populated state when the flap ends.",
  budget: WEB_VITALS_BUDGET,
  seedSchemaIds: [...MISSION_CONTROL_SCHEMA_IDS],
  faultChain: [
    { label: "socket flaps not-live", event: "ws-flap", expected: "degraded" },
    { label: "socket returns live", event: "recover", expected: "populated" },
  ],
};

/** An offline↔online transition → `offline` then restored `populated` (Req 8.5). */
export const FAULT_OFFLINE_ONLINE: ResilienceScenario = {
  id: "resilience.fault.offline-online",
  kind: "fault-transition",
  seed: 80505,
  title: "Offline↔online renders offline (never stale-as-live) and restores populated",
  narrative:
    "The harness transitions the browser offline and back online; the Console renders the offline Universal_State while offline (never presenting stale data as live) and restores the populated state on return to online.",
  budget: WEB_VITALS_BUDGET,
  seedSchemaIds: [...MISSION_CONTROL_SCHEMA_IDS],
  faultChain: [
    { label: "browser goes offline", event: "offline", expected: "offline" },
    { label: "browser returns online", event: "online", expected: "populated" },
  ],
};

/**
 * A chained sequence of transitions proving the Console renders the correct
 * DISTINCT state at every step and NEVER latches on a prior state (Req 8.6).
 * The chain deliberately alternates fault kinds and recoveries so a latched
 * (stuck) state would be caught: offline → online → 503 → recover →
 * schema-violation → recover → ws-flap → recover.
 */
export const FAULT_CHAIN: ResilienceScenario = {
  id: "resilience.fault.chain",
  kind: "fault-transition",
  seed: 80606,
  title: "Chained fault/connectivity transitions render distinct states without latching",
  narrative:
    "The harness chains offline→online→503→recover→schema-violation→recover→ws-flap→recover; the Console renders the correct distinct Universal_State at every step and never latches on a prior state.",
  budget: WEB_VITALS_BUDGET,
  seedSchemaIds: [...MISSION_CONTROL_SCHEMA_IDS],
  faultChain: [
    { label: "browser goes offline", event: "offline", expected: "offline" },
    { label: "browser returns online", event: "online", expected: "populated" },
    { label: "503 for a data request", event: "http-503", expected: "degraded" },
    { label: "request succeeds again", event: "recover", expected: "populated" },
    { label: "schema-violating payload", event: "schema-violation", expected: "error" },
    { label: "valid data resumes", event: "recover", expected: "populated" },
    { label: "socket flaps not-live", event: "ws-flap", expected: "degraded" },
    { label: "socket returns live", event: "recover", expected: "populated" },
  ],
};

/** Every fault-transition Resilience_Scenario (Req 8.1–8.6), ordered by requirement. */
export const FAULT_TRANSITIONS: readonly ResilienceScenario[] = [
  FAULT_503,
  FAULT_SCHEMA_VIOLATION,
  FAULT_401_STORM,
  FAULT_WS_FLAP,
  FAULT_OFFLINE_ONLINE,
  FAULT_CHAIN,
];
