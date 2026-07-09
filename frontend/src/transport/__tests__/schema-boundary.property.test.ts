// Feature: atlas-console-elevation, Property 4: Schema boundary is fail-closed and forward-compatible
//
// Property 4: For any payload that satisfies a domain schema, parsing through
// the transport boundary (`parseWithSchema`, exercised via `createHttpClient`)
// succeeds even when arbitrary additional (disjoint) keys are present, and all
// known fields are preserved (forward-compatible / passthrough — Req 1.4). For
// any payload missing a required field or presenting a type-mismatched field,
// parsing raises a typed `SchemaViolationError` and yields no rendered value
// (fail-closed — Req 1.2).
//
// The representative passthrough domain schema is `DecisionEnvelopeSchema`
// (task 3.1 made response schemas `.passthrough()`); the boundary is the real
// `createHttpClient` response path, so this test drives `parseWithSchema`
// exactly as the running Console does.
//
// Validates: Requirements 1.2, 1.4

import fc from "fast-check";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionEnvelopeSchema } from "../../domain/decision-envelope";
import { SchemaViolationError } from "../errors";
import { createHttpClient } from "../http-client";

// ---------------------------------------------------------------------------
// Test doubles: a real HTTP client over a mocked `fetch`, matching the
// established transport test harness (http-client.test.ts).
// ---------------------------------------------------------------------------

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function fetchMock(): ReturnType<typeof vi.fn> {
  const mock = vi.fn();
  vi.stubGlobal("fetch", mock);
  return mock;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

// The known top-level keys of DecisionEnvelopeSchema. Extra keys must be
// disjoint from these so we truly test *additive* forward compatibility.
const KNOWN_KEYS = [
  "decision_id",
  "tier",
  "confidence",
  "phase_reached",
  "escalated",
  "selected_action",
  "timestamp",
  "degraded",
  "is_synthetic",
  "agents",
] as const;

type ValidEnvelope = {
  decision_id: string;
  tier: string;
  confidence: number;
  phase_reached: number;
  escalated: boolean;
  degraded: boolean;
  is_synthetic: boolean;
};

// A payload that satisfies DecisionEnvelopeSchema. The three fields with no
// schema default — decision_id, tier, confidence — are the "required" fields;
// the rest carry defaults but we populate them for a fuller round-trip.
const validEnvelopeArb: fc.Arbitrary<ValidEnvelope> = fc.record({
  decision_id: fc.uuid(),
  tier: fc.constantFrom("tier_1", "tier_2", "tier_3", "tier_4"),
  confidence: fc.double({ min: 0, max: 1, noNaN: true }),
  phase_reached: fc.integer({ min: 1, max: 5 }),
  escalated: fc.boolean(),
  degraded: fc.boolean(),
  is_synthetic: fc.boolean(),
});

// Arbitrary keys that are guaranteed disjoint from the known schema keys.
const extraKeyArb: fc.Arbitrary<string> = fc
  .string({ minLength: 1, maxLength: 12 })
  .filter((k) => !(KNOWN_KEYS as readonly string[]).includes(k));

// A dictionary of disjoint additive fields with JSON-round-trippable values.
const extraFieldsArb: fc.Arbitrary<Record<string, unknown>> = fc.dictionary(
  extraKeyArb,
  fc.oneof(
    fc.string(),
    fc.integer(),
    fc.boolean(),
    fc.constant(null),
    fc.array(fc.string(), { maxLength: 3 }),
  ),
  { maxKeys: 5 },
);

// The three required fields (no schema default) — removing any one is a
// guaranteed "missing required field" violation.
const requiredKeyArb = fc.constantFrom<keyof ValidEnvelope>("decision_id", "tier", "confidence");

// An invalid payload: either a valid envelope with a required field removed,
// or a valid envelope with a required field corrupted to the wrong type.
const invalidEnvelopeArb: fc.Arbitrary<Record<string, unknown>> = validEnvelopeArb.chain((base) =>
  fc.oneof(
    // (a) Missing required field.
    requiredKeyArb.map((key) => {
      const copy: Record<string, unknown> = { ...base };
      delete copy[key];
      return copy;
    }),
    // (b) Type-mismatched required field.
    fc.constantFrom<Record<string, unknown>>(
      { ...base, confidence: "high" }, // number → string
      { ...base, confidence: true }, // number → boolean
      { ...base, tier: "tier_9" }, // enum member → non-member
      { ...base, tier: 3 }, // enum member → number
      { ...base, decision_id: 12345 }, // uuid string → number
      { ...base, decision_id: "not-a-uuid" }, // uuid string → non-uuid string
    ),
  ),
);

// ---------------------------------------------------------------------------
// Property 4
// ---------------------------------------------------------------------------

describe("Schema boundary — Property 4: fail-closed and forward-compatible", () => {
  it("parses a valid payload with arbitrary disjoint extra keys and preserves known fields", async () => {
    await fc.assert(
      fc.asyncProperty(validEnvelopeArb, extraFieldsArb, async (envelope, extras) => {
        const payload = { ...envelope, ...extras };
        const fetch = fetchMock();
        fetch.mockResolvedValueOnce(jsonResponse(payload));
        const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

        const result = await client.get<Record<string, unknown>>("/decisions/live", {
          schema: DecisionEnvelopeSchema,
          schemaId: "decision-envelope.v1",
        });

        // Known fields are preserved verbatim.
        expect(result.decision_id).toBe(envelope.decision_id);
        expect(result.tier).toBe(envelope.tier);
        expect(result.confidence).toBe(envelope.confidence);
        expect(result.phase_reached).toBe(envelope.phase_reached);
        expect(result.escalated).toBe(envelope.escalated);
        expect(result.degraded).toBe(envelope.degraded);
        expect(result.is_synthetic).toBe(envelope.is_synthetic);

        // Forward compatibility: unknown additive keys pass through untouched
        // and never trigger a validation failure.
        for (const [key, value] of Object.entries(extras)) {
          expect(result[key]).toStrictEqual(value);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("raises SchemaViolationError and yields no value for missing-required or type-mismatched payloads", async () => {
    await fc.assert(
      fc.asyncProperty(invalidEnvelopeArb, async (payload) => {
        const UNSET = Symbol("unset");
        const fetch = fetchMock();
        fetch.mockResolvedValueOnce(jsonResponse(payload));
        const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

        let rendered: unknown = UNSET;
        let error: unknown;
        try {
          rendered = await client.get("/decisions/live", {
            schema: DecisionEnvelopeSchema,
            schemaId: "decision-envelope.v1",
          });
        } catch (err) {
          error = err;
        }

        // Fail-closed: a typed SchemaViolationError is raised...
        expect(error).toBeInstanceOf(SchemaViolationError);
        expect((error as SchemaViolationError).schemaId).toBe("decision-envelope.v1");
        expect((error as SchemaViolationError).issues.length).toBeGreaterThan(0);

        // ...and no value is ever produced for rendering (the assignment never
        // ran, so the sentinel is untouched).
        expect(rendered).toBe(UNSET);
      }),
      { numRuns: 100 },
    );
  });
});
