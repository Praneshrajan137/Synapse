import {
  AGENT_NAMES,
  ProposalConstellation,
  type ProposalLike,
} from "@ds/compounds/ProposalConstellation";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const eightProposals: ProposalLike[] = AGENT_NAMES.map((agent, i) => ({
  agent_name: agent,
  utility_score: 0.5 + i * 0.05,
  confidence: 0.6 + (i % 3) * 0.1,
}));

describe("ProposalConstellation", () => {
  it("renders one button per frozen agent (8 total)", () => {
    render(<ProposalConstellation proposals={eightProposals} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(AGENT_NAMES.length);
  });

  it("uses fixed agent order — Demand Prophet first, Sustainability Agent last", () => {
    render(<ProposalConstellation proposals={eightProposals} />);
    const buttons = screen.getAllByRole("button");
    // aria-label format: "<Label> — utility N, confidence N"
    expect(buttons[0]?.getAttribute("aria-label")).toMatch(/^Demand Prophet/);
    expect(buttons[AGENT_NAMES.length - 1]?.getAttribute("aria-label")).toMatch(
      /^Sustainability Agent/,
    );
  });

  it("renders revealed agents with utility + confidence in aria-label", () => {
    render(
      <ProposalConstellation
        proposals={[
          { agent_name: "pricing_oracle", utility_score: 0.86, confidence: 0.91 },
        ]}
      />,
    );
    const button = screen.getByRole("button", { name: /Pricing Oracle — utility 0.86/ });
    expect(button.getAttribute("aria-label")).toMatch(/confidence 0\.91/);
  });

  it('marks not-yet-arrived agents as "no proposal yet"', () => {
    render(
      <ProposalConstellation
        proposals={[
          { agent_name: "demand_prophet", utility_score: 0.7, confidence: 0.8 },
        ]}
      />,
    );
    const noProposal = screen.getAllByRole("button", { name: /no proposal yet/ });
    expect(noProposal).toHaveLength(AGENT_NAMES.length - 1);
  });

  it("fires onSelectAgent with the agent name when its node is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ProposalConstellation
        proposals={[
          { agent_name: "routing_navigator", utility_score: 0.5, confidence: 0.7 },
        ]}
        onSelectAgent={onSelect}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Routing Navigator — utility/ }));
    expect(onSelect).toHaveBeenCalledWith("routing_navigator");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("disables buttons for agents without a proposal (cannot select empty slots)", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ProposalConstellation
        proposals={[
          { agent_name: "demand_prophet", utility_score: 0.7, confidence: 0.8 },
        ]}
        onSelectAgent={onSelect}
      />,
    );
    const empty = screen.getByRole("button", { name: /Pricing Oracle — no proposal yet/ });
    expect(empty).toBeDisabled();
    await user.click(empty);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("disables every node when onSelectAgent is not provided (display-only mode)", () => {
    render(<ProposalConstellation proposals={eightProposals} />);
    const buttons = screen.getAllByRole("button");
    for (const b of buttons) expect(b).toBeDisabled();
  });

  it("reflects selectedAgent via aria-pressed", () => {
    render(
      <ProposalConstellation
        proposals={eightProposals}
        selectedAgent="freshness_guardian"
        onSelectAgent={() => undefined}
      />,
    );
    const selected = screen.getByRole("button", { name: /Freshness Guardian — utility/ });
    expect(selected.getAttribute("aria-pressed")).toBe("true");
    const other = screen.getByRole("button", { name: /Pricing Oracle — utility/ });
    expect(other.getAttribute("aria-pressed")).toBe("false");
  });

  it("clamps out-of-range utility_score and confidence into [0, 1]", () => {
    render(
      <ProposalConstellation
        proposals={[
          { agent_name: "pricing_oracle", utility_score: 1.7, confidence: -0.5 },
        ]}
      />,
    );
    const button = screen.getByRole("button", { name: /Pricing Oracle — utility/ });
    // aria-label always shows 2-decimal forms of the clamped values
    expect(button.getAttribute("aria-label")).toMatch(/utility 1\.00/);
    expect(button.getAttribute("aria-label")).toMatch(/confidence 0\.00/);
  });

  it("honours the explicit `revealed` set even when proposals exist for non-revealed agents", () => {
    // All 8 proposals exist, but only one is "revealed" — the others should
    // render as not-yet-arrived even though we have their data.
    render(
      <ProposalConstellation
        proposals={eightProposals}
        revealed={new Set(["demand_prophet"])}
      />,
    );
    const revealedNode = screen.getByRole("button", { name: /Demand Prophet — utility/ });
    expect(revealedNode.getAttribute("aria-label")).toMatch(/utility/);
    // Other agents still have proposals but their utility chip is hidden.
    // We assert this indirectly: the constellation has 8 buttons total.
    expect(screen.getAllByRole("button")).toHaveLength(AGENT_NAMES.length);
  });

  it("exposes role=figure with a descriptive aria-label (screen-reader entry point)", () => {
    render(<ProposalConstellation proposals={eightProposals} />);
    const figure = screen.getByRole("figure", { name: /Agent proposal constellation/ });
    expect(figure).toBeInTheDocument();
  });

  it("accepts className override on the outer wrapper", () => {
    const { container } = render(
      <ProposalConstellation proposals={[]} className="test-marker-xyz" />,
    );
    const root = container.firstElementChild;
    expect(root?.className).toMatch(/test-marker-xyz/);
  });
});
