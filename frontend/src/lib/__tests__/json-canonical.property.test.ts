// Feature: atlas-console-elevation, Property 41: Outbound payloads are canonical JSON
//
// Property 41 (Validates: Requirements 12.4) — for ANY JSON-serializable value,
// `canonicalJson` produces output that:
//   • has lexicographically sorted object keys (recursively),
//   • carries NO insignificant whitespace (whitespace only ever appears inside
//     string literals, never between structural tokens),
//   • DROPS `undefined` object properties, and
//   • is IDEMPOTENT — re-canonicalizing the parsed canonical form is stable.

import { canonicalJson } from "@lib/json-canonical";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

// A JSON arbitrary constrained to what canonicalJson accepts: finite numbers,
// strings, booleans, null, and nested arrays/objects. (Non-finite numbers,
// bigint, symbol, and functions are rejected by contract and out of scope.)
const jsonArb: fc.Arbitrary<unknown> = fc.letrec((tie) => ({
  value: fc.oneof(
    { depthSize: "small" },
    fc.constant(null),
    fc.boolean(),
    fc.integer(),
    fc.double({ noNaN: true, noDefaultInfinity: true }),
    fc.string(),
    fc.array(tie("value"), { maxLength: 5 }),
    fc.dictionary(fc.string({ maxLength: 8 }), tie("value"), { maxKeys: 6 }),
  ),
})).value;

// A variant whose object keys are guaranteed NON-integer-like (prefixed), so
// re-parsing the canonical string preserves key order — JSON.parse otherwise
// hoists integer-like keys ("0") ahead of others per the JS spec, which would
// mask the (correct) lexicographic sort the serializer already applied.
const safeKeyArb: fc.Arbitrary<string> = fc.string({ maxLength: 8 }).map((s) => `k${s}`);
const jsonSafeKeysArb: fc.Arbitrary<unknown> = fc.letrec((tie) => ({
  value: fc.oneof(
    { depthSize: "small" },
    fc.constant(null),
    fc.boolean(),
    fc.integer(),
    fc.string(),
    fc.array(tie("value"), { maxLength: 5 }),
    fc.dictionary(safeKeyArb, tie("value"), { maxKeys: 6 }),
  ),
})).value;

/** Recursively assert every object's keys are in ascending lexicographic order. */
function assertSortedKeys(parsed: unknown): void {
  if (Array.isArray(parsed)) {
    for (const item of parsed) assertSortedKeys(item);
    return;
  }
  if (parsed !== null && typeof parsed === "object") {
    const keys = Object.keys(parsed as Record<string, unknown>);
    const sorted = [...keys].sort();
    expect(keys).toEqual(sorted);
    for (const k of keys) assertSortedKeys((parsed as Record<string, unknown>)[k]);
  }
}

/**
 * Structural whitespace scanner: walk the serialized string, skipping over
 * string literals (respecting `\"` escapes). Any space/tab/newline/CR found
 * OUTSIDE a string is "insignificant" whitespace and a violation.
 */
function hasInsignificantWhitespace(s: string): boolean {
  let inString = false;
  let escaped = false;
  for (const ch of s) {
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === "\\") escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') {
      inString = true;
      continue;
    }
    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r") return true;
  }
  return false;
}

describe("canonicalJson — Property 41: outbound payloads are canonical JSON", () => {
  it("sorts object keys recursively", () => {
    fc.assert(
      fc.property(jsonSafeKeysArb, (value) => {
        assertSortedKeys(JSON.parse(canonicalJson(value)));
      }),
      { numRuns: 200 },
    );
  });

  it("is invariant under input key reordering (a direct consequence of sorting)", () => {
    // Reversing a record's key insertion order must not change the canonical
    // output — the strongest observable form of "keys are sorted".
    const recordArb = fc.dictionary(safeKeyArb, jsonSafeKeysArb, { maxKeys: 8 });
    fc.assert(
      fc.property(recordArb, (record) => {
        const reversed = Object.fromEntries(Object.entries(record).reverse());
        expect(canonicalJson(reversed)).toBe(canonicalJson(record));
      }),
      { numRuns: 200 },
    );
  });

  it("emits no insignificant whitespace between structural tokens", () => {
    fc.assert(
      fc.property(jsonArb, (value) => {
        expect(hasInsignificantWhitespace(canonicalJson(value))).toBe(false);
      }),
      { numRuns: 200 },
    );
  });

  it("is idempotent — re-canonicalizing the parsed canonical form is stable", () => {
    fc.assert(
      fc.property(jsonArb, (value) => {
        const once = canonicalJson(value);
        const twice = canonicalJson(JSON.parse(once));
        expect(twice).toBe(once);
      }),
      { numRuns: 200 },
    );
  });

  it("drops `undefined` object properties", () => {
    // Build a record where some keys carry `undefined`; those keys must be
    // wholly absent from the canonical output (Python json.dumps parity).
    const recordWithUndefinedArb = fc.dictionary(
      fc.string({ minLength: 1, maxLength: 8 }),
      fc.oneof(fc.integer(), fc.string(), fc.boolean(), fc.constant(undefined)),
      { maxKeys: 8 },
    );

    fc.assert(
      fc.property(recordWithUndefinedArb, (record) => {
        const parsed = JSON.parse(canonicalJson(record)) as Record<string, unknown>;
        for (const [key, val] of Object.entries(record)) {
          if (val === undefined) {
            expect(Object.hasOwn(parsed, key)).toBe(false);
          } else {
            expect(Object.hasOwn(parsed, key)).toBe(true);
          }
        }
      }),
      { numRuns: 200 },
    );
  });
});
