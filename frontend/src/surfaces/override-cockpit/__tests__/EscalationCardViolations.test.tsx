import type { EscalationMessage } from "@domain/escalation";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EscalationCard } from "../EscalationCard";

// FE-INV-038: every guardrail violation renders with its severity — the
// operator overriding a guardrail must see exactly WHICH constraints fired
// and how hard, never a bare count with the first message.

function message(violations: EscalationMessage["violations"]): EscalationMessage {
  return {
    type: "escalation",
    decision_id: "11111111-1111-4111-8111-111111111111",
    tier: "tier_3",
    confidence: 0.55,
    proposals: [],
    recommended_action: {},
    violations,
    reason: "guardrail",
  };
}

describe("EscalationCard — violations (FE-INV-038)", () => {
  it("renders EVERY violation with code, message, and severity", () => {
    render(
      <EscalationCard
        message={message([
          {
            code: "PRICE_CAP",
            message: "Essential multiplier 1.4 exceeds 1.3x",
            severity: "critical",
          },
          { code: "STOCK_FLOOR", message: "Safety stock below floor", severity: "medium" },
          { code: "ROUTE_SLA", message: "Route exceeds freshness window", severity: "low" },
        ])}
        receivedAt={Date.now()}
        pending={true}
        onCommit={vi.fn()}
      />,
    );
    const section = screen.getByLabelText("Guardrail violations");
    expect(section).toHaveTextContent("PRICE_CAP");
    expect(section).toHaveTextContent("Essential multiplier 1.4 exceeds 1.3x");
    expect(section).toHaveTextContent("critical");
    expect(section).toHaveTextContent("STOCK_FLOOR");
    expect(section).toHaveTextContent("medium");
    expect(section).toHaveTextContent("ROUTE_SLA");
    expect(section).toHaveTextContent("low");
  });

  it("a missing severity defaults to medium rather than disappearing", () => {
    render(
      <EscalationCard
        message={message([{ code: "X", message: "no severity attached" }])}
        receivedAt={Date.now()}
        pending={true}
        onCommit={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Guardrail violations")).toHaveTextContent("medium");
  });

  it("no violations section when the escalation carries none", () => {
    render(
      <EscalationCard
        message={message([])}
        receivedAt={Date.now()}
        pending={true}
        onCommit={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText("Guardrail violations")).not.toBeInTheDocument();
  });
});
