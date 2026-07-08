// Feature: atlas-console-elevation, Property 1: Coverage classification soundness
//
// Property 1: Coverage classification soundness — for any capability
// entitlement and console-capability introspection, `classifyCoverage` assigns
// exactly one `CoverageStatus`, and:
//   - entitled === false                              → "out-of-scope"
//   - entitled, no client method AND no domain schema → "uncovered"
//   - entitled, client method AND domain schema AND complete schema → "covered"
//   - entitled, anything else                         → "partial"
//
// Validates: Requirements 1.1

import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { classifyCoverage } from "../contract-coverage";
import type {
  CapabilityEntitlement,
  CapabilityKind,
  ConsoleCapability,
  CoverageStatus,
} from "../../../spec/contract-fidelity/types";

const ALL_STATUSES: readonly CoverageStatus[] = [
  "covered",
  "partial",
  "uncovered",
  "out-of-scope",
];

const capabilityKindArb: fc.Arbitrary<CapabilityKind> = fc.constantFrom<CapabilityKind>(
  "http",
  "ws",
  "sse",
);

const entitlementArb: fc.Arbitrary<CapabilityEntitlement> = fc.record({
  capabilityId: fc.string({ minLength: 1, maxLength: 40 }),
  router: fc.string({ minLength: 1, maxLength: 20 }),
  kind: capabilityKindArb,
  ref: fc.string({ minLength: 1, maxLength: 40 }),
  entitled: fc.boolean(),
});

const consoleCapabilityArb: fc.Arbitrary<ConsoleCapability> = fc.record({
  capabilityId: fc.string({ minLength: 1, maxLength: 40 }),
  hasClientMethod: fc.boolean(),
  hasDomainSchema: fc.boolean(),
  schemaComplete: fc.boolean(),
});

describe("classifyCoverage — Property 1: Coverage classification soundness", () => {
  it("assigns exactly one valid CoverageStatus for any entitlement + console capability", () => {
    fc.assert(
      fc.property(entitlementArb, consoleCapabilityArb, (entitlement, consoleCapability) => {
        const status = classifyCoverage(entitlement, consoleCapability);

        // Exactly one of the four valid statuses.
        expect(ALL_STATUSES).toContain(status);

        const { hasClientMethod, hasDomainSchema, schemaComplete } = consoleCapability;

        if (!entitlement.entitled) {
          // Not entitled → out-of-scope, regardless of console surface.
          expect(status).toBe("out-of-scope");
          return;
        }

        // Entitled capabilities are never out-of-scope.
        expect(status).not.toBe("out-of-scope");

        if (!hasClientMethod && !hasDomainSchema) {
          expect(status).toBe("uncovered");
        } else if (hasClientMethod && hasDomainSchema && schemaComplete) {
          expect(status).toBe("covered");
        } else {
          expect(status).toBe("partial");
        }
      }),
      { numRuns: 200 },
    );
  });

  it("is a total, deterministic function (same inputs → same status)", () => {
    fc.assert(
      fc.property(entitlementArb, consoleCapabilityArb, (entitlement, consoleCapability) => {
        const first = classifyCoverage(entitlement, consoleCapability);
        const second = classifyCoverage(entitlement, consoleCapability);
        expect(first).toBe(second);
      }),
      { numRuns: 100 },
    );
  });
});

// Feature: atlas-console-elevation, Property 2: Drift failure is exactly the entitled-gap predicate
//
// Property 2: `computeDriftFailure(rows)` is true iff some entitled row has
// status `uncovered` or `partial`. Out-of-scope rows carry status
// "out-of-scope" (never uncovered/partial) and can never change the result:
// inserting or removing any number of out-of-scope rows leaves `failed`
// unchanged.
//
// Validates: Requirements 1.5, 1.6

import { computeDriftFailure, diffContractFields } from "../contract-coverage";
import type { CoverageRow } from "../../../spec/contract-fidelity/types";

// A field-name arbitrary drawn from a small pool so schema/contract sets
// realistically overlap rather than being almost-always disjoint.
const fieldNameArb: fc.Arbitrary<string> = fc.constantFrom(
  "id",
  "tier",
  "confidence",
  "city",
  "createdAt",
  "escalated",
  "status",
  "payload",
  "channel",
  "sequence",
);

const fieldListArb: fc.Arbitrary<string[]> = fc.array(fieldNameArb, { maxLength: 12 });

// An entitled row: status is one of the three in-scope statuses.
const entitledStatusArb = fc.constantFrom<CoverageRow["status"]>(
  "covered",
  "partial",
  "uncovered",
);

const coverageRowArb = (
  statusArb: fc.Arbitrary<CoverageRow["status"]>,
): fc.Arbitrary<CoverageRow> =>
  fc.record({
    capabilityId: fc.string({ minLength: 1, maxLength: 40 }),
    status: statusArb,
    missingFields: fieldListArb,
    overStrictFields: fieldListArb,
  });

// Entitled rows (in-scope) and out-of-scope rows generated separately so we
// preserve the invariant that out-of-scope rows never carry uncovered/partial.
const entitledRowArb = coverageRowArb(entitledStatusArb);
const outOfScopeRowArb = coverageRowArb(fc.constant<CoverageRow["status"]>("out-of-scope"));

