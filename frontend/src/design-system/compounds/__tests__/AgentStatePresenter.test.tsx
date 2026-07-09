import { agentStateDescriptor } from "@domain/agent-state";
import { AgentStatePresenter } from "@ds/compounds/AgentStatePresenter";
import { agentColorVar } from "@lib/agent-identity";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("AgentStatePresenter — live states", () => {
  it("renders the status word, glyph, and data-agent-state attr (non-colour channels, Req 2.4)", () => {
    render(
      <AgentStatePresenter
        state={{
          kind: "live",
          descriptor: agentStateDescriptor("acting"),
          hue: agentColorVar("demand_prophet"),
        }}
        agent="demand_prophet"
      />,
    );
    // Status word (non-colour channel).
    expect(screen.getByText("Acting")).toBeInTheDocument();
    // Accessible label carries the agent identity + status word.
    const el = screen.getByLabelText("Demand Prophet: Acting");
    // data-agent-state attribute (non-colour channel).
    expect(el.getAttribute("data-agent-state")).toBe("acting");
  });

  it("paints the frozen identity hue with chroma rationed toward the neutral base (Req 2.5/2.7)", () => {
    const { container } = render(
      <AgentStatePresenter
        state={{
          kind: "live",
          descriptor: agentStateDescriptor("interrupting"),
          hue: agentColorVar("pricing_oracle"),
        }}
        agent="pricing_oracle"
      />,
    );
    const dot = container.querySelector("[aria-hidden='true']") as HTMLElement;
    // Token-only colour: references the agent hue var + the neutral mix, no raw literal.
    expect(dot.style.background).toContain(agentColorVar("pricing_oracle"));
    expect(dot.style.background).toContain("var(--syn-neutral-mix)");
    // interrupting floor factor 0.25 → 25% identity share (chroma > 0, Req 2.7).
    expect(dot.style.background).toContain("25%");
  });

  it("does not render a raw colour literal (INV-CLR-009)", () => {
    const { container } = render(
      <AgentStatePresenter
        state={{
          kind: "live",
          descriptor: agentStateDescriptor("thinking"),
          hue: agentColorVar("routing_navigator"),
        }}
      />,
    );
    expect(container.innerHTML).not.toMatch(/#[0-9a-f]{3,8}/i);
  });
});

describe("AgentStatePresenter — honest non-live markers", () => {
  it("renders an explicit non-colour 'unavailable' marker (Req 2.3)", () => {
    render(<AgentStatePresenter state={{ kind: "unavailable", reason: "no-backend-event" }} />);
    const el = screen.getByLabelText("unavailable");
    expect(screen.getByText("unavailable")).toBeInTheDocument();
    expect(el.getAttribute("data-agent-state")).toBe("unavailable");
  });

  it("renders an explicit non-colour 'not-live' marker when the stream is stale (Req 2.6)", () => {
    render(
      <AgentStatePresenter state={{ kind: "not-live", sinceMs: 1_000 }} agent="supplier_trust" />,
    );
    const el = screen.getByLabelText("Supplier Trust: not-live");
    expect(screen.getByText("not-live")).toBeInTheDocument();
    expect(el.getAttribute("data-agent-state")).toBe("not-live");
  });

  it("never paints an identity hue for a non-live marker (never shows a frozen state as active)", () => {
    const { container } = render(<AgentStatePresenter state={{ kind: "not-live", sinceMs: 0 }} />);
    const dot = container.querySelector("[aria-hidden='true']") as HTMLElement;
    expect(dot.style.background).toBe("");
  });
});
