import type { ConsensusDecision } from "@domain/consensus-decision";
import { CouncilTheater } from "@surfaces/council-theater/CouncilTheater";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
// i18next global bootstrap (registers the "common" namespace).
import "@i18n/index";

// The surface is exercised through the shared decision hook; mock it so we
// control loading / error / success without a transport or QueryClient.
const queryState = vi.hoisted(() => ({
  value: {} as {
    isLoading?: boolean;
    isError?: boolean;
    error?: unknown;
    data?: { decision: ConsensusDecision; raw: undefined } | undefined;
  },
}));
vi.mock("@hooks/use-decision", () => ({
  useDecisionQuery: () => queryState.value,
}));

const DECISION_ID = "11111111-1111-4111-8111-111111111111";

function fixtureDecision(): ConsensusDecision {
  return {
    decision_id: DECISION_ID,
    timestamp: "2026-06-16T10:00:00.000Z",
    tier: "tier_3",
    proposals: [{ agent_name: "demand_prophet", utility_score: 0.81, confidence: 0.88 }],
    selected_action: { reorder_qty: 120 },
    pareto_weights: { cost: 0.5, time: 0.5 },
    confidence: 0.82,
    escalated_to_human: false,
    human_override: null,
    audit_trace: ["t1: collected"],
    phase_reached: 5,
    debate_rounds: 1,
    pareto_front: [{ cost: 0.5, time: 0.5 }],
    context_messages: [{ agent_name: "demand_prophet", content: "Forecast spike." }],
    execution_confirmations: ["ok: acked"],
    audit_id: null,
  };
}

function renderAt(ui: ReactNode, id = DECISION_ID) {
  return render(
    <MemoryRouter initialEntries={[`/council/${id}`]}>
      <Routes>
        <Route path="/council/:id" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  queryState.value = {};
});

describe("CouncilTheater surface", () => {
  it("shows a loading state while the decision is in flight", () => {
    queryState.value = { isLoading: true };
    renderAt(<CouncilTheater />);
    expect(screen.getByText(/Loading deliberation/)).toBeInTheDocument();
  });

  it("surfaces an explicit error, never a silent empty stage", () => {
    queryState.value = { isLoading: false, isError: true, error: new Error("not found") };
    renderAt(<CouncilTheater />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/Decision unavailable/);
    expect(alert).toHaveTextContent(/not found/);
  });

  it("renders the choreography and a deep-link back to the analyst detail", () => {
    queryState.value = {
      isLoading: false,
      isError: false,
      data: { decision: fixtureDecision(), raw: undefined },
    };
    renderAt(<CouncilTheater />);
    expect(screen.getByRole("heading", { level: 1, name: "Council Theater" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Consensus deliberation reconstruction/i)).toBeInTheDocument();
    const back = screen.getByRole("link", { name: /Decision detail/ });
    expect(back).toHaveAttribute("href", `/decisions/${DECISION_ID}`);
  });
});
