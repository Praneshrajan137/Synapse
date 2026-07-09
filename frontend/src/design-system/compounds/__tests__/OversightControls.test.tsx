// Unit tests for the OversightControls compound (task 7.6).
//
// Covers the three behavioural guarantees the property tests cannot reach
// because they live in the rendering + effect layer:
//
//   - Audit-row-first commits for override AND steering (Req 3.1, 3.6):
//     the audit endpoint must succeed before the decision is marked acted /
//     the steering value is applied.
//   - Revert-on-failure (Req 3.6): a failed steering audit commit reverts the
//     value and surfaces an error; a failed override leaves the decision
//     un-acted (Req 3.1).
//   - WS-ack-is-not-commit (Req 3.1): while the audit POST is in flight the
//     decision stays pending — only the HTTP 2xx (not a WebSocket ack) commits.
//   - Full keyboard operability of every oversight action (Req 3.3): every
//     action is reachable and activatable without a pointer.
//
// The override mutation runs for real (audit-row-first by construction) with
// only its transport (`useSynapseApi`) mocked, so the ordering guarantee is
// exercised end to end. The steering store runs for real with a controllable
// audit writer. React Testing Library + Vitest.

import type { EscalationMessage } from "@domain/escalation";
import { OversightControls } from "@ds/compounds/OversightControls";
import { useEscalationStore } from "@state/escalation.store";
import {
  DEFAULT_PARETO_WEIGHTS,
  DEFAULT_TIER_THRESHOLDS,
  setSteeringWriter,
  useSteeringStore,
} from "@state/steering.store";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock only the transport: the audit-row-first override mutation itself runs
// for real so we can prove the commit ordering.
const submitOverrideMock = vi.hoisted(() => vi.fn());
vi.mock("@hooks/use-synapse-api", () => ({
  useSynapseApi: () => ({ submitOverride: submitOverrideMock }),
}));

// sonner renders to a portal we don't mount; stub to keep tests quiet.
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}));

const DECISION_ID = "11111111-1111-4111-8111-111111111111";

