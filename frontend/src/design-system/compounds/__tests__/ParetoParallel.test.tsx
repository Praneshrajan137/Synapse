import { ParetoParallel } from "@ds/compounds/ParetoParallel";
import { PARETO_OBJECTIVES } from "@lib/pareto";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

function row(values: number[]): Record<string, number> {
  const r: Record<string, number> = {};
  PARETO_OBJECTIVES.forEach((o, i) => {
    r[o] = values[i] ?? 0.5;
  });
  return r;
}

const front = [
  row([0.9, 0.2, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
  row([0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7]),
  row([0.2, 0.9, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
];

describe("ParetoParallel", () => {
  it("renders an honest empty state when there is no front (fast-path decision)", () => {
    render(<ParetoParallel front={[]} />);
    expect(screen.getByLabelText(/Pareto front not recorded/)).toBeInTheDocument();
    expect(screen.getByText(/fast-path decision/)).toBeInTheDocument();
  });

  it("renders one axis per objective with its label", () => {
    render(<ParetoParallel front={front} />);
    // Every objective short-label appears as an axis header.
    expect(screen.getByText("Demand")).toBeInTheDocument();
    expect(screen.getByText("Carbon")).toBeInTheDocument();
  });

  it("describes the front for screen readers (role=img)", () => {
    render(<ParetoParallel front={front} />);
    expect(
      screen.getByRole("img", {
        name: /Pareto front: 3 candidate decisions across 8 objectives/,
      }),
    ).toBeInTheDocument();
  });

  it("exposes the knee solution's values + weights as a screen-reader list (INV-CLR-011)", () => {
    // Two clear trade-offs; weighting route hard makes the route-strong row the
    // knee (no neutral objectives to pull it back to balance).
    const twoRow = [
      row([0.95, 0.2, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
      row([0.2, 0.95, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
    ];
    render(<ParetoParallel front={twoRow} weights={{ route_efficiency: 5 }} />);
    expect(screen.getByText(/Route: 0.95, objective weight 5.00/)).toBeInTheDocument();
  });

  it("honours an explicit kneeIndex override", () => {
    render(<ParetoParallel front={front} kneeIndex={0} />);
    // Knee row 0 has Demand 0.90.
    expect(screen.getByText(/Demand: 0.90/)).toBeInTheDocument();
  });

  it("accepts a className override", () => {
    const { container } = render(<ParetoParallel front={front} className="pp-marker" />);
    expect(container.firstElementChild?.className).toMatch(/pp-marker/);
  });
});
