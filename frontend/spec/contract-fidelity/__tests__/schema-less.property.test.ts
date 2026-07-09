// Feature: atlas-console-effectiveness, Property 19: A schema-less capability resolved to either classification never leaves an untracked failure, and an unclassified non-entitled schema-less capability fails the gate and is named
//
// Property 19: Schema-less classification leaves no untracked failure.
//
// *For any* schema-less capability resolved to either classification
// ("no-body/open-shape ⇒ covered" or "tracked-partial"), the drift suite
// records it without an untracked failure; and *for any* new schema-less
// capability that is neither classified nor entitled-out-of-scope, the suite
// fails and names it.
//
// Validates: Requirements 16.2, 16.3, 16.5

import fc from "fast-check";
import { describe, expect, it } from "vitest";
import {
  isSchemaLess,
  resolveSchemaLess,
  trackedPartialIds,
  SCHEMA_LESS_RESOLUTIONS,
} from "../schema-less";
import type {
  ConsoleCapability,
  SchemaLessClass,
  SchemaLessResolution,
} from "../types";

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

const schemaLessClassArb: fc.Arbitrary<SchemaLessClass> =
  fc.constantFrom<SchemaLessClass>("no-body-open-shape-covered", "tracked-partial");

// A capabilityId arbitrary drawn from a small pool so generated capabilities
// realistically collide with (and diverge from) the resolution catalog rather
// than being almost-always novel strings.
const capabilityIdArb: fc.Arbitrary<string> = fc.oneof(
  // Ids that exist in the authoritative catalog.
  fc.constantFrom(...SCHEMA_LESS_RESOLUTIONS.map((r) => r.capabilityId)),
  // Novel ids that are NOT in the catalog (prefixed to guarantee no overlap).
  fc.string({ minLength: 1, maxLength: 24 }).map((s) => `novel.${s}`),
);

// A ConsoleCapability that is guaranteed schema-less: consumed by the Console
// (client method bound) but validating no Domain_Schema.
const schemaLessCapabilityArb: fc.Arbitrary<ConsoleCapability> = fc.record({
  capabilityId: capabilityIdArb,
  hasClientMethod: fc.constant(true),
  hasDomainSchema: fc.constant(false),
  schemaComplete: fc.boolean(),
});

// An arbitrary ConsoleCapability (any surface combination) so we exercise the
// isSchemaLess filter alongside genuinely schema-less rows.
const anyCapabilityArb: fc.Arbitrary<ConsoleCapability> = fc.record({
  capabilityId: capabilityIdArb,
  hasClientMethod: fc.boolean(),
  hasDomainSchema: fc.boolean(),
  schemaComplete: fc.boolean(),
});

// A resolution catalog arbitrary: a de-duplicated set of classifications keyed
// by capabilityId, so we can test resolution against arbitrary catalogs.
const resolutionArb: fc.Arbitrary<SchemaLessResolution> = fc.record({
  capabilityId: capabilityIdArb,
  classification: schemaLessClassArb,
  rationale: fc.string({ minLength: 1, maxLength: 60 }),
});

const catalogArb: fc.Arbitrary<readonly SchemaLessResolution[]> = fc
  .array(resolutionArb, { maxLength: 12 })
  .map((rs) => {
    // De-duplicate by capabilityId (last wins) — a real catalog has one entry
    // per capability, matching the Map construction in resolveSchemaLess.
    const byId = new Map<string, SchemaLessResolution>();
    for (const r of rs) byId.set(r.capabilityId, r);
    return [...byId.values()];
  });

// ---------------------------------------------------------------------------
// Property 19
// ---------------------------------------------------------------------------

describe("resolveSchemaLess — Property 19: schema-less classification leaves no untracked failure", () => {
  it("a resolved schema-less capability (either classification) never leaves an untracked failure", () => {
    fc.assert(
      fc.property(
        fc.array(anyCapabilityArb, { maxLength: 20 }),
        catalogArb,
        (caps, catalog) => {
          const result = resolveSchemaLess(caps, catalog);
          const byId = new Map(catalog.map((r) => [r.capabilityId, r]));
          const tracked = trackedPartialIds(result);

          // Exactly the schema-less capabilities are represented as rows.
          const schemaLessCaps = caps.filter(isSchemaLess);
          expect(result.rows.length).toBe(schemaLessCaps.length);

          for (const row of result.rows) {
            const resolution = byId.get(row.capabilityId);

            if (resolution) {
              // A resolved row carries its classification + a named rationale,
              // and is NEVER named as an untracked failure (Req 16.2, 16.3).
              expect(row.schemaLess).toBe(resolution.classification);
              expect(row.rationale).toBe(resolution.rationale);
              expect(result.unclassified).not.toContain(row.capabilityId);

              if (resolution.classification === "no-body-open-shape-covered") {
                // Covered: never fails the gate for a missing response schema.
                expect(row.status).toBe("covered");
                expect(tracked.has(row.capabilityId)).toBe(false);
              } else {
                // tracked-partial: partial in the table but tracked, so it is
                // excluded from the failure decision (Req 16.3).
                expect(row.status).toBe("partial");
                expect(tracked.has(row.capabilityId)).toBe(true);
              }
            } else {
              // Unresolved schema-less capability → named + partial (Req 16.5).
              expect(row.schemaLess).toBeNull();
              expect(row.rationale).toBeNull();
              expect(row.status).toBe("partial");
              expect(result.unclassified).toContain(row.capabilityId);
              expect(tracked.has(row.capabilityId)).toBe(false);
            }
          }

          // `failed` is exactly "some capability is unclassified".
          expect(result.failed).toBe(result.unclassified.length > 0);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("an unclassified schema-less capability is named in `unclassified` and sets failed=true", () => {
    fc.assert(
      fc.property(
        fc.array(schemaLessCapabilityArb, { minLength: 1, maxLength: 12 }),
        catalogArb,
        (caps, catalog) => {
          const catalogIds = new Set(catalog.map((r) => r.capabilityId));
          // The distinct schema-less capabilityIds that have no classification.
          const expectedUnclassified = new Set(
            caps.map((c) => c.capabilityId).filter((id) => !catalogIds.has(id)),
          );

          const result = resolveSchemaLess(caps, catalog);

          // Every unclassified capability is named exactly.
          expect(new Set(result.unclassified)).toEqual(expectedUnclassified);

          // Presence of any unclassified capability forces the gate to fail.
          expect(result.failed).toBe(expectedUnclassified.size > 0);
          if (expectedUnclassified.size > 0) {
            expect(result.failed).toBe(true);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it("a fully classified schema-less surface never fails and names nothing (Req 16.4 corollary)", () => {
    fc.assert(
      fc.property(
        fc.array(schemaLessCapabilityArb, { maxLength: 12 }),
        (caps) => {
          // Build a catalog that classifies every present capability.
          const catalog: SchemaLessResolution[] = caps.map((c) => ({
            capabilityId: c.capabilityId,
            classification: "no-body-open-shape-covered",
            rationale: `classified ${c.capabilityId}`,
          }));

          const result = resolveSchemaLess(caps, catalog);

          expect(result.unclassified).toEqual([]);
          expect(result.failed).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });
});
