/**
 * Contract Fidelity — Entitlement manifest.
 *
 * The authoritative, hand-curated list of every backend HTTP capability the
 * Atlas Console is *entitled to consume*, enumerated across `api/routers/*`
 * (agents, auth, decisions, escalations, firehose, metrics, orders, steering,
 * system, telemetry, topology) plus the gateway app-level health probes.
 *
 * This is Input #1 of the Contract Fidelity Suite (design "Contract Fidelity
 * Suite"). The suite classifies each entitled capability's Coverage_Status by
 * introspecting the Console's typed client + domain schemas; capabilities
 * marked `entitled: false` are `out-of-scope` and NEVER counted as a coverage
 * gap (Requirements 1.5, 1.6).
 *
 * Enumeration is grounded in the real routers under `api/routers/*` (their
 * route decorators and the mount prefixes in `api/main.py`) and cross-checked
 * against what the Console actually calls (`transport/synapse-api.ts`,
 * `lib/log.ts`, and the SSE/WS transports catalogued in `channels.ts`).
 *
 * `capabilityId` format — `"{router}.{METHOD}.{ref}"`, e.g.
 * `"decisions.GET./api/v1/decisions/{decision_id}"`. The HTTP method is
 * captured inside the id (per the design Data Models note) so `CapabilityKind`
 * can stay `"http" | "ws" | "sse"`.
 *
 * Only HTTP capabilities live here. WebSocket channels and SSE streams are
 * catalogued in `channels.ts` (also typed as `CapabilityEntitlement`).
 */

import type { CapabilityEntitlement } from "./types";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/**
 * A `CapabilityEntitlement` enriched with the HTTP `method` for readability.
 * The `method` is also encoded inside `capabilityId` (the canonical key the
 * suite matches on), so this stays structurally assignable to the base
 * `CapabilityEntitlement` type consumed by the classifier.
 */
export interface HttpCapabilityEntitlement extends CapabilityEntitlement {
  readonly method: HttpMethod;
}

/** Canonical id builder — keeps every capabilityId consistently shaped. */
function capabilityId(router: string, method: string, ref: string): string {
  return `${router}.${method}.${ref}`;
}

/** Small helper so each row reads as data, not boilerplate. */
function http(
  router: string,
  method: HttpMethod,
  ref: string,
  entitled: boolean,
): HttpCapabilityEntitlement {
  return {
    router,
    method,
    ref,
    capabilityId: capabilityId(router, method, ref),
    kind: "http",
    entitled,
  };
}

/**
 * Every HTTP capability the Console is entitled to consume, plus the router
 * capabilities that exist on the backend but the Console intentionally does
 * NOT consume (marked `entitled: false` → out-of-scope, so the drift suite
 * never flags them as gaps).
 */
export const HTTP_ENTITLEMENTS: readonly HttpCapabilityEntitlement[] = [
  // ── gateway (api/main.py app-level probes) ──────────────────────────────
  // Consumed by SynapseApi.health()/ready() for the Shell liveness pills.
  http("gateway", "GET", "/health", true),
  http("gateway", "GET", "/ready", true),

  // ── agents (api/routers/agents.py, prefix /api/v1/agents) ───────────────
  // GET "" resolves to the bare prefix (no trailing slash) → listAgents().
  http("agents", "GET", "/api/v1/agents", true),

  // ── auth (api/routers/auth.py, prefix /api/v1/auth) ─────────────────────
  http("auth", "POST", "/api/v1/auth/login", true), // login()
  http("auth", "POST", "/api/v1/auth/refresh", true), // refresh()
  http("auth", "POST", "/api/v1/auth/logout", true), // logout()
  http("auth", "GET", "/api/v1/auth/.well-known/jwks.json", true), // jwks.fetch()

  // ── decisions (api/routers/decisions.py, prefix /api/v1/decisions) ──────
  // POST / (trigger_decision) is an orchestrator proxy; the Console submits
  // decisions directly to the orchestrator (`submitDecision` → orchestrator
  // /api/v1/decisions), NOT through this gateway route → out-of-scope.
  http("decisions", "POST", "/api/v1/decisions", false),
  http("decisions", "GET", "/api/v1/decisions/recent", true), // listRecentDecisions()
  http("decisions", "GET", "/api/v1/decisions/{decision_id}", true), // getDecision()
  http("decisions", "POST", "/api/v1/decisions/{decision_id}/override", true), // submitOverride()

  // ── escalations (api/routers/escalations.py, prefix /api/v1/escalations) ─
  http("escalations", "GET", "/api/v1/escalations/analytics", true), // getEscalationAnalytics()

  // ── metrics (api/routers/metrics.py — NOT mounted in api/main.py) ───────
  // The metrics router is consumed only in-process by agents.py, which merges
  // the per-agent latency/rate/coverage overlay into GET /api/v1/agents. Its
  // routes are never independently exposed to the Console → out-of-scope.
  http("metrics", "GET", "/api/v1/metrics/agents", false),
  http("metrics", "GET", "/api/v1/metrics/healthz", false),

  // ── orders (api/routers/orders.py, prefix /api/v1/orders) ───────────────
  http("orders", "POST", "/api/v1/orders", true), // submitOrder()

  // ── steering (api/routers/steering.py, prefix /api/v1/steering) ─────────
  http("steering", "POST", "/api/v1/steering", true), // submitSteering()

  // ── system (api/routers/system.py, prefix /api/v1/system) ───────────────
  http("system", "GET", "/api/v1/system/posture", true), // getSystemPosture()
  http("system", "GET", "/api/v1/system/slo", true), // getSlo()
  http("system", "GET", "/api/v1/system/calibration", true), // getCalibration()

  // ── telemetry (api/routers/telemetry.py, prefix /api/v1) ────────────────
  // POST /telemetry is consumed via navigator.sendBeacon in lib/log.ts (Web
  // Vitals + error + audit_view beacons). POST /csp-report is a browser-native
  // CSP `report-uri` sink wired in nginx/CSP — no Console client method and no
  // rendered response → out-of-scope.
  http("telemetry", "POST", "/api/v1/telemetry", true),
  http("telemetry", "POST", "/api/v1/csp-report", false),

  // ── topology (api/routers/topology.py, prefix /api/v1) ──────────────────
  http("topology", "GET", "/api/v1/topology", true), // getTopology()
];

export default HTTP_ENTITLEMENTS;
