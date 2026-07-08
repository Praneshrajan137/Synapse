/**
 * Effectiveness_Harness — schema-bound MSW handler set (Req 1.1, 1.4, 1.5, 1.6).
 *
 * This module builds the full set of Mock Service Worker HTTP handlers the
 * browser worker (`./browser-worker.ts`) registers. Every handler's response
 * body is derived from and validated against the same `Domain_Schema` the
 * Atlas_Console applies at runtime, via the shared schema-bound fixture factory
 * (`./fixture-factory.ts` + `./schema-registry.ts`), so a passing harness test
 * can never be built on a mock that misrepresents the real contract.
 *
 * Design "B. Harness — MSW browser worker + stream driver" requires the worker
 * to **reuse and extend** the existing `src/test/msw-handlers.ts` `handlers`
 * array rather than duplicating it. That reuse happens in `browser-worker.ts`
 * where these effectiveness handlers are prepended to the base handlers
 * (first-match-wins ⇒ these populated fixtures supersede the base
 * empty/minimal ones, while the base `/health`, `/ready`, and `/api/v1/agents`
 * handlers are reused unchanged).
 *
 * Every Backend_Contract HTTP path the Console issues (enumerated from
 * `transport/synapse-api.ts`, `transport/jwks.ts`, and the demo-theater raw
 * fetches) is intercepted here so no request reaches a live endpoint (Req 1.1,
 * 1.5). The scripted WebSocket/SSE streams for real-time channels are the
 * stream driver's responsibility (task 2.2) and are intentionally out of scope
 * for this HTTP handler set.
 */

import { http, HttpResponse, type RequestHandler } from "msw";

import { buildFixture } from "./fixture-factory";
import type { SchemaId } from "./schema-registry";

// ─────────────────────────────────────────────────────────────────────────
// Backend_Contract HTTP surface — enumerated capability descriptors
// ─────────────────────────────────────────────────────────────────────────

type HttpMethod = "get" | "post";

/**
 * One Backend_Contract HTTP capability the harness serves. A `schemaId`
 * resolves to a `Domain_Schema` in the shared registry (the body is generated
 * from and validated against it); a `null` `schemaId` is a schema-less
 * capability (no response body or an open/ack shape) whose `staticBody` is
 * served verbatim.
 */
interface HandlerSpec {
  /** Stable capability id, e.g. `decisions.GET./api/v1/decisions/recent`. */
  readonly capabilityId: string;
  /** The Surface(s) this capability feeds toward its populated state (Req 1.4). */
  readonly surfaces: readonly Surface[];
  readonly method: HttpMethod;
  /** Matches the request URL; ordered most-specific-first (first match wins). */
  readonly pattern: RegExp;
  /** Bound Domain_Schema id, or `null` for a schema-less capability (Req 2.4). */
  readonly schemaId: SchemaId | null;
  /** Verbatim body for a schema-less capability. Ignored when `schemaId` set. */
  readonly staticBody?: unknown;
  /** Response status; defaults to 200 (use 204 for no-content acks). */
  readonly status?: number;
}

/** The Console's top-level Surfaces (Req 1.4 surface list). */
export type Surface =
  | "mission-control"
  | "decision-theater"
  | "override-cockpit"
  | "audit-vault"
  | "operations"
  | "steering"
  | "twin-lab"
  | "council-theater"
  | "agent-council"
  | "live-markets"
  | "ingress"
  | "auth"
  | "demo-theater";

/** Every Surface in the Req 1.4 surface list (used to assert full coverage). */
export const ALL_SURFACES: readonly Surface[] = [
  "mission-control",
  "decision-theater",
  "override-cockpit",
  "audit-vault",
  "operations",
  "steering",
  "twin-lab",
  "council-theater",
  "agent-council",
  "live-markets",
  "ingress",
  "auth",
  "demo-theater",
];

