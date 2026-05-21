// ============================================================================
// Testing layer 5 — Design by Contract. Pre/postconditions on the resolver's
// critical functions (parseOklch, gamutMap, resolveAll reference resolution).
// ============================================================================
import { describe, it, expect } from "vitest";
import { parseOklch, gamutMap, resolveAll, isInGamut, toRgb, num } from "../build/resolve.mjs";

describe("DbC — parseOklch precondition", () => {
  it("parses a well-formed OKLCH literal", () => {
    expect(parseOklch("oklch(0.7 0.15 250)")).toMatchObject({ l: 0.7, c: 0.15, h: 250 });
  });
  it("throws on an unparseable value", () => {
    expect(() => parseOklch("not-a-color")).toThrow(/parseOklch/);
  });
});

describe("DbC — gamutMap postcondition", () => {
  it("result is in-gamut and preserves L and H for every sampled input", () => {
    for (let l = 0.1; l <= 0.95; l += 0.1) {
      for (let h = 0; h < 360; h += 45) {
        const out = gamutMap({ mode: "oklch", l, c: 0.4, h });
        expect(isInGamut(toRgb(out)), `L${l} H${h}`).toBe(true);
        expect(out.l).toBe(num(l, 4));
        expect(out.h).toBe(num(h, 2));
      }
    }
  });
});

describe("DbC — reference resolution preconditions (PRE-CLR-002)", () => {
  it("throws on a dangling reference", () => {
    const flat = new Map([["a.x", { type: "color", value: "{a.missing}" }]]);
    expect(() => resolveAll(flat)).toThrow(/PRE-CLR-002|dangling/);
  });
  it("throws on a circular reference", () => {
    const flat = new Map([
      ["a", { type: "color", value: "{b}" }],
      ["b", { type: "color", value: "{a}" }],
    ]);
    expect(() => resolveAll(flat)).toThrow(/circular/);
  });
  it("throws when a themed value is missing a branch", () => {
    const flat = new Map([["a", { type: "color", value: { dark: "oklch(0.5 0 0)" } }]]);
    expect(() => resolveAll(flat)).toThrow();
  });
  it("resolves a valid reference chain", () => {
    const flat = new Map([
      ["base", { type: "color", value: { light: "oklch(0.9 0 0)", dark: "oklch(0.2 0 0)" } }],
      ["alias", { type: "color", value: "{base}" }],
    ]);
    const out = resolveAll(flat);
    expect(out.dark.get("alias").oklch.l).toBe(0.2);
    expect(out.light.get("alias").oklch.l).toBe(0.9);
  });
});
