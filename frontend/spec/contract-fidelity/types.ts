/**
 * Contract Fidelity data models.
 *
 * Canonical types for the Contract Fidelity Suite that compares backend
 * capabilities the Console is entitled to consume against the Console's actual
 * client surface (client methods + domain schemas), producing a drift report.
 *
 * These types mirror the design "Data Models > Contract Fidelity Models"
 * section exactly and back Requirements 1.1 and 1.5.
 */

export type CapabilityKind = "http" | "ws" | "sse";
export type CoverageStatus = "covered" | "partial" | "uncovered" | "out-of-scope";

export interface CapabilityEntitlement {
  readonly capabilityId: string; // e.g. "decisions.GET./api/v1/decisions/{id}"
  readonly router: string; // "decisions"
  readonly kind: CapabilityKind;
  readonly ref: string; // path | channel | stream name
  readonly entitled: boolean; // false → out-of-scope
}

export interface ConsoleCapability {
  readonly capabilityId: string;
  readonly hasClientMethod: boolean;
  readonly hasDomainSchema: boolean;
  readonly schemaComplete: boolean; // no required contract field missing
}

export interface CoverageRow {
  readonly capabilityId: string;
  readonly status: CoverageStatus;
  readonly missingFields: readonly string[]; // in contract, absent from schema
  readonly overStrictFields: readonly string[]; // required by schema, absent from contract
}

/**
 * The two honest classifications a schema-less Backend_Contract capability (one
 * with no response body or an open/unconstrained shape) resolves to, closing
 * the permanently-red drift gate (Requirement 16.1):
 *
 *  • `no-body-open-shape-covered` — the capability genuinely returns no body
 *    (e.g. a 204) or a spec-governed / status-only shape the Console does not
 *    model as a Domain_Schema; treated as covered, never failing the gate for
 *    a missing response schema (Req 16.2).
 *  • `tracked-partial` — the capability carries an open-shape payload the
 *    Console consumes but does not (yet) constrain with a Domain_Schema;
 *    recorded as a tracked partial with a named rationale, never left as an
 *    untracked failure (Req 16.3).
 */
export type SchemaLessClass = "no-body-open-shape-covered" | "tracked-partial";

/** An explicit, named classification decision for one schema-less capability. */
export interface SchemaLessResolution {
  readonly capabilityId: string;
  readonly classification: SchemaLessClass;
  /** Human-readable justification — required so a `tracked-partial` is tracked, not silent (Req 16.3). */
  readonly rationale: string;
}

export interface DriftReport {
  readonly generatedAt: string;
  readonly rows: readonly CoverageRow[];
  readonly backendGaps: readonly { kind: "agent-state" | "oversight" | "uplift"; name: string }[];
  /** The applied schema-less classifications, surfaced in the report (Req 16.1, 16.3). */
  readonly schemaLess: readonly SchemaLessResolution[];
  /** Schema-less capabilities that are neither classified nor out-of-scope (Req 16.5). */
  readonly unclassifiedSchemaLess: readonly string[];
  readonly failed: boolean; // any entitled row uncovered/partial (excluding tracked schema-less)
}
