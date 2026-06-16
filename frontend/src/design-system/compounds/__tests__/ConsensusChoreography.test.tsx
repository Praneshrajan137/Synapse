import type { ConsensusDecision } from "@domain/consensus-decision";
import { ConsensusChoreography } from "@ds/compounds/ConsensusChoreography";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DecisionDetailResponse } from "@transport/synapse-api";
import { beforeEach, describe, expect, it, vi } from "vitest";
// i18next global bootstrap (registers the "common" namespace).
import "@i18n/index";

// Control framer's reduced-motion read so we can exercise BOTH the narrated
// player and the static all-phases reveal (FE-INV-046). The jsdom matchMedia
// stub always reports matches:false, so we override the hook directly.
const motionState = vi.hoisted(() => ({ reduced: false }));
vi.mock("framer-motion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("framer-motion")>();
  return { ...actual, useReducedMotion: () => motionState.reduced };
});

function decision(overrides: Partial<ConsensusDecision> = {}): ConsensusDecision {
  return {
    decision_id: "11111111-1111-4111-8111-111111111111",
    timestamp: "2026-06-16T10:00:00.000Z",
    tier: "tier_3",
    proposals: [
      { agent_name: "demand_prophet", utility_score: 0.81, confidence: 0.88, status: "selected" },
      { agent_name: "pricing_oracle", utility_score: 0.62, confidence: 0.74, status: "proposed" },
    ],
    selected_action: { reorder_qty: 120, store_id: "store_blr_003" },
    pareto_weights: { cost: 0.4, time: 0.3, sustainability: 0.3 },
    confidence: 0.82,
    escalated_to_human: false,
    human_override: null,
    audit_trace: ["t1: collected", "t2: debated", "t3: arbitrated", "t4: executed"],
    phase_reached: 5,
    debate_rounds: 2,
    pareto_front: [
      { cost: 0.4, time: 0.3, sustainability: 0.3 },
      { cost: 0.5, time: 0.2, sustainability: 0.3 },
    ],
    context_messages: [
      { agent_name: "demand_prophet", content: "Forecast spike for SKU eggs." },
      { agent_name: "pricing_oracle", content: "Margin holds under 1.2x." },
    ],
    execution_confirmations: ["ok: store acked", "ok: kafka published"],
    audit_id: null,
    ...overrides,
  };
}

const fastPath = decision({
  decision_id: "22222222-2222-4222-8222-222222222222",
  tier: "tier_1",
  phase_reached: 4,
  debate_rounds: 0,
  pareto_front: null,
  context_messages: [],
  execution_confirmations: ["ok: fast path executed"],
});

beforeEach(() => {
  motionState.reduced = false;
});

describe("ConsensusChoreography", () => {
  it("labels itself a recorded reconstruction, never live (FE-INV-047)", () => {
    render(<ConsensusChoreography decision={decision()} autoPlay={false} />);
    expect(screen.getByText(/recorded reconstruction/i)).toBeInTheDocument();
    expect(screen.queryByText(/\blive\b/i)).not.toBeInTheDocument();
  });

  it("marks a synthetic decision with the SyntheticBadge (FE-INV-047)", () => {
    render(
      <ConsensusChoreography
        decision={decision()}
        raw={{ is_synthetic: true } as unknown as DecisionDetailResponse}
        autoPlay={false}
      />,
    );
    expect(screen.getByText(/demo/i)).toBeInTheDocument();
  });

  it("renders the collected proposals at phase 1", () => {
    render(<ConsensusChoreography decision={decision()} autoPlay={false} initialPhase={1} />);
    expect(screen.getByLabelText(/Agent proposal constellation/i)).toBeInTheDocument();
    // AgentProposalChip shows the utility to three decimals.
    expect(screen.getByText("0.810")).toBeInTheDocument();
  });

  it("shows the recorded debate transcript when the row has debate rounds", () => {
    render(<ConsensusChoreography decision={decision()} autoPlay={false} initialPhase={2} />);
    expect(screen.getByText(/Forecast spike for SKU eggs/)).toBeInTheDocument();
  });

  it("honestly shows 'no debate' on a fast path, never a fabricated transcript (FE-INV-045)", () => {
    render(<ConsensusChoreography decision={fastPath} autoPlay={false} initialPhase={2} />);
    expect(screen.getByText(/no debate/i)).toBeInTheDocument();
    expect(screen.getByText(/fast path/i)).toBeInTheDocument();
    expect(screen.queryByText(/Forecast spike/)).not.toBeInTheDocument();
  });

  it("steps phases via the scrubber controls (the index drives the slice)", async () => {
    const user = userEvent.setup();
    render(<ConsensusChoreography decision={decision()} autoPlay={false} initialPhase={1} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuenow", "1");
    await user.click(screen.getByLabelText(/Next phase/));
    expect(slider).toHaveAttribute("aria-valuenow", "2");
  });

  it("under reduced motion reveals every phase statically with no player (FE-INV-046)", () => {
    motionState.reduced = true;
    render(<ConsensusChoreography decision={decision()} />);
    expect(screen.getByText(/Reduced motion/i)).toBeInTheDocument();
    // No transport controls in the static reveal…
    expect(screen.queryByRole("button", { name: /play|pause|replay/i })).toBeNull();
    expect(screen.queryByRole("slider")).toBeNull();
    // …and all phases' content is present at once (text carries every state).
    expect(screen.getByText(/Proposals collected/)).toBeInTheDocument();
    expect(screen.getByText(/Forecast spike for SKU eggs/)).toBeInTheDocument();
    expect(screen.getByText(/Execution confirmations/)).toBeInTheDocument();
    expect(screen.getByText(/No realized outcome scored yet/)).toBeInTheDocument();
  });

  it("renders the scored outcome tri-state when the row carries one (unknown ≠ confirmed)", () => {
    render(
      <ConsensusChoreography
        decision={decision()}
        raw={{ outcome: { status: "unknown" } } as unknown as DecisionDetailResponse}
        autoPlay={false}
        initialPhase={5}
      />,
    );
    expect(screen.getByText(/not yet realized/i)).toBeInTheDocument();
    expect(screen.queryByText(/played out as decided/i)).not.toBeInTheDocument();
  });
});
