import { describe, expect, it } from "vitest";
import {
  DECK_NEUTRAL,
  DECK_RISK,
  DECK_WARN,
  SATURATION_RISK,
  SATURATION_WARN,
  storeFillColor,
} from "../palette";

describe("storeFillColor — quiet by default (SENSORIUM P3)", () => {
  it("is neutral at rest (a healthy store is NOT coloured)", () => {
    expect(storeFillColor(0)).toEqual(DECK_NEUTRAL);
    expect(storeFillColor(undefined)).toEqual(DECK_NEUTRAL);
    expect(storeFillColor(SATURATION_WARN)).toEqual(DECK_NEUTRAL); // boundary inclusive-below
  });

  it("warns above the warn threshold", () => {
    expect(storeFillColor(SATURATION_WARN + 0.01)).toEqual(DECK_WARN);
    expect(storeFillColor(0.85)).toEqual(DECK_WARN);
  });

  it("flags risk above the risk threshold", () => {
    expect(storeFillColor(SATURATION_RISK + 0.01)).toEqual(DECK_RISK);
    expect(storeFillColor(1)).toEqual(DECK_RISK);
  });

  it("returns 4-channel RGBA tuples", () => {
    for (const v of [0, 0.8, 0.95]) {
      expect(storeFillColor(v)).toHaveLength(4);
    }
  });
});
