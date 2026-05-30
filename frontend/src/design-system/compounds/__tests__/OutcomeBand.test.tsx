import { OutcomeBand, quantile, quantileDots } from "@ds/compounds/OutcomeBand";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("quantile", () => {
  it("interpolates quantiles of a sorted sample", () => {
    const s = [0, 1, 2, 3, 4];
    expect(quantile(s, 0)).toBe(0);
    expect(quantile(s, 1)).toBe(4);
    expect(quantile(s, 0.5)).toBe(2);
    expect(quantile(s, 0.25)).toBe(1);
  });

  it("handles singletons and clamps q", () => {
    expect(quantile([7], 0.3)).toBe(7);
    expect(quantile([0, 10], 2)).toBe(10);
    expect(quantile([0, 10], -1)).toBe(0);
  });
});

describe("quantileDots", () => {
  it("produces N equal-probability dots", () => {
    const dots = quantileDots([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 20);
    expect(dots).toHaveLength(20);
    // Monotonic non-decreasing (dots walk up the distribution).
    for (let i = 1; i < dots.length; i++) {
      expect(dots[i]).toBeGreaterThanOrEqual(dots[i - 1] as number);
    }
  });

  it("returns nothing for an empty sample", () => {
    expect(quantileDots([], 20)).toEqual([]);
  });
});

describe("OutcomeBand", () => {
  it("refuses to imply precision with too few samples (P7)", () => {
    render(<OutcomeBand samples={[1, 2]} />);
    expect(screen.getByText(/Too few samples/)).toBeInTheDocument();
  });

  it("summarises median + tail percentiles for screen readers", () => {
    const samples = Array.from({ length: 40 }, (_, i) => i); // 0..39
    render(<OutcomeBand samples={samples} unit="m" label="Delivery time" />);
    expect(
      screen.getByRole("img", { name: /Delivery time: median .* 10th–90th percentile/ }),
    ).toBeInTheDocument();
  });

  it("counts scenarios beyond a ceiling threshold", () => {
    const samples = Array.from({ length: 20 }, (_, i) => i); // 0..19
    render(<OutcomeBand samples={samples} threshold={15} unit="m" />);
    // values 16..19 exceed 15 → roughly 4/20 over; assert the 'over' callout.
    expect(screen.getByText(/over 15m/)).toBeInTheDocument();
  });
});
