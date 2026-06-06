import {
  DIVERGENCE_RESYNC_THRESHOLD,
  DivergenceTrace,
  divergenceSummary,
} from "@ds/compounds/DivergenceTrace";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("divergenceSummary", () => {
  it("reports the I-12 re-sync threshold default", () => {
    expect(DIVERGENCE_RESYNC_THRESHOLD).toBe(0.1);
  });

  it("handles an empty series honestly", () => {
    const s = divergenceSummary([]);
    expect(s.latest).toBeNull();
    expect(s.breaches).toBe(0);
    expect(s.trend).toBe("n/a");
  });

  it("counts breaches above the threshold", () => {
    const s = divergenceSummary([0.02, 0.04, 0.12, 0.2, 0.05]);
    expect(s.breaches).toBe(2);
    expect(s.max).toBeCloseTo(0.2, 5);
    expect(s.latest).toBeCloseTo(0.05, 5);
  });

  it("derives trend from the last two samples", () => {
    expect(divergenceSummary([0.02, 0.05]).trend).toBe("rising");
    expect(divergenceSummary([0.08, 0.03]).trend).toBe("falling");
    expect(divergenceSummary([0.04, 0.04]).trend).toBe("flat");
  });
});

describe("DivergenceTrace", () => {
  it("renders an honest empty state with no samples", () => {
    render(<DivergenceTrace series={[]} />);
    expect(screen.getByText(/No twin divergence samples yet/)).toBeInTheDocument();
  });

  it("summarises latest + breaches for screen readers (INV-CLR-011)", () => {
    render(<DivergenceTrace series={[0.02, 0.04, 0.12, 0.05]} />);
    expect(
      screen.getByRole("img", {
        name: /latest KL 0.050.*re-sync threshold 0.1.*1 of 4 samples above threshold/,
      }),
    ).toBeInTheDocument();
  });

  it("calls out breaches vs all-clear in the caption", () => {
    const { rerender } = render(<DivergenceTrace series={[0.12, 0.15]} />);
    expect(screen.getByText(/breach/)).toBeInTheDocument();
    rerender(<DivergenceTrace series={[0.02, 0.03]} />);
    expect(screen.getByText(/no breaches/)).toBeInTheDocument();
  });
});
