import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfidenceChip } from "@ds/compounds/ConfidenceChip";

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
});
