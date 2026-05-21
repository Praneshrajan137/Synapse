import { describe, expect, it } from "vitest";
import fc from "fast-check";
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
      fc.property(
        fc.dictionary(fc.string({ minLength: 1, maxLength: 8 }), fc.integer()),
        (obj) => {
          const reversed = Object.fromEntries(Object.entries(obj).reverse());
          return canonicalJson(obj) === canonicalJson(reversed);
        },
      ),
      { numRuns: 200 },
    );
  });
});
