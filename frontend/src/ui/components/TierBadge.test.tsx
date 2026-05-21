import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { TierBadge } from "./TierBadge";

describe("TierBadge", () => {
  it("renders the short tier label", () => {
    render(<TierBadge tier="tier_3" />);
    expect(screen.getByText("T3")).toBeInTheDocument();
  });

  it("appends the latency budget when asked", () => {
    render(<TierBadge tier="tier_1" showLatency />);
    expect(screen.getByText(/<100ms/)).toBeInTheDocument();
  });

  it("describes the tier in its title for hover context", () => {
    render(<TierBadge tier="tier_4" />);
    expect(screen.getByTitle(/Monte Carlo/)).toBeInTheDocument();
  });

  it("has no accessibility violations across all four tiers", async () => {
    const { container } = render(
      <div>
        <TierBadge tier="tier_1" />
        <TierBadge tier="tier_2" />
        <TierBadge tier="tier_3" />
        <TierBadge tier="tier_4" showLatency />
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
