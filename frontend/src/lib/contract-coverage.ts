// Contract coverage classification — pure functions backing the Contract
// Fidelity Suite (Req 1). These decide, without any I/O, how the Console's
// client surface (typed client methods + domain Zod schemas) covers each
// backend capability the Console is entitled to consume, and whether the
// resulting drift report should fail the check.
//
// Every function here is referentially transparent: no Date.now, no
// randomness, no network/disk access. This keeps them unit- and
// property-testable independent of the harness that gathers their inputs.

import type {
  CapabilityEntitlement,
  ConsoleCapability,
  CoverageRow,
  CoverageStatus,
} from "../../spec/contract-fidelity/types";

/**
 * Classify a single capability into exactly one {@link CoverageStatus}.
 *
 * Semantics (design "Coverage classification"):
 * - `out-of-scope` — the Console is not entitled to consume the capability
 *   (`entitlement.entitled === false`); never counted as a coverage gap.
 * - `covered`      — a typed client method exists AND a domain schema exists
 *   AND that schema is complete (no required contract field missing).
 * - `uncovered`    — neither a typed client method nor a domain schema exists.
 * - `partial`      — anything in between: a client method exists but the
 *   response schema is incomplete or the channel/stream is only partially
 *   modeled (e.g. a method without a schema, or a schema without a method).
 *
 * The four branches are mutually exclusive and total, so every capability
 * receives exactly one status.
 */
export function classifyCoverage(
  entitlement: CapabilityEntitlement,
  consoleCapability: ConsoleCapability,
): CoverageStatus {
  if (!entitlement.entitled) {
    return "out-of-scope";
  }

  const { hasClientMethod, hasDomainSchema, schemaComplete } = consoleCapability;

  if (hasClientMethod && hasDomainSchema && schemaComplete) {
    return "covered";
  }

  if (!hasClientMethod && !hasDomainSchema) {
    return "uncovered";
  }

  return "partial";
}

/** Result of comparing the backend contract's fields against a domain schema. */
export interface ContractFieldDiff {
  /** Fields present in the contract but absent from the Console schema. */
  readonly missingFields: string[];
  /** Fields the Console schema requires that are absent from the contract. */
  readonly overStrictFields: string[];
}

/**
 * Diff the backend contract's field set against a domain schema's (required)
 * field set as a pair of set differences (design Property 3):
 *
 * - `missingFields`    = contractFields − schemaFields
 * - `overStrictFields` = schemaFields   − contractFields
 *
 * `schemaFields` is the schema's required field set: a field the schema
 * requires but the contract does not provide is over-strict drift, while a
 * contract field the schema omits is missing-field drift. Output preserves
 * first-occurrence order from its source set and is de-duplicated so the diff
 * is a true set difference.
 */
export function diffContractFields(
  contractFields: readonly string[],
  schemaFields: readonly string[],
): ContractFieldDiff {
  const schemaSet = new Set(schemaFields);
  const contractSet = new Set(contractFields);

  const missingFields = dedupe(contractFields.filter((field) => !schemaSet.has(field)));
  const overStrictFields = dedupe(schemaFields.filter((field) => !contractSet.has(field)));

  return { missingFields, overStrictFields };
}

/**
 * Compute the drift report's `failed` flag (design Property 2, Req 1.6).
 *
 * `failed` is true iff some entitled row is `uncovered` or `partial`.
 * Out-of-scope rows carry status `out-of-scope` (never `uncovered`/`partial`),
 * so they can never change the result — an out-of-scope capability is never a
 * coverage gap.
 */
export function computeDriftFailure(rows: readonly CoverageRow[]): boolean {
  return rows.some((row) => row.status === "uncovered" || row.status === "partial");
}

/** Return a copy of `values` with duplicates removed, preserving first order. */
function dedupe(values: readonly string[]): string[] {
  return [...new Set(values)];
}
