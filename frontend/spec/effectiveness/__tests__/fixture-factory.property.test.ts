/**
 * Feature: atlas-console-effectiveness, Property 1: Every generated fixture
 * validates against its bound Domain_Schema, and any schema change that
 * invalidates a fixture fails at build/setup naming the fixture and schema
 *
 * Validates: Requirements 2.1, 2.2, 2.3
 *
 * Property-based verification of fixture–schema soundness for the
 * Effectiveness_Harness fixture factory (design "Property 1: Every fixture
 * validates against its bound Domain_Schema"). Two universally-quantified
 * facets are exercised over the real shared registry with `numRuns: 100`:
 *
 *   1. Soundness (Req 2.1, 2.2): for ANY registered `schemaId` and ANY seed,
 *      `buildFixture` derives a `schema-bound` body that validates against that
 *      SAME `Domain_Schema` — never a hand-authored, unbound, or invalid shape.
 *   2. Invalidation is caught, naming fixture + schema (Req 2.3): for ANY
 *      registered schema a fixture that no longer validates is mechanically
 *      detectable, and a build/setup validation failure raises a
 *      `FixtureSchemaError` that names both the offending fixture and schema.
 */

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  buildFixture,
  buildSchemaViolatingFixture,
  FixtureSchemaError,
  type FixtureRequest,
} from "../fixture-factory";
import { DOMAIN_SCHEMA_REGISTRY, getSchema, type SchemaId } from "../schema-registry";

/** Every `schemaId` bound in the shared registry — the schema-bound input space. */
const REGISTERED_SCHEMA_IDS: readonly SchemaId[] = Object.keys(DOMAIN_SCHEMA_REGISTRY);

/** An arbitrary drawing a registered schema id paired with a 32-bit seed. */
const registeredRequest = fc.record<Pick<FixtureRequest, "schemaId" | "seed">>({
  schemaId: fc.constantFrom(...REGISTERED_SCHEMA_IDS),
  seed: fc.integer({ min: 0, max: 0xffffffff }),
});

describe("Property 1: fixture–schema soundness", () => {
  it("guards the registry is non-empty so the property has an input space", () => {
    expect(REGISTERED_SCHEMA_IDS.length).toBeGreaterThan(0);
  });

  // Req 2.1 + 2.2: every derived fixture is schema-bound and validates against
  // its own bound Domain_Schema for any seed.
  it("derives a schema-bound body that validates against its bound Domain_Schema", () => {
    fc.assert(
      fc.property(registeredRequest, ({ schemaId, seed }) => {
        const req: FixtureRequest = {
          capabilityId: `cap.${schemaId}`,
          schemaId,
          seed,
        };

        const result = buildFixture(req);

        // The fixture is bound to the requested schema, never schema-less.
        expect(result.kind).toBe("schema-bound");
        if (result.kind !== "schema-bound") return;
        expect(result.schemaId).toBe(schemaId);

        // The body validates against the SAME schema the Console applies at
        // runtime — the core soundness guarantee (Req 2.1, 2.2).
        const schema = getSchema(schemaId);
        expect(schema).toBeDefined();
        expect(schema?.safeParse(result.body).success).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  // Req 2.3: a fixture that no longer validates its bound schema is caught
  // mechanically — the schema rejects the invalidating payload.
  it("detects an invalidating fixture: the bound schema rejects a schema-violating body", () => {
    fc.assert(
      fc.property(registeredRequest, ({ schemaId, seed }) => {
        const violating = buildSchemaViolatingFixture(schemaId, seed);
        const schema = getSchema(schemaId);
        expect(schema).toBeDefined();
        // A schema-invalidating fixture fails validation, so drift is caught.
        expect(schema?.safeParse(violating).success).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  // Req 2.1 + 2.3: a build/setup validation failure raises FixtureSchemaError
  // that NAMES both the offending fixture and the schema.
  it("fails naming the fixture and schema when the bound schema cannot be resolved", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1 }).filter((id) => !(id in DOMAIN_SCHEMA_REGISTRY)),
        fc.string({ minLength: 1 }),
        fc.integer({ min: 0, max: 0xffffffff }),
        (unknownSchemaId, capabilityId, seed) => {
          const req: FixtureRequest = { capabilityId, schemaId: unknownSchemaId, seed };

          let thrown: unknown;
          try {
            buildFixture(req);
          } catch (err) {
            thrown = err;
          }

          expect(thrown).toBeInstanceOf(FixtureSchemaError);
          const error = thrown as FixtureSchemaError;
          // The error names the offending fixture and schema (Req 2.1, 2.3).
          expect(error.fixtureId).toBe(capabilityId);
          expect(error.schemaId).toBe(unknownSchemaId);
          expect(error.message).toContain(capabilityId);
          expect(error.message).toContain(unknownSchemaId);
        },
      ),
      { numRuns: 100 },
    );
  });
});
