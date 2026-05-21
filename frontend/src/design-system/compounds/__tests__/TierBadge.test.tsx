import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TierBadge } from "@ds/compounds/TierBadge";

describe("TierBadge", () => {
  it("renders the tier label", () => {
    render(<TierBadge tier="tier_3" />);
    expect(screen.getByText("Tier 3")).toBeInTheDocument();
  });

  it("exposes the SLA in the accessible label", () => {
    render(<TierBadge tier="tier_2" />);
    const badge = screen.getByLabelText(/Tier 2/i);
    expect(badge).toBeInTheDocument();
  });
});
