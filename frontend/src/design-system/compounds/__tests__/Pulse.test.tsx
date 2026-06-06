import { Pulse, beatPeriodMs } from "@ds/compounds/Pulse";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("beatPeriodMs — calm, bounded cadence", () => {
  it("rests slowly when idle", () => {
    expect(beatPeriodMs(0)).toBe(2600);
    expect(beatPeriodMs(-5)).toBe(2600);
    expect(beatPeriodMs(Number.NaN)).toBe(2600);
  });

  it("speeds up with load but never strobes (floor 900ms)", () => {
    expect(beatPeriodMs(120)).toBe(900);
    expect(beatPeriodMs(1000)).toBe(900); // clamped
    expect(beatPeriodMs(60)).toBeGreaterThan(900);
    expect(beatPeriodMs(60)).toBeLessThan(2600);
  });

  it("is monotonic decreasing in rate", () => {
    let prev = Number.POSITIVE_INFINITY;
    for (let r = 0; r <= 120; r += 10) {
      const p = beatPeriodMs(r);
      expect(p).toBeLessThanOrEqual(prev);
      prev = p;
    }
  });
});

describe("Pulse", () => {
  it("renders the rate and confidence as text, not colour alone (INV-CLR-011)", () => {
    render(<Pulse rate={42} confidence={0.88} />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("88%")).toBeInTheDocument();
    expect(screen.getByText("autonomous")).toBeInTheDocument();
  });

  it("classifies the confidence zone against the I-5 gates", () => {
    const { rerender } = render(<Pulse rate={10} confidence={0.65} />);
    expect(screen.getByText("needs review")).toBeInTheDocument();
    rerender(<Pulse rate={10} confidence={0.75} />);
    expect(screen.getByText("on the gate")).toBeInTheDocument();
    rerender(<Pulse rate={10} confidence={0.95} />);
    expect(screen.getByText("autonomous")).toBeInTheDocument();
  });

  it("shows an honest 'no signal' state when confidence is null (P7)", () => {
    render(<Pulse rate={0} confidence={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("no signal")).toBeInTheDocument();
    // Never invents a percentage when there is no data.
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });

  it("exposes a descriptive role=img label for screen readers", () => {
    render(<Pulse rate={42} confidence={0.88} />);
    const fig = screen.getByRole("img", {
      name: /System pulse: 42 decisions per minute, aggregate confidence 88 percent — autonomous/,
    });
    expect(fig).toBeInTheDocument();
  });

  it("labels the no-signal case honestly for screen readers", () => {
    render(<Pulse rate={5} confidence={null} />);
    expect(screen.getByRole("img", { name: /no confidence signal yet/ })).toBeInTheDocument();
  });

  it("rounds and clamps a noisy rate", () => {
    render(<Pulse rate={41.7} confidence={0.9} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("accepts a className override", () => {
    const { container } = render(<Pulse rate={1} confidence={0.9} className="pulse-marker-xyz" />);
    expect(container.firstElementChild?.className).toMatch(/pulse-marker-xyz/);
  });
});
