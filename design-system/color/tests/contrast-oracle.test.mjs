// ============================================================================
// Testing layer 6 — Oracle. The contrast engine is checked against
// independently-published reference values, not against itself.
//   - APCA-W3 0.1.9: #000-on-#fff = Lc 106.04 ; #fff-on-#000 = Lc -107.88
//   - WCAG 2.1: #fff/#000 = 21 ; #767676/#fff = 4.54 (the canonical AA edge)
// ============================================================================
import { describe, it, expect } from "vitest";
import { wcag, apca } from "../build/contrast.mjs";

describe("Oracle — APCA against APCA-W3 reference values", () => {
  it("black text on white is Lc ~106 (normal polarity)", () => {
    expect(apca("#000000", "#ffffff")).toBeCloseTo(106.04, 0);
  });
  it("white text on black is Lc ~-108 (reverse polarity)", () => {
    expect(apca("#ffffff", "#000000")).toBeCloseTo(-107.88, 0);
  });
  it("identical colours yield Lc 0", () => {
    expect(apca("#5b5b5b", "#5b5b5b")).toBe(0);
  });
});

describe("Oracle — WCAG against WCAG 2.1 reference values", () => {
  it("white on black is exactly 21:1", () => {
    expect(wcag("#ffffff", "#000000")).toBeCloseTo(21, 5);
  });
  it("#767676 on white is the canonical 4.54:1 AA edge", () => {
    expect(wcag("#767676", "#ffffff")).toBeCloseTo(4.54, 1);
  });
  it("identical colours yield 1:1", () => {
    expect(wcag("#abcdef", "#abcdef")).toBeCloseTo(1, 5);
  });
});