/**
 * The effectiveness capability descriptors, ordered most-specific-path-first so
 * MSW's first-match-wins resolution is deterministic (e.g. the `/override` and
 * `/recent` sub-paths precede the bare `/api/v1/decisions/:id`).
 *
 * `/health`, `/ready`, and `/api/v1/agents` are intentionally omitted here —
 * the base `src/test/msw-handlers.ts` handlers already serve them at a
 * populated state and are reused unchanged (design "reuse and extend").
 */
export const EFFECTIVENESS_HANDLER_SPECS: readonly HandlerSpec[] = [
  // ── Auth (drives the auth Surface + the app-wide token lifecycle) ────────
  {
    capabilityId: "auth.POST./api/v1/auth/login",
    surfaces: ["auth"],
    method: "post",
    pattern: /\/api\/v1\/auth\/login(?:\?|$)/,
    schemaId: "LoginResponse",
  },
  {
    capabilityId: "auth.POST./api/v1/auth/refresh",
    surfaces: ["auth"],
    method: "post",
    pattern: /\/api\/v1\/auth\/refresh(?:\?|$)/,
    schemaId: "RefreshResponse",
  },
  {
    capabilityId: "auth.POST./api/v1/auth/logout",
    surfaces: ["auth"],
    method: "post",
    pattern: /\/api\/v1\/auth\/logout(?:\?|$)/,
    schemaId: null,
    status: 204,
  },
  {
    capabilityId: "auth.GET./api/v1/auth/.well-known/jwks.json",
    surfaces: ["auth"],
    method: "get",
    pattern: /\/api\/v1\/auth\/\.well-known\/jwks\.json(?:\?|$)/,
    schemaId: null,
    // JWKS is advisory and schema-less in the domain registry; a single RSA
    // key entry keeps `knownKids` non-empty without asserting a signature.
    staticBody: {
      keys: [{ kty: "RSA", kid: "harness-kid-1", use: "sig", alg: "RS256", n: "harness", e: "AQAB" }],
    },
  },

  // ── Decisions (Decision Theater / Override Cockpit / Audit Vault) ────────
  {
    capabilityId: "decisions.GET./api/v1/decisions/recent",
    surfaces: ["decision-theater", "audit-vault", "mission-control"],
    method: "get",
    pattern: /\/api\/v1\/decisions\/recent(?:\?|$)/,
    schemaId: "AuditListResponse",
  },
  {
    capabilityId: "decisions.POST./api/v1/decisions/:id/override",
    surfaces: ["override-cockpit"],
    method: "post",
    pattern: /\/api\/v1\/decisions\/[^/?]+\/override(?:\?|$)/,
    schemaId: "OverrideApiResponse",
  },
  {
    capabilityId: "decisions.GET./api/v1/decisions/:id",
    surfaces: ["decision-theater", "audit-vault"],
    method: "get",
    // uuid-like id; ordered after `/recent` so "recent" never matches here.
    pattern: /\/api\/v1\/decisions\/[0-9a-fA-F][0-9a-fA-F-]{7,}(?:\?|$)/,
    schemaId: "DecisionDetailResponse",
  },
  {
    capabilityId: "decisions.POST./api/v1/decisions",
    surfaces: ["ingress"],
    method: "post",
    pattern: /\/api\/v1\/decisions(?:\?|$)/,
    schemaId: "ConsensusDecision",
  },

  // ── Topology (Mission Control living map / Twin Lab) ─────────────────────
  {
    capabilityId: "topology.GET./api/v1/topology",
    surfaces: ["mission-control", "twin-lab", "live-markets"],
    method: "get",
    pattern: /\/api\/v1\/topology(?:\?|$)/,
    schemaId: "TopologyResponse",
  },

  // ── System posture + Operations / Standing Watch ─────────────────────────
  {
    capabilityId: "system.GET./api/v1/system/posture",
    surfaces: ["mission-control", "operations"],
    method: "get",
    pattern: /\/api\/v1\/system\/posture(?:\?|$)/,
    schemaId: "SystemPosture",
  },
  {
    capabilityId: "system.GET./api/v1/system/slo",
    surfaces: ["operations"],
    method: "get",
    pattern: /\/api\/v1\/system\/slo(?:\?|$)/,
    schemaId: "SloResponse",
  },
  {
    capabilityId: "system.GET./api/v1/system/calibration",
    surfaces: ["operations", "council-theater", "agent-council"],
    method: "get",
    pattern: /\/api\/v1\/system\/calibration(?:\?|$)/,
    schemaId: "CalibrationResponse",
  },
  {
    capabilityId: "escalations.GET./api/v1/escalations/analytics",
    surfaces: ["operations", "override-cockpit"],
    method: "get",
    pattern: /\/api\/v1\/escalations\/analytics(?:\?|$)/,
    schemaId: "EscalationAnalytics",
  },

  // ── Steering (write-ack) ─────────────────────────────────────────────────
  {
    capabilityId: "steering.POST./api/v1/steering",
    surfaces: ["steering"],
    method: "post",
    pattern: /\/api\/v1\/steering(?:\?|$)/,
    schemaId: "SteeringResponse",
  },

  // ── Orders ingress (outbox-backed, 202-style ack — schema-less) ──────────
  {
    capabilityId: "orders.POST./api/v1/orders",
    surfaces: ["ingress"],
    method: "post",
    pattern: /\/api\/v1\/orders(?:\?|$)/,
    schemaId: null,
    status: 202,
    staticBody: { status: "accepted", order_id: "harness-order-1", outbox_id: "harness-outbox-1" },
  },

  // ── Digital Twin Monte-Carlo simulate (council-theater / twin-lab) ───────
  {
    capabilityId: "twin.POST./simulate",
    surfaces: ["twin-lab", "council-theater"],
    method: "post",
    pattern: /\/simulate(?:\?|$)/,
    schemaId: "TwinState",
  },

  // ── Demo Theater HTTP surface (the SSE stream is served by task 2.2) ─────
  {
    capabilityId: "demo.POST./api/v1/demo/run",
    surfaces: ["demo-theater"],
    method: "post",
    pattern: /\/api\/v1\/demo\/run(?:\?|$)/,
    schemaId: null,
    staticBody: { job_id: "harness-demo-job-1" },
  },
  {
    capabilityId: "demo.POST./api/v1/demo/:id/cancel",
    surfaces: ["demo-theater"],
    method: "post",
    pattern: /\/api\/v1\/demo\/[^/?]+\/cancel(?:\?|$)/,
    schemaId: null,
    status: 204,
  },
  {
    capabilityId: "demo.GET./api/v1/demo/:id/artifact/:segment",
    surfaces: ["demo-theater"],
    method: "get",
    pattern: /\/api\/v1\/demo\/[^/?]+\/artifact\/[^/?]+(?:\?|$)/,
    schemaId: null,
    staticBody: { segment: "summary", artifact: { generated_by: "effectiveness-harness" } },
  },
];

