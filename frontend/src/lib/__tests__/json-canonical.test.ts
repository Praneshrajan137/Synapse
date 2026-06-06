import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { canonicalJson } from "../json-canonical";

// FE-INV-012 — canonical JSON outbound.
describe("canonicalJson", () => {
  it("sorts object keys recursively", () => {
    const a = { b: 1, a: { z: 1, y: 2 } };
    const b = { a: { y: 2, z: 1 }, b: 1 };
    expect(canonicalJson(a)).toBe(canonicalJson(b));
    expect(canonicalJson(a)).toBe('{"a":{"y":2,"z":1},"b":1}');
  });

  it("drops undefined object properties (Python json.dumps semantics)", () => {
    expect(canonicalJson({ a: 1, b: undefined })).toBe('{"a":1}');
  });

  it("serializes undefined in arrays as null (JSON.stringify parity)", () => {
    expect(canonicalJson([1, undefined, 3])).toBe("[1,null,3]");
  });

  it("rejects non-finite numbers (mirrors Python json.dumps default)", () => {
    expect(() => canonicalJson({ x: Number.POSITIVE_INFINITY })).toThrow(RangeError);
    expect(() => canonicalJson({ x: Number.NaN })).toThrow(RangeError);
  });

  it("emits dates as ISO strings", () => {
    const date = new Date("2026-05-18T12:00:00.000Z");
    expect(canonicalJson({ ts: date })).toBe('{"ts":"2026-05-18T12:00:00.000Z"}');
  });

  it("is deterministic regardless of insertion order (property test)", () => {
    fc.assert(
      fc.property(fc.dictionary(fc.string({ minLength: 1, maxLength: 8 }), fc.integer()), (obj) => {
        const reversed = Object.fromEntries(Object.entries(obj).reverse());
        return canonicalJson(obj) === canonicalJson(reversed);
      }),
      { numRuns: 200 },
    );
  });

  // ---------------------------------------------------------------------------
  // Sprint 13 §Phase 4.1 — kill mutmut survivors in json-canonical.ts.
  // The previous run left 8 mutants alive in `isPlainObject` (LogicalOperator,
  // ConditionalExpression) and in canonicalize's null/error-message paths.
  // Each test below targets one survivor by name.
  // ---------------------------------------------------------------------------

  it("null serializes to 'null' literal, NOT throws (kills L26 ConditionalExpression)", () => {
    // Survivor: `if (value === null) return null` mutated to `false` would
    // fall through to the unsupported-type branch and throw.
    expect(canonicalJson(null)).toBe("null");
  });

  it("top-level null inside object still serializes to literal null", () => {
    expect(canonicalJson({ x: null })).toBe('{"x":null}');
  });

  it("arrays are NOT treated as plain objects (kills LogicalOperator !Array.isArray flip)", () => {
    // Survivor: `!Array.isArray(v)` mutated to `Array.isArray(v)` would route
    // arrays through the plain-object branch and emit `{}`. Pin the actual
    // array serialization.
    expect(canonicalJson([3, 1, 2])).toBe("[3,1,2]");
    // Nested array of objects keeps array semantics
    expect(canonicalJson([{ b: 1, a: 2 }])).toBe('[{"a":2,"b":1}]');
  });

  it("primitives skip the plain-object branch (kills LogicalOperator typeof flips)", () => {
    // If `typeof v === "object" && v !== null` were mutated to `||`, then
    // string/number would enter isPlainObject. Pin all primitive serializations.
    expect(canonicalJson("hello")).toBe('"hello"');
    expect(canonicalJson(42)).toBe("42");
    expect(canonicalJson(true)).toBe("true");
    expect(canonicalJson(false)).toBe("false");
    expect(canonicalJson(0)).toBe("0");
    expect(canonicalJson("")).toBe('""');
  });

  it("error message contains the offending value (kills L31 StringLiteral '``' mutation)", () => {
    // Survivor: the template string in the RangeError is replaced with empty
    // backticks. Asserting the message contains the value-name kills it.
    expect(() => canonicalJson({ x: Number.POSITIVE_INFINITY })).toThrow(/non-finite number/);
    expect(() => canonicalJson({ x: Number.NEGATIVE_INFINITY })).toThrow(/non-finite number/);
  });

  it("unsupported types throw TypeError with type name in the message", () => {
    // bigint is unsupported — pin the TypeError + the typeof in the message
    expect(() => canonicalJson({ x: BigInt(1) as unknown })).toThrow(TypeError);
    expect(() => canonicalJson({ x: BigInt(1) as unknown })).toThrow(/bigint/);
    expect(() => canonicalJson({ x: Symbol("s") as unknown })).toThrow(/symbol/);
  });

  it("isPlainObject path is exercised on Date BEFORE plain-object branch", () => {
    // Date.instanceof check is before isPlainObject. A mutant that drops the
    // Date branch would fall into isPlainObject and emit `{}`. Pin the ISO.
    const d = new Date("2026-01-01T00:00:00.000Z");
    expect(canonicalJson({ when: d })).toBe('{"when":"2026-01-01T00:00:00.000Z"}');
  });

  it("nested arrays of nulls remain literal nulls", () => {
    // Nested null at every level — kills any mutant that conflates null with
    // undefined or with empty object.
    expect(canonicalJson([null, [null, null], { a: null }])).toBe('[null,[null,null],{"a":null}]');
  });
});
