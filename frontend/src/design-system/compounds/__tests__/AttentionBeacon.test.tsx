import type { EscalationMessage } from "@domain/escalation";
import { AttentionBeacon } from "@ds/compounds";
import { useAttentionAck } from "@state/attention.store";
import { useEscalationStore } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SystemPosture } from "@transport/synapse-api";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Isolate from the network: drive posture through a mock the tests control.
const posture = vi.hoisted(() => ({
  current: {
    data: { degraded: false, breakers: {}, brownout: {} } as SystemPosture,
    isError: false,
  },
}));
vi.mock("@hooks/use-posture", () => ({ usePosture: () => posture.current }));

function LocationProbe() {
  return <div data-testid="loc">{useLocation().pathname}</div>;
}

function wrapper(node: ReactNode) {
  return (
    <MemoryRouter initialEntries={["/"]}>
      {node}
      <LocationProbe />
    </MemoryRouter>
  );
}

function escalationMsg(id: string): EscalationMessage {
  return { type: "escalation", decision_id: id, confidence: 0.6, proposals: [], violations: [] };
}

describe("AttentionBeacon", () => {
  beforeEach(() => {
    useEscalationStore.setState({ entries: [] });
    useFirehoseStore.getState().flushAll();
    useAttentionAck.getState().reset();
    posture.current = {
      data: { degraded: false, breakers: {}, brownout: {} } as SystemPosture,
      isError: false,
    };
  });
  afterEach(() => vi.clearAllMocks());

  it("reads 'All clear' when nothing needs attention", () => {
    render(wrapper(<AttentionBeacon />));
    expect(screen.getByText(/All clear/)).toBeInTheDocument();
  });

  it("surfaces a pending escalation and routes to the cockpit when opened", async () => {
    const user = userEvent.setup();
    useEscalationStore.getState().append(escalationMsg("11111111-1111-4111-8111-111111111111"));
    render(wrapper(<AttentionBeacon />));

    expect(screen.getByText(/1 needs you/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { expanded: false }));
    await user.click(screen.getByText(/1 decision awaits you/));
    expect(screen.getByTestId("loc")).toHaveTextContent("/cockpit");
  });

  it("lets the operator acknowledge an informational degradation", async () => {
    const user = userEvent.setup();
    posture.current = {
      data: { degraded: true, breakers: { demand: "open" }, brownout: {} } as SystemPosture,
      isError: false,
    };
    render(wrapper(<AttentionBeacon />));

    await user.click(screen.getByRole("button", { expanded: false }));
    expect(within(screen.getByRole("menu")).getByText(/circuit breaker/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Acknowledge/ }));
    // Once acked, the degradation is gone and the beacon falls back to All clear.
    expect(screen.getByText(/All clear/)).toBeInTheDocument();
  });
});
