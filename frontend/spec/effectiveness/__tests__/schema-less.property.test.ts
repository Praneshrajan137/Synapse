/**
 * Feature: atlas-console-effectiveness, Property 2: A capability with no
 * Domain_Schema is classified schema-less and surfaced as such, never treated
 * as schema-bound
 *
 * Validates: Requirements 2.4
 *
 * Property-based verification of the Effectiveness_Harness fixture factory's
 * schema-less classification (design "A. Harness — schema registry + fixture
 * factory"; Requirement 2.4). A Backend_Contract capability that has no
 * Domain_Schema — either because it carries no `schemaId` (`schemaId === null`)
 * or because its `schemaId` resolves to nothing in the shared registry — must
 * be marked `schema-less` and surfaced with that classification in the harness
 * report, and must NEVER be treated as `schema-bound`.
 *
 * Three universally-quantified facets are exercised with `numRuns: 100`:
 *
 *   1. `classifyFixture` on a capability with no Domain_Schema always yields a
 *      `schema-less` classification carrying a surfaced `reason`, never a
 *      `schema-bound` classification (Req 2.4).
 *   2. `buildFixture` on a null-schema capability always yields a `schema-less`
 *      result that preserves the capability id, never a `schema-bound` result,
 *      and never throws (a schema-less capability is not a build failure).
 *   3. A registered `schemaId` is, by contrast, classified `schema-bound` — the
 *      classifier discriminates rather than blanket-labelling everything
 *      schema-less.
 */

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  buildFixture,
  classifyFixture,
  type FixtureRequest,
} from "../fixture-factory";
import { DOMAIN_SCHEMA_REGISTRY, hasSchema, type SchemaId } from "../schema-registry";

/** Every `schemaId` bound in the shared registry — the schema-bound input space. */
const REGISTERED_SCHEMA_IDS: readonly SchemaId[] = Object.keys(DOMAIN_SCHEMA_REGISTRY);

/** A non-empty capability id; may name an HTTP, WS, or SSE capability. */
const capabilityIdArb = fc.oneof(
  fc.string({ minLength: 1 }),
  // Bias toward realistic capability ids so both schema-less reasons appear:
  // streamed channels (`.WS.`/`.SSE.`) → "open-shape", others → "no-body".
  fc
    .tuple(
      fc.constantFrom("decisions", "audit", "ops", "firehose", "auth"),
      fc.constantFrom("GET", "POST", "WS", "SSE"),
      fc.string({ minLength: 1 }),
    )
    .map(([domain, verb, path]) => `${domain}.${verb}.${path}`),
);

/** A `schemaId` string that is NOT registered — i.e. resolves to no Domain_Schema. */
const unregisteredSchemaIdArb = fc
  .string({ minLength: 1 })
  .filter((id) => !hasSchema(id));

describe("Property 2: schema-less classification", () => {
  it("guards the registry is non-empty so the schema-bound contrast has an input space", () => {
    expect(REGISTERED_SCHEMA_IDS.length).toBeGreaterThan(0);
  });

  // Req 2.4: a capability with a null schemaId is classified schema-less and
  // surfaces a reason, never schema-bound.
  it("classifies a null-schema capability as schema-less with a surfaced reason", () => {
    fc.assert(
      fc.property(capabilityIdArb, fc.integer({ min: 0, max: 0xffffffff }), (capabilityId, seed) => {
        const req: FixtureRequest = { capabilityId, schemaId: null, seed };

        const classification = classifyFixture(req);

        expect(classification.kind).toBe("schema-less");
        if (classification.kind !== "schema-less") return;
        // The classification is surfaced with a concrete reason (Req 2.4).
        expect(["no-body", "open-shape"]).toContain(classification.reason);
      }),
      { numRuns: 100 },
    );
  });

  // Req 2.4: a capability whose schemaId is not registered has no Domain_Schema,
  // so it too must be classified schema-less rather than schema-bound.
  it("classifies an unregistered-schemaId capability as schema-less, never schema-bound", () => {
    fc.assert(
      fc.property(
        capabilityIdArb,
        unregisteredSchemaIdArb,
        fc.integer({ min: 0, max: 0xffffffff }),
        (capabilityId, schemaId, seed) => {
          const req: FixtureRequest = { capabilityId, schemaId, seed };

          const classification = classifyFixture(req);

          // No registered Domain_Schema ⇒ never schema-bound (Req 2.4).
          expect(classification.kind).toBe("schema-less");
        },
      ),
      { numRuns: 100 },
    );
  });

  // Req 2.4: buildFixture on a null-schema capability yields a schema-less
  // result (not schema-bound), preserves the capability id, and does not throw.
  it("builds a schema-less result for a null-schema capability, never schema-bound", () => {
    fc.assert(
      fc.property(capabilityIdArb, fc.integer({ min: 0, max: 0xffffffff }), (capabilityId, seed) => {
        const req: FixtureRequest = { capabilityId, schemaId: null, seed };

        const result = buildFixture(req);

        expect(result.kind).toBe("schema-less");
        if (result.kind !== "schema-less") return;
        // The classification is surfaced against the originating capability so
        // the harness report can attribute it (Req 2.4).
        expect(result.capabilityId).toBe(capabilityId);
      }),
      { numRuns: 100 },
    );
  });

  // Contrast facet: the classifier discriminates — a registered schemaId is
  // schema-bound, proving schema-less is not a blanket label (Req 2.4).
  it("classifies a registered schemaId as schema-bound, discriminating from schema-less", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...REGISTERED_SCHEMA_IDS),
        capabilityIdArb,
        fc.integer({ min: 0, max: 0xffffffff }),
        (schemaId, capabilityId, seed) => {
          const req: FixtureRequest = { capabilityId, schemaId, seed };

          const classification = classifyFixture(req);

          expect(classification.kind).toBe("schema-bound");
          if (classification.kind !== "schema-bound") return;
          expect(classification.schemaId).toBe(schemaId);
        },
      ),
      { numRuns: 100 },
    );
  });
});