// ─────────────────────────────────────────────────────────────────────────
// Handler construction
// ─────────────────────────────────────────────────────────────────────────

/**
 * Build the effectiveness MSW handlers for a fixed `seed`. Each schema-bound
 * capability's body is generated from its `Domain_Schema` and re-validated
 * through that same schema at build time (via {@link buildFixture}); a fixture
 * that fails validation throws `FixtureSchemaError` naming the fixture and
 * schema, so contract drift is caught mechanically (Req 2.1, 2.3).
 *
 * The `seed` is the only entropy source (Req 1.3): each capability draws from a
 * capability-scoped derivation of the base seed, so a given `(seed, capability)`
 * pair yields a byte-identical body on every run while distinct capabilities
 * still get distinct data.
 */
export function buildEffectivenessHandlers(seed: number): RequestHandler[] {
  return EFFECTIVENESS_HANDLER_SPECS.map((spec) => {
    const status = spec.status ?? 200;
    const body = resolveBody(spec, seed);
    const responder = () =>
      status === 204
        ? new HttpResponse(null, { status: 204 })
        : HttpResponse.json(body as Parameters<typeof HttpResponse.json>[0], { status });
    return spec.method === "get"
      ? http.get(spec.pattern, responder)
      : http.post(spec.pattern, responder);
  });
}

