import type { CalibrationBin } from "@domain/operations";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReliabilityCurve } from "../ReliabilityCurve";

function bin(lo: number, n: number, observed: number | null): CalibrationBin {
  return { lo, hi: lo + 0.1, n, mean_confidence: lo + 0.05, observed_rate: observed };
}

describe("ReliabilityCurve (FE-INV-043 honest about evidence)", () => {
  it("says so when there are no scored outcomes, instead of drawing a flat line", () => {
    render(<ReliabilityCurve bins={[]} />);
    expect(screen.getByText(/Awaiting scored outcomes/)).toBeInTheDocument();
  });

  it("ignores bins with n=0 or a null observed rate", () => {
    render(<ReliabilityCurve bins={[bin(0.5, 0, 0.5), bin(0.6, 3, null)]} />);
    // Both bins are unscorable → still 'awaiting', never a fabricated point.
    expect(screen.getByText(/Awaiting scored outcomes/)).toBeInTheDocument();
  });

  it("discloses the scored n in the figure summary", () => {
    render(<ReliabilityCurve bins={[bin(0.9, 4, 0.75), bin(0.8, 2, 0.5)]} />);
    const fig = screen.getByRole("img");
    expect(fig.getAttribute("aria-label")).toMatch(/6 scored decisions/);
  });
});
