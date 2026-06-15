import type { SloResponse, SloTier } from "@domain/operations";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SloBurnBoard } from "../SloBurnBoard";

function tier(severity: SloTier["severity"], fast: number | null, slow: number | null): SloTier {
  return {
    objective: 0.99,
    latency_target_s: 0.5,
    windows: {
      fast: { window: "1h", error_rate: fast, burn_rate: fast },
      slow: { window: "6h", error_rate: slow, burn_rate: slow },
    },
    budget_remaining_30d: null,
    severity,
  };
}

describe("SloBurnBoard (FE-INV-042)", () => {
  it("renders 'burn unknown' for every tier when Prometheus is unreachable, never green", () => {
    render(<SloBurnBoard data={undefined} isError={true} />);
    expect(screen.getByText(/source: unknown/)).toBeInTheDocument();
    // All four tiers read "burn unknown"; none reads "healthy".
    expect(screen.getAllByText(/burn unknown/)).toHaveLength(4);
    expect(screen.queryByText(/healthy/)).not.toBeInTheDocument();
  });

  it("shows fast + slow burn and the severity word for each tier", () => {
    const data: SloResponse = {
      ts: 0,
      source: "prometheus",
      tiers: {
        tier_1: tier("critical", 20, 8),
        tier_2: tier("warning", 2, 7),
        tier_3: tier("ok", 0, 0),
        tier_4: tier("ok", 0, 0),
      },
    };
    render(<SloBurnBoard data={data} isError={false} />);
    expect(screen.getByText(/critical/)).toBeInTheDocument();
    expect(screen.getByText(/burning/)).toBeInTheDocument();
    expect(screen.getAllByText(/healthy/)).toHaveLength(2);
    // Multi-window: both 1h and 6h burns rendered.
    expect(screen.getByText("1h 20.0×")).toBeInTheDocument();
    expect(screen.getByText("6h 8.0×")).toBeInTheDocument();
  });

  it("renders a null burn as '—', not a fabricated number", () => {
    const data: SloResponse = {
      ts: 0,
      source: "prometheus",
      tiers: { tier_1: tier("unknown", null, null) },
    };
    render(<SloBurnBoard data={data} isError={false} />);
    // tier_1 (explicit unknown) + the 3 unfilled tiers all read "—", never 0.
    expect(screen.getAllByText("1h —").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/1h 0\.0×/)).not.toBeInTheDocument();
  });
});
