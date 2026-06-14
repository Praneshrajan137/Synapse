import type { LiveDecision } from "@domain/decision-envelope";
import type { EscalationMessage } from "@domain/escalation";
import { SystemTrustTile } from "@ds/compounds";
import { useEscalationStore } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import { act, render, screen } from "@testing-library/react";
import type { SystemPosture } from "@transport/synapse-api";
import { beforeEach, describe, expect, it, vi } from "vitest";

const posture = vi.hoisted(() => ({
  current: {
    data: { degraded: false, breakers: {}, brownout: {} } as SystemPosture,
    isError: false,
  },
}));
vi.mock("@hooks/use-posture", () => ({ usePosture: () => posture.current }));

function decision(over: Partial<LiveDecision> = {}): LiveDecision {
  return {
    decision_id: crypto.randomUUID(),
    tier: "tier_1",
    confidence: 0.95,
    phase_reached: 1,
    escalated: false,
    selected_action: {},
    degraded: false,
    is_synthetic: false,
    agents: [],
    ...over,
  } as LiveDecision;
}

function seed(...ds: LiveDecision[]) {
  act(() => ds.forEach((d, i) => useFirehoseStore.getState().appendDecision(d, i + 1)));
}

describe("SystemTrustTile", () => {
  beforeEach(() => {
    useFirehoseStore.getState().flushAll();
    useEscalationStore.setState({ entries: [] });
    posture.current = {
      data: { degraded: false, breakers: {}, brownout: {} } as SystemPosture,
      isError: false,
    };
  });

  it("reads Standby with no live decisions", () => {
    render(<SystemTrustTile />);
    expect(screen.getByText("Standby")).toBeInTheDocument();
  });

  it("reads Autonomous when confident, un-escalated, healthy", () => {
    render(<SystemTrustTile />);
    seed(decision(), decision(), decision());
    expect(screen.getByText("Autonomous")).toBeInTheDocument();
  });

  it("reads Supervised when a decision awaits the operator", () => {
    render(<SystemTrustTile />);
    seed(decision());
    act(() =>
      useEscalationStore.getState().append({
        type: "escalation",
        decision_id: "11111111-1111-4111-8111-111111111111",
        confidence: 0.6,
        proposals: [],
        violations: [],
      } as EscalationMessage),
    );
    expect(screen.getByText("Supervised")).toBeInTheDocument();
  });

  it("reads Degraded when a circuit breaker is open", () => {
    posture.current = {
      data: { degraded: true, breakers: { demand: "open" }, brownout: {} } as SystemPosture,
      isError: false,
    };
    render(<SystemTrustTile />);
    seed(decision());
    expect(screen.getByText("Degraded")).toBeInTheDocument();
    expect(screen.getByText(/circuit breaker/)).toBeInTheDocument();
  });
});
