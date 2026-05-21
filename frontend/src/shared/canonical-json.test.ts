/**
 * SYNAPSE Atlas Console — canonical JSON property tests.
 *
 * These tests are the front line of the I-13 contract. Property names
 * prefixed with "prop:" so `pnpm test:property` can grep them.
 */
import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { canonicalize, CanonicalJsonError } from "./canonical-json";

describe("canonical-json", () => {
  it("encodes primitives the way Python's json.dumps would", () => {
    expect(canonicalize(null)).toBe("null");
    expect(canonicalize(true)).toBe("true");
    expect(canonicalize(false)).toBe("false");
    expect(canonicalize(0)).toBe("0");
    expect(canonicalize(-1.5)).toBe("-1.5");
    expect(canonicalize("hello")).toBe('"hello"');
    expect(canonicalize("ünïçødé")).toBe('"ünïçødé"');
  });

  it("sorts object keys ascending and uses ',' / ':' separators", () => {
    const obj = { b: 2, a: 1, c: { z: 3, y: 2 } };
    expect(canonicalize(obj)).toBe('{"a":1,"b":2,"c":{"y":2,"z":3}}');
  });

  it("preserves array order", () => {
    expect(canonicalize([3, 1, 2])).toBe("[3,1,2]");
  });

  it("drops undefined object values like JSON.stringify", () => {
    expect(canonicalize({ a: 1, b: undefined })).toBe('{"a":1}');
  });

  it("rejects non-finite numbers", () => {
    expect(() => canonicalize(NaN)).toThrow(CanonicalJsonError);
    expect(() => canonicalize(Infinity)).toThrow(CanonicalJsonError);
    expect(() => canonicalize(-Infinity)).toThrow(CanonicalJsonError);
  });

  it("rejects bigint and undefined at the root", () => {
    expect(() => canonicalize(undefined)).toThrow(CanonicalJsonError);
    expect(() => canonicalize(BigInt(1))).toThrow(CanonicalJsonError);
  });

  it("prop: round-trips JSON-safe arbitraries through JSON.parse", () => {
    fc.assert(
      fc.property(
        fc.jsonValue({ noUnicodeString: false, depthSize: "small" }),
        (value) => {
          const out = canonicalize(value);
          expect(JSON.parse(out)).toEqual(value);
        },
      ),
      { seed: 20260430, numRuns: 250 },
    );
  });

  it("prop: stable under key-permutation (sort invariance)", () => {
    fc.assert(
      fc.property(
        fc.dictionary(fc.string(), fc.jsonValue({ depthSize: "small" })),
        (dict) => {
          const a = { ...dict };
          const reversedKeys = Object.keys(a).reverse();
          const b: Record<string, unknown> = {};
          for (const k of reversedKeys) b[k] = a[k];
          expect(canonicalize(a)).toBe(canonicalize(b));
        },
      ),
      { seed: 20260430, numRuns: 250 },
    );
  });
});
