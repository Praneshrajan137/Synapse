import { describe, expect, it } from "vitest";
import {
  AWAITING_UPLIFT_MEASURE,
  UPLIFT_BACKEND_GAP,
  type UpliftMeasure,
  resolveUpliftSlot,
} from "../uplift-slot";

function measure(overrides: Partial<UpliftMeasure> = {}): UpliftMeasure {
  return {
    value: 0.12,
    sampleSize: 480,
    windowLabel: "Last 30 days",
    asOf: "2025-01-01T00:00:00.000Z",
    ...overrides,
  };
}

// Req 17.1–17.4 — the pure Operations uplift slot resolver.
describe("resolveUpliftSlot", () => {
  it("renders a present state disclosing value, sample size, window, and as-of (Req 17.2)", () => {
    const slot = resolveUpliftSlot(measure());
    expect(slot).toEqual({
      kind: "present",
      value: 0.12,
      sampleSize: 480,
      windowLabel: "Last 30 days",
      asOf: "2025-01-01T00:00:00.000Z",
    });
  });

  it("renders an awaiting state when no measure is exposed — never hidden (Req 17.1, 17.3)", () => {
    const slot = resolveUpliftSlot(null);
    expect(slot).toEqual({ kind: "awaiting" });
    expect(AWAITING_UPLIFT_MEASURE).toBe("Awaiting uplift measure");
  });

  it("does not fabricate a value from an untrustworthy measure (Req 17.4)", () => {
    // Non-finite value, non-positive/non-finite sample size, or empty
    // disclosures cannot be presented honestly → they collapse to awaiting.
    expect(resolveUpliftSlot(measure({ value: Number.NaN })).kind).toBe("awaiting");
    expect(resolveUpliftSlot(measure({ value: Number.POSITIVE_INFINITY })).kind).toBe("awaiting");
    expect(resolveUpliftSlot(measure({ sampleSize: 0 })).kind).toBe("awaiting");
    expect(resolveUpliftSlot(measure({ sampleSize: -5 })).kind).toBe("awaiting");
    expect(resolveUpliftSlot(measure({ sampleSize: Number.NaN })).kind).toBe("awaiting");
    expect(resolveUpliftSlot(measure({ windowLabel: "   " })).kind).toBe("awaiting");
    expect(resolveUpliftSlot(measure({ asOf: "" })).kind).toBe("awaiting");
  });

  it("presents a real measured value of zero — 0 is a measurement, not absence", () => {
    const slot = resolveUpliftSlot(measure({ value: 0 }));
    expect(slot.kind).toBe("present");
    if (slot.kind === "present") expect(slot.value).toBe(0);
  });

  it("truncates a fractional sample size to a whole observation count", () => {
    const slot = resolveUpliftSlot(measure({ sampleSize: 480.9 }));
    expect(slot.kind).toBe("present");
    if (slot.kind === "present") expect(slot.sampleSize).toBe(480);
  });

  it("exposes the uplift backend gap for the drift report (Req 17.3)", () => {
    expect(UPLIFT_BACKEND_GAP.kind).toBe("uplift");
    expect(UPLIFT_BACKEND_GAP.name).toBe("system-level-uplift-measure");
    expect(UPLIFT_BACKEND_GAP.rationale.length).toBeGreaterThan(0);
  });
});
