import { ConfidenceChip } from "@ds/compounds/ConfidenceChip";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("ConfidenceChip", () => {
  it("renders the percentage and color-band class", () => {
    render(<ConfidenceChip value={0.92} />);
    const chip = screen.getByLabelText(/Confidence 92 percent/i);
    expect(chip.className).toMatch(/confidence-ok/);
  });

  it("highlights when below threshold (FE-INV-007 visual signal)", () => {
    render(<ConfidenceChip value={0.6} threshold={0.7} />);
    const chip = screen.getByLabelText(/Confidence 60 percent.*below threshold/i);
    expect(chip.className).toMatch(/ring-/);
  });

  it("is driven by the continuous gate-anchored scale with VSUP (ADR-045)", () => {
    render(<ConfidenceChip value={0.55} />);
    const chip = screen.getByLabelText(/Confidence 55 percent/i);
    // Inline oklch colour from confidenceColor(value, {vsup: true}).
    expect(chip.getAttribute("style")).toMatch(/oklch\(/);
    expect(chip.className).toMatch(/confidence-risk/);
  });

  it("band classes map to the I-5 gates, not the legacy 0.9 cut", () => {
    // 0.75 sits in the escalation band [0.70, 0.80) — the old 3-stop ramp
    // wrongly called everything below 0.9 "warn" and above it "ok".
    render(<ConfidenceChip value={0.75} threshold={0.7} />);
    expect(screen.getByLabelText(/Confidence 75 percent/i).className).toMatch(/confidence-warn/);
    render(<ConfidenceChip value={0.82} threshold={0.7} />);
    expect(screen.getByLabelText(/Confidence 82 percent/i).className).toMatch(/confidence-ok/);
  });
});
