import type { EscalationMessage } from "@domain/escalation";
import { CatchUpBanner } from "@ds/compounds";
import { useEscalationStore } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  act(() => document.dispatchEvent(new Event("visibilitychange")));
}

function escalate(id: string) {
  act(() =>
    useEscalationStore.getState().append({
      type: "escalation",
      decision_id: id,
      confidence: 0.6,
      proposals: [],
      violations: [],
    } as EscalationMessage),
  );
}

describe("CatchUpBanner", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useEscalationStore.setState({ entries: [] });
    useFirehoseStore.getState().flushAll();
  });
  afterEach(() => {
    vi.useRealTimers();
    setHidden(false);
  });

  it("summarises what arrived during a real absence", () => {
    render(
      <MemoryRouter>
        <CatchUpBanner />
      </MemoryRouter>,
    );
    setHidden(true);
    vi.advanceTimersByTime(31_000);
    escalate("11111111-1111-4111-8111-111111111111");
    setHidden(false);

    expect(screen.getByText(/While you were away/)).toBeInTheDocument();
    expect(screen.getByText(/1 new escalation/)).toBeInTheDocument();
  });

  it("stays silent for a blink-away under the threshold", () => {
    render(
      <MemoryRouter>
        <CatchUpBanner />
      </MemoryRouter>,
    );
    setHidden(true);
    vi.advanceTimersByTime(5_000);
    escalate("22222222-2222-4222-8222-222222222222");
    setHidden(false);

    expect(screen.queryByText(/While you were away/)).not.toBeInTheDocument();
  });
});