function wrapper(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

/** Seed a pending escalation entry whose id matches the decision under review. */
function seedPendingEscalation(): void {
  act(() =>
    useEscalationStore.getState().append({
      type: "escalation",
      decision_id: DECISION_ID,
      confidence: 0.6,
      proposals: [],
      violations: [],
    } as EscalationMessage),
  );
}

function entryStatus(): string | undefined {
  return useEscalationStore.getState().entries.find((e) => e.id === DECISION_ID)?.status;
}

beforeEach(() => {
  submitOverrideMock.mockReset();
  // Reset the real stores between tests.
  useEscalationStore.setState({ entries: [], connected: false });
  useSteeringStore.setState({
    paretoWeights: DEFAULT_PARETO_WEIGHTS,
    tierThresholds: DEFAULT_TIER_THRESHOLDS,
    lastError: null,
  });
  // Default steering writer: succeeds. Individual tests override it.
  setSteeringWriter(async () => undefined);
});

afterEach(() => {
  setSteeringWriter(async () => undefined);
});

describe("OversightControls — full keyboard operability (Req 3.3)", () => {
  it("exposes an aria-keyshortcut on every oversight action", () => {
    render(
      wrapper(
        <OversightControls operatorRole="ops" decisionConfidence={0.95} decisionId={DECISION_ID} />,
      ),
    );

    // Override actions.
    for (const [action, key] of [
      ["approve", "A"],
      ["reject", "R"],
      ["modify", "M"],
    ] as const) {
      const btn = document.querySelector(`[data-action="${action}"]`);
      expect(btn?.getAttribute("aria-keyshortcuts")).toBe(key);
    }

    // Secondary authority actions + steering.
    for (const [cap, key] of [
      ["interrupt", "I"],
      ["recover", "C"],
      ["delegate", "D"],
      ["escalate-prev", "K"],
      ["escalate-next", "J"],
      ["dismiss", "Escape"],
    ] as const) {
      const btn = document.querySelector(`[data-capability="${cap}"]`);
      expect(btn?.getAttribute("aria-keyshortcuts")).toBe(key);
    }
    expect(screen.getByLabelText(/Steer/).getAttribute("aria-keyshortcuts")).toBe("S");
  });

  it("activates approve/reject/modify by keyboard alone (no pointer)", async () => {
    submitOverrideMock.mockResolvedValue({ audit_escalation_id: 1 });
    render(
      wrapper(
        <OversightControls operatorRole="ops" decisionConfidence={0.95} decisionId={DECISION_ID} />,
      ),
    );

    fireEvent.keyDown(document.body, { key: "a" });
    await waitFor(() =>
      expect(submitOverrideMock).toHaveBeenCalledWith(
        DECISION_ID,
        expect.objectContaining({ action: "approved" }),
      ),
    );

    fireEvent.keyDown(document.body, { key: "r" });
    await waitFor(() =>
      expect(submitOverrideMock).toHaveBeenCalledWith(
        DECISION_ID,
        expect.objectContaining({ action: "rejected" }),
      ),
    );

    fireEvent.keyDown(document.body, { key: "m" });
    await waitFor(() =>
      expect(submitOverrideMock).toHaveBeenCalledWith(
        DECISION_ID,
        expect.objectContaining({ action: "modified" }),
      ),
    );
  });

  it("routes escalate-next/prev and dismiss to their handlers by keyboard", () => {
    const onEscalateNext = vi.fn();
    const onEscalatePrev = vi.fn();
    const onDismiss = vi.fn();
    render(
      wrapper(
        <OversightControls
          operatorRole="ops"
          decisionConfidence={0.95}
          decisionId={DECISION_ID}
          onEscalateNext={onEscalateNext}
          onEscalatePrev={onEscalatePrev}
          onDismiss={onDismiss}
        />,
      ),
    );

    fireEvent.keyDown(document.body, { key: "j" });
    fireEvent.keyDown(document.body, { key: "k" });
    fireEvent.keyDown(document.body, { key: "Escape" });

    expect(onEscalateNext).toHaveBeenCalledTimes(1);
    expect(onEscalatePrev).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("keeps a viewer's controls keyboard-inert (shortcuts disarmed, Req 3.9)", () => {
    render(
      wrapper(
        <OversightControls
          operatorRole="viewer"
          decisionConfidence={0.95}
          decisionId={DECISION_ID}
        />,
      ),
    );
    fireEvent.keyDown(document.body, { key: "a" });
    expect(submitOverrideMock).not.toHaveBeenCalled();
    // Controls are present but disabled — never hidden.
    expect(document.querySelector('[data-action="approve"]')).toBeDisabled();
    expect(screen.getByText(/read-only/)).toBeInTheDocument();
  });
});

describe("OversightControls — audit-row-first override (Req 3.1)", () => {
  it("does not mark the decision acted until the audit POST resolves (WS-ack-is-not-commit)", async () => {
    let resolveOverride: ((v: { audit_escalation_id: number }) => void) | undefined;
    submitOverrideMock.mockImplementation(
      () =>
        new Promise<{ audit_escalation_id: number }>((res) => {
          resolveOverride = res;
        }),
    );
    seedPendingEscalation();
    render(
      wrapper(
        <OversightControls operatorRole="ops" decisionConfidence={0.95} decisionId={DECISION_ID} />,
      ),
    );

    fireEvent.click(screen.getByText("Approve"));

    // Audit POST is in flight — the decision must stay pending. A WebSocket
    // ack arriving now would be operational confirmation only, never the commit.
    await waitFor(() => expect(submitOverrideMock).toHaveBeenCalledTimes(1));
    expect(entryStatus()).toBe("pending");

    // Audit row commits (HTTP 2xx) → only now is the decision marked acted.
    await act(async () => {
      resolveOverride?.({ audit_escalation_id: 42 });
    });
    await waitFor(() => expect(entryStatus()).toBe("acted"));
    expect(useEscalationStore.getState().entries[0]?.acted_action).toBe("approved");
  });

  it("leaves the decision un-acted when the audit commit fails", async () => {
    submitOverrideMock.mockRejectedValue(new Error("audit insert failed"));
    seedPendingEscalation();
    render(
      wrapper(
        <OversightControls operatorRole="ops" decisionConfidence={0.95} decisionId={DECISION_ID} />,
      ),
    );

    fireEvent.click(screen.getByText("Approve"));

    await waitFor(() => expect(submitOverrideMock).toHaveBeenCalledTimes(1));
    // The commit failed, so the decision is never marked acted.
    await waitFor(() => expect(entryStatus()).toBe("pending"));
  });
});

describe("OversightControls — audit-row-first steering (Req 3.6, 3.7)", () => {
  it("applies the steering value after the audit writer resolves", async () => {
    const writer = vi.fn(async () => undefined);
    setSteeringWriter(writer);
    render(
      wrapper(
        <OversightControls operatorRole="ops" decisionConfidence={0.95} steeringTarget="cost" />,
      ),
    );

    const slider = screen.getByLabelText(/Steer/);
    fireEvent.change(slider, { target: { value: "0.6" } });

    await waitFor(() => expect(writer).toHaveBeenCalledTimes(1));
    // Audit-row-first: the writer receives the clamped value.
    expect(writer).toHaveBeenCalledWith(
      expect.objectContaining({ action: "set_pareto_weight", target: "cost", value: 0.6 }),
    );
    await waitFor(() => expect(useSteeringStore.getState().paretoWeights.cost).toBe(0.6));
    expect(useSteeringStore.getState().lastError).toBeNull();
  });

  it("reverts the value and surfaces an error when the audit commit fails", async () => {
    const before = useSteeringStore.getState().paretoWeights.cost;
    setSteeringWriter(async () => {
      throw new Error("steering audit rejected");
    });
    render(
      wrapper(
        <OversightControls operatorRole="ops" decisionConfidence={0.95} steeringTarget="cost" />,
      ),
    );

    const slider = screen.getByLabelText(/Steer/);
    fireEvent.change(slider, { target: { value: "0.9" } });

    // The optimistic value is rolled back to the pre-adjustment weight.
    await waitFor(() => expect(useSteeringStore.getState().paretoWeights.cost).toBe(before));
    expect(useSteeringStore.getState().lastError).toBe("steering audit rejected");
    // The failure is communicated, not silent.
    expect(await screen.findByText(/Steering change not applied/)).toBeInTheDocument();
  });
});
