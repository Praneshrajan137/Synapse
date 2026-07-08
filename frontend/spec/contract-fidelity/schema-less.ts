/**
 * Contract Fidelity — schema-less capability classification (Requirement 16).
 *
 * The drift gate was permanently red because every schema-less capability (one
 * the Console consumes but validates no Domain_Schema against — a no-body
 * response or an open/unconstrained shape) classified as `partial`, and a
 * partial entitled row fails the gate. A permanently-red gate corrodes the
 * honesty culture, so this module forces each schema-less capability into one
 * of two explicit, named classifications (design "M. spec/contract-fidelity —
 * schema-less classification"):
 *
 *   • `no-body-open-shape-covered` — no body (e.g. a 204) or a spec-governed /
 *     status-only shape the Console does not model; treated as covered and
 *     NEVER failing the gate for a missing response schema (Req 16.2).
 *   • `tracked-partial` — an open-shape payload the Console consumes but does
 *     not yet constrain with a Domain_Schema; recorded as a tracked partial
 *     with a named rationale, NEVER an untracked failure (Req 16.3).
 *
 * With every schema-less capability resolved, the drift gate reaches green for
 * the entitled surface (Req 16.4). A *new* schema-less capability that is
 * neither classified here nor entitled-out-of-scope is reported as
 * `unclassified` and fails the gate, forcing the classification decision
 * rather than silently absorbing it (Req 16.5).
 *
 * {@link resolveSchemaLess} is a pure, I/O-free function so it is fully
 * property-testable (task 19.2).
 */

import type {
  ConsoleCapability,
  CoverageRow,
  CoverageStatus,
  SchemaLessClass,
  SchemaLessResolution,
} from "./types";

/**
 * The authoritative classification of every schema-less capability the Console
 * consumes today. Each entry carries a named rationale so the decision is
 * explicit and auditable. Adding a new schema-less capability to the surface
 * without a matching entry here fails the gate (Req 16.5).
 *
 * Split:
 *  • `no-body-open-shape-covered` — genuinely no body (204), status-only
 *    liveness probes, or spec-governed payloads (JWKS, fire-and-forget beacon)
 *    the Console never renders a field of.
 *  • `tracked-partial` — open-shape payloads the Console does consume
 *    (an order ack, the open `metric` channel, the demo SSE stream) that are
 *    candidates for a future Domain_Schema and are tracked until then.
 */
export const SCHEMA_LESS_RESOLUTIONS: readonly SchemaLessResolution[] = [
  {
    capabilityId: "gateway.GET./health",
    classification: "no-body-open-shape-covered",
    rationale:
      "Liveness probe: the Console reads only the HTTP status for its liveness pill; the raw status object has no stable response contract to model.",
  },
  {
    capabilityId: "gateway.GET./ready",
    classification: "no-body-open-shape-covered",
    rationale:
      "Readiness probe: the Console reads only the HTTP status for its readiness pill; the raw status object has no stable response contract to model.",
  },
  {
    capabilityId: "auth.POST./api/v1/auth/logout",
    classification: "no-body-open-shape-covered",
    rationale: "Logout returns 204 No Content — there is no response body to validate.",
  },
  {
    capabilityId: "auth.GET./api/v1/auth/.well-known/jwks.json",
    classification: "no-body-open-shape-covered",
    rationale:
      "JWKS is an RFC 7517 key set consumed by the JOSE verifier; its shape is governed by the JWKS spec, not a Console Domain_Schema.",
  },
  {
    capabilityId: "telemetry.POST./api/v1/telemetry",
    classification: "no-body-open-shape-covered",
    rationale:
      "Web-Vitals / error / audit_view beacons sent via navigator.sendBeacon — fire-and-forget with no rendered response body to validate.",
  },
  {
    capabilityId: "orders.POST./api/v1/orders",
    classification: "tracked-partial",
    rationale:
      "Returns a 202 acknowledgement object the Console fires-and-forgets; the open-shape ack is unmodeled and tracked until an OrderAck Domain_Schema is warranted.",
  },
  {
    capabilityId: "firehose.WS.metric",
    classification: "tracked-partial",
    rationale:
      "Intentionally open-shape per-agent metric channel: a listener is bound but the payload passes through un-schema'd; tracked until a Metric Domain_Schema is warranted.",
  },
  {
    capabilityId: "demo.SSE./api/v1/demo/{job_id}/stream",
    classification: "tracked-partial",
    rationale:
      "Demo-theater SSE payloads are consumed via EventSource as open-shape events; tracked until a demo-stream Domain_Schema is warranted.",
  },
];

