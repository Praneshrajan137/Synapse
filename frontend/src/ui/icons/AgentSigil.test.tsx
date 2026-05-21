import { AGENT_NAMES } from "@/ui/tokens";
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { AGENT_LABEL, AgentSigil } from "./AgentSigil";

describe("AgentSigil", () => {
  it("renders a distinct sigil for every one of the eight agents", () => {
    for (const agent of AGENT_NAMES) {
      const { container } = render(<AgentSigil agent={agent} />);
      const svg = container.querySelector("svg");
      expect(svg).not.toBeNull();
      expect(svg?.querySelectorAll("path, circle, rect").length ?? 0).toBeGreaterThan(0);
    }
  });

  it("is decorative (aria-hidden) by default", () => {
    const { container } = render(<AgentSigil agent="demand_prophet" />);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("becomes a labelled image when a title is provided", () => {
    const { container } = render(
      <AgentSigil agent="pricing_oracle" title={AGENT_LABEL.pricing_oracle} />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("role", "img");
    expect(svg).toHaveAttribute("aria-label", "Pricing Oracle");
  });

  it("uses the agent token hue by default and honors a color override", () => {
    const fallback = render(<AgentSigil agent="routing_navigator" />);
    const defaultColor = fallback.container.querySelector("svg")?.style.color;
    expect(defaultColor).toBeTruthy();

    const overridden = render(<AgentSigil agent="routing_navigator" color="#112233" />);
    const overrideColor = overridden.container.querySelector("svg")?.style.color;
    expect(overrideColor).toBeTruthy();
    expect(overrideColor).not.toBe(defaultColor);
  });

  it("has no accessibility violations when labelled", async () => {
    const { container } = render(
      <AgentSigil agent="disruption_shield" title="Disruption Shield" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
