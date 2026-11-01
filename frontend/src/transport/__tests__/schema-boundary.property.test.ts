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
// Prototype-named extra keys (finding 120). fast-check's string arbitrary draws
// `__proto__`, `constructor` and `prototype` on purpose. JSON.parse makes each an
// own key. zod 4.6.7 does not copy an own `__proto__` into its output
// (`handleCatchall`, core/schemas.ts: "Don't copy an undeclared __proto__ into the
// result"), so the round-trip this property demands of every other key cannot hold
// for that one, and for it the property asserts the safe outcome instead: the
// parsed payload's prototype is still `Object.prototype`. `constructor` and
// `prototype` are copied like any other key, so they keep the round-trip.
// Explicit cases below meet all three names on every run.
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

/** A 200 JSON response carrying exactly `text`, as the bytes a gateway would send. */
function rawJsonResponse(text: string): Response {
  return new Response(text, {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function jsonResponse(body: unknown): Response {
  return rawJsonResponse(JSON.stringify(body));
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

// The declared top-level keys of DecisionEnvelopeSchema, read from the schema
// itself. Extra keys must be disjoint from these so we truly test *additive*
// forward compatibility. The hand-written list this replaced had drifted: it
// omitted `initiator`, so a drawn `initiator` key would have been parsed as the
// ZInitiator enum rather than passed through as an extra key.
const KNOWN_KEYS: readonly string[] = Object.keys(DecisionEnvelopeSchema.shape);

// Property names with prototype meaning: assigning `__proto__` on a plain object
// replaces its prototype, and `constructor` / `prototype` are the members a
// prototype-pollution chain walks through. Never filtered from the generator;
// the explicit cases at the end of this file meet each one on every run.
const PROTOTYPE_KEY_NAMES = ["__proto__", "constructor", "prototype"] as const;

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
  .filter((k) => !KNOWN_KEYS.includes(k));

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

        // No extra key, whatever its name, replaced the parsed payload's prototype.
        expect(Object.getPrototypeOf(result)).toBe(Object.prototype);

        // Forward compatibility: unknown additive keys pass through untouched
        // and never trigger a validation failure. `__proto__` alone is held to
        // the safe outcome asserted just above instead: zod does not copy it.
        for (const [key, value] of Object.entries(extras)) {
          if (key === "__proto__") continue;
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

// ---------------------------------------------------------------------------
// Prototype-named extra keys, on every run (finding 120)
// ---------------------------------------------------------------------------

describe("Schema boundary — prototype-named extra keys", () => {
  const DECISION_ID = "3f2b8c1e-5d4a-4c7b-9e6f-1a2b3c4d5e6f";

  // The value is an object on purpose. The `__proto__` setter ignores a primitive
  // other than null, so an object value is what shows a parser that lets the key
  // through: the parsed payload would then inherit `polluted` from it.
  it.each(PROTOTYPE_KEY_NAMES)(
    "an extra %s key neither replaces nor pollutes the parsed payload's prototype",
    async (key) => {
      const text = [
        `{"decision_id":"${DECISION_ID}","tier":"tier_2","confidence":0.5,`,
        `${JSON.stringify(key)}:{"polluted":true}}`,
      ].join("");
      // The body really carries the key as an own property, as a gateway's would.
      const sent: unknown = JSON.parse(text);
      expect(typeof sent === "object" && sent !== null && Object.hasOwn(sent, key)).toBe(true);

      const fetch = fetchMock();
      fetch.mockResolvedValueOnce(rawJsonResponse(text));
      const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

      const result = await client.get<Record<string, unknown>>("/decisions/live", {
        schema: DecisionEnvelopeSchema,
        schemaId: "decision-envelope.v1",
      });

      // The extra key did not fail the passthrough schema...
      expect(result.decision_id).toBe(DECISION_ID);
      // ...did not become the parsed payload's prototype...
      expect(Object.getPrototypeOf(result)).toBe(Object.prototype);
      expect(result.polluted).toBeUndefined();
      // ...and did not reach the prototype every object shares.
      expect(Object.hasOwn(Object.prototype, "polluted")).toBe(false);
    },
  );
});