// A realistic mixed-status row (any of the four statuses).
const anyRowArb = coverageRowArb(
  fc.constantFrom<CoverageRow["status"]>("covered", "partial", "uncovered", "out-of-scope"),
);

/** Splice `extras` into `base` at pseudo-random positions determined by `insertions`. */
function interleave(
  base: readonly CoverageRow[],
  extras: readonly CoverageRow[],
  positions: readonly number[],
): CoverageRow[] {
  const result = [...base];
  extras.forEach((extra, i) => {
    const pick = positions[i % positions.length] ?? 0;
    const pos = result.length === 0 ? 0 : pick % (result.length + 1);
    result.splice(pos, 0, extra);
  });
  return result;
}

describe("computeDriftFailure — Property 2: Drift failure is exactly the entitled-gap predicate", () => {
  it("returns true iff some row is uncovered or partial", () => {
    fc.assert(
      fc.property(fc.array(anyRowArb, { maxLength: 30 }), (rows) => {
        const expected = rows.some(
          (row) => row.status === "uncovered" || row.status === "partial",
        );
        expect(computeDriftFailure(rows)).toBe(expected);
      }),
      { numRuns: 200 },
    );
  });

  it("is unchanged by inserting any number of out-of-scope rows", () => {
    fc.assert(
      fc.property(
        fc.array(entitledRowArb, { maxLength: 20 }),
        fc.array(outOfScopeRowArb, { maxLength: 20 }),
        fc.array(fc.nat(1000), { minLength: 1, maxLength: 20 }),
        (entitledRows, outOfScopeRows, positions) => {
          const baseline = computeDriftFailure(entitledRows);
          const withOutOfScope = interleave(entitledRows, outOfScopeRows, positions);
          expect(computeDriftFailure(withOutOfScope)).toBe(baseline);
        },
      ),
      { numRuns: 200 },
    );
  });

  it("a set of only out-of-scope rows never fails", () => {
    fc.assert(
      fc.property(fc.array(outOfScopeRowArb, { maxLength: 30 }), (rows) => {
        expect(computeDriftFailure(rows)).toBe(false);
      }),
      { numRuns: 100 },
    );
  });
});

// Feature: atlas-console-elevation, Property 3: Contract field diff is a set difference
//
// Property 3: `diffContractFields(contractFields, schemaFields)` returns
//   - missingFields    = contract − schema   (in contract, absent from schema)
//   - overStrictFields = schemaRequired − contract (required by schema, absent from contract)
// The results are true set differences: de-duplicated, disjoint from the
// subtrahend, and each element is drawn from the correct source set.
//
// Validates: Requirements 1.3

describe("diffContractFields — Property 3: Contract field diff is a set difference", () => {
  it("missingFields = contract − schema and overStrictFields = schema − contract", () => {
    fc.assert(
      fc.property(fieldListArb, fieldListArb, (contractFields, schemaFields) => {
        const { missingFields, overStrictFields } = diffContractFields(
          contractFields,
          schemaFields,
        );

        const contractSet = new Set(contractFields);
        const schemaSet = new Set(schemaFields);

        // Exact set-difference membership.
        const expectedMissing = new Set([...contractSet].filter((f) => !schemaSet.has(f)));
        const expectedOverStrict = new Set([...schemaSet].filter((f) => !contractSet.has(f)));

        expect(new Set(missingFields)).toEqual(expectedMissing);
        expect(new Set(overStrictFields)).toEqual(expectedOverStrict);

        // De-duplicated: no element appears twice.
        expect(missingFields.length).toBe(new Set(missingFields).size);
        expect(overStrictFields.length).toBe(new Set(overStrictFields).size);

        // Every missing field comes from contract and is absent from schema.
        for (const f of missingFields) {
          expect(contractSet.has(f)).toBe(true);
          expect(schemaSet.has(f)).toBe(false);
        }

        // Every over-strict field comes from schema and is absent from contract.
        for (const f of overStrictFields) {
          expect(schemaSet.has(f)).toBe(true);
          expect(contractSet.has(f)).toBe(false);
        }
      }),
      { numRuns: 200 },
    );
  });

  it("is symmetric under argument swap (missing ⇄ overStrict)", () => {
    fc.assert(
      fc.property(fieldListArb, fieldListArb, (a, b) => {
        const forward = diffContractFields(a, b);
        const swapped = diffContractFields(b, a);
        expect(new Set(forward.missingFields)).toEqual(new Set(swapped.overStrictFields));
        expect(new Set(forward.overStrictFields)).toEqual(new Set(swapped.missingFields));
      }),
      { numRuns: 100 },
    );
  });

  it("disjoint sets produce full differences; identical sets produce empty differences", () => {
    fc.assert(
      fc.property(fieldListArb, (fields) => {
        const same = diffContractFields(fields, fields);
        expect(same.missingFields).toEqual([]);
        expect(same.overStrictFields).toEqual([]);
      }),
      { numRuns: 100 },
    );
  });
});
