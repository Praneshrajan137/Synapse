// Feature: atlas-console-elevation, Property 43: Telemetry payloads are field-whitelisted
//
// Property 43 (Validates: Requirements 14.1) — for ANY telemetry event, the
// payload produced by `whitelistTelemetryFields` (the single source of truth
// for what leaves the client) contains ONLY allow-listed field names, carries
// no `undefined` values, never invents a field the input did not have, and
// never mutates its input.

import { ALLOWED_TELEMETRY_FIELDS, whitelistTelemetryFields } from "@lib/log";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const ALLOWED = new Set<string>(ALLOWED_TELEMETRY_FIELDS);

// Mix allow-listed keys with clearly-forbidden ones (raw payloads, PII, etc.)
// so the whitelist has something to strip on essentially every run.
const FORBIDDEN_KEYS = [
  "username",
  "operator_id",
  "email",
  "password",
  "raw_payload",
  "secret",
  "authorization",
  "cookie",
] as const;

const keyArb: fc.Arbitrary<string> = fc.oneof(
  fc.constantFrom(...ALLOWED_TELEMETRY_FIELDS),
  fc.constantFrom(...FORBIDDEN_KEYS),
  fc.string({ minLength: 1, maxLength: 12 }),
);

const valueArb: fc.Arbitrary<unknown> = fc.oneof(
  fc.string(),
  fc.integer(),
  fc.boolean(),
  fc.constant(null),
  fc.constant(undefined),
);

const eventArb: fc.Arbitrary<Record<string, unknown>> = fc.dictionary(keyArb, valueArb, {
  maxKeys: 12,
});

describe("whitelistTelemetryFields — Property 43: telemetry payloads are field-whitelisted", () => {
  it("forwards ONLY allow-listed fields, and never a non-whitelisted one", () => {
    fc.assert(
      fc.property(eventArb, (event) => {
        const out = whitelistTelemetryFields(event);
        for (const key of Object.keys(out)) {
          expect(ALLOWED.has(key)).toBe(true);
        }
      }),
      { numRuns: 200 },
    );
  });

  it("emits exactly the allow-listed input keys that had a defined value", () => {
    fc.assert(
      fc.property(eventArb, (event) => {
        const out = whitelistTelemetryFields(event);
        const expected = Object.keys(event).filter((k) => ALLOWED.has(k) && event[k] !== undefined);
        expect(new Set(Object.keys(out))).toEqual(new Set(expected));
        // Values are passed through untouched (never fabricated) ...
        for (const k of expected) expect(out[k]).toBe(event[k]);
        // ... and no `undefined` value ever survives.
        for (const v of Object.values(out)) expect(v).not.toBeUndefined();
      }),
      { numRuns: 200 },
    );
  });

  it("never mutates its input event", () => {
    fc.assert(
      fc.property(eventArb, (event) => {
        const snapshot = JSON.stringify(event);
        whitelistTelemetryFields(event);
        expect(JSON.stringify(event)).toBe(snapshot);
      }),
      { numRuns: 200 },
    );
  });
});