/** Resolve a capability's response body: schema-bound fixture or static body. */
function resolveBody(spec: HandlerSpec, seed: number): unknown {
  if (spec.schemaId === null) {
    return spec.staticBody ?? {};
  }
  const result = buildFixture({
    capabilityId: spec.capabilityId,
    schemaId: spec.schemaId,
    seed: capabilitySeed(seed, spec.capabilityId),
  });
  return result.body;
}

/**
 * Derive a deterministic, capability-scoped seed from the base seed so distinct
 * capabilities get distinct data while any given `(seed, capability)` pair is
 * fully reproducible (FNV-1a over the capability id, mixed with the base seed).
 */
export function capabilitySeed(base: number, capabilityId: string): number {
  let h = (base >>> 0) ^ 0x811c9dc5;
  for (let i = 0; i < capabilityId.length; i += 1) {
    h = Math.imul(h ^ capabilityId.charCodeAt(i), 0x01000193) >>> 0;
  }
  return h >>> 0;
}

// ─────────────────────────────────────────────────────────────────────────
// Backend_Contract path classification (Req 1.5, 1.6)
// ─────────────────────────────────────────────────────────────────────────

/**
 * True iff `pathname` is a Backend_Contract HTTP path the harness is expected to
 * serve a fixture for. Used by the browser worker's unhandled-request guard: an
 * unhandled request matching this predicate fails the test naming the path
 * (Req 1.6), while same-origin static assets (the app's own JS/CSS/fonts/data)
 * are bypassed.
 *
 * The demo SSE stream (`/api/v1/demo/:id/stream`) and the WebSocket firehose
 * (`/ws/...`) are excluded here because they are served by the scripted stream
 * driver (task 2.2), not by an HTTP fixture.
 */
export function isBackendContractPath(pathname: string): boolean {
  if (/\/api\/v1\/demo\/[^/]+\/stream$/.test(pathname)) return false; // SSE (task 2.2)
  if (pathname.startsWith("/ws/")) return false; // WebSocket (task 2.2)
  return (
    pathname.startsWith("/api/") ||
    pathname === "/health" ||
    pathname === "/ready" ||
    pathname === "/simulate"
  );
}

/**
 * Map of every Surface to the capability ids that drive it toward a populated
 * Universal_State, for the harness coverage report (Req 1.4). Includes the
 * base-handler capabilities (`/api/v1/agents`) reused from
 * `src/test/msw-handlers.ts`.
 */
export function surfaceCoverage(): Readonly<Record<Surface, readonly string[]>> {
  const coverage = Object.fromEntries(ALL_SURFACES.map((s) => [s, [] as string[]])) as Record<
    Surface,
    string[]
  >;
  // Base handlers reused from src/test/msw-handlers.ts.
  coverage["mission-control"].push("agents.GET./api/v1/agents");
  coverage["council-theater"].push("agents.GET./api/v1/agents");
  coverage["agent-council"].push("agents.GET./api/v1/agents");
  for (const spec of EFFECTIVENESS_HANDLER_SPECS) {
    for (const surface of spec.surfaces) {
      coverage[surface].push(spec.capabilityId);
    }
  }
  return coverage;
}

/** Every Surface with no seeded capability — must be empty to satisfy Req 1.4. */
export function uncoveredSurfaces(): readonly Surface[] {
  const coverage = surfaceCoverage();
  return ALL_SURFACES.filter((s) => coverage[s].length === 0);
}
