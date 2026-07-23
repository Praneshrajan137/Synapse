import type { WorldVital } from "@lib/autonomy";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorldVitals } from "../WorldVitals";
// Bootstrap i18n so world.* copy resolves.
import "@i18n/index";

function vital(over: Partial<WorldVital> = {}): WorldVital {
  return {
    city: "bengaluru",
    kind: "live",
    synthetic: true,
    fillRate: 0.97,
    spoilageRate: 0.01,
    pendingOrders: 2,
    demandRate: 1.2,
    restocks: 4,
    simTimeMin: 120,
    skuCount: 2,
    ...over,
  };
}

describe("WorldVitals", () => {
  it("labels a live world as a simulation and shows its vitals", () => {
    render(<WorldVitals worlds={[vital()]} />);
    expect(screen.getByText(/simulated world/i)).toBeInTheDocument();
    // fill rate rendered as a percentage.
    expect(screen.getByText("97%")).toBeInTheDocument();
  });

  it("renders a stalled world as degraded, not as healthy vitals", () => {
    render(<WorldVitals worlds={[vital({ kind: "stalled", fillRate: null })]} />);
    expect(screen.getByText(/world clock stalled/i)).toBeInTheDocument();
    // No fabricated vitals for a stalled world.
    expect(screen.queryByText("97%")).not.toBeInTheDocument();
  });

  it("renders an unreachable world honestly", () => {
    render(<WorldVitals worlds={[vital({ kind: "unreachable", fillRate: null })]} />);
    expect(screen.getByText(/world unreachable/i)).toBeInTheDocument();
  });
});