/**
 * A {@link ConsoleCapability} is schema-less iff the Console consumes it
 * (a client method / listener is bound) but validates no Domain_Schema against
 * it. Out-of-scope capabilities carry no client method, so they are never
 * schema-less and never forced through this classification.
 */
export function isSchemaLess(cap: ConsoleCapability): boolean {
  return cap.hasClientMethod && !cap.hasDomainSchema;
}

/** A coverage row for a schema-less capability, carrying its classification. */
export interface SchemaLessRow extends CoverageRow {
  /** The applied classification, or `null` when the capability is unclassified. */
  readonly schemaLess: SchemaLessClass | null;
  /** The named rationale, or `null` when unclassified. */
  readonly rationale: string | null;
}

export interface SchemaLessResolutionResult {
  /** One row per schema-less capability, with its resolved status + classification. */
  readonly rows: readonly SchemaLessRow[];
  /** True iff at least one schema-less capability is unclassified (Req 16.5). */
  readonly failed: boolean;
  /** The capabilityIds of every unclassified schema-less capability, named for the gate (Req 16.5). */
  readonly unclassified: readonly string[];
}

/**
 * Resolve every schema-less capability among `caps` against the classification
 * catalog `resolutions`, mapping each to a {@link CoverageStatus}:
 *
 *  • `no-body-open-shape-covered` → `covered` (never fails the gate — Req 16.2)
 *  • `tracked-partial`            → `partial`, but tracked with a rationale so
 *    it is excluded from the failure decision (Req 16.3)
 *  • unclassified                 → `partial` and named in `unclassified`, so a
 *    new, unresolved schema-less capability fails and is named (Req 16.5)
 *
 * Pure and I/O-free: `failed === unclassified.length > 0`.
 */
export function resolveSchemaLess(
  caps: readonly ConsoleCapability[],
  resolutions: readonly SchemaLessResolution[] = SCHEMA_LESS_RESOLUTIONS,
): SchemaLessResolutionResult {
  const byId = new Map<string, SchemaLessResolution>(
    resolutions.map((r) => [r.capabilityId, r]),
  );

  const rows: SchemaLessRow[] = [];
  const unclassified: string[] = [];

  for (const cap of caps) {
    if (!isSchemaLess(cap)) continue;

    const resolution = byId.get(cap.capabilityId);
    if (!resolution) {
      unclassified.push(cap.capabilityId);
      rows.push({
        capabilityId: cap.capabilityId,
        status: "partial",
        missingFields: [],
        overStrictFields: [],
        schemaLess: null,
        rationale: null,
      });
      continue;
    }

    const status: CoverageStatus =
      resolution.classification === "no-body-open-shape-covered" ? "covered" : "partial";
    rows.push({
      capabilityId: cap.capabilityId,
      status,
      missingFields: [],
      overStrictFields: [],
      schemaLess: resolution.classification,
      rationale: resolution.rationale,
    });
  }

  return { rows, failed: unclassified.length > 0, unclassified };
}

/**
 * The capabilityIds classified `tracked-partial`. These stay `partial` in the
 * coverage table (honest: they are not fully covered) but are excluded from the
 * drift-failure decision because they are tracked with a named rationale
 * (Req 16.3). Derived from the applied resolutions so it can never drift from
 * the catalog.
 */
export function trackedPartialIds(
  result: SchemaLessResolutionResult,
): ReadonlySet<string> {
  return new Set(
    result.rows.filter((r) => r.schemaLess === "tracked-partial").map((r) => r.capabilityId),
  );
}
