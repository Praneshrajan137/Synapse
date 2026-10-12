import type { LiveDecision } from "@domain/decision-envelope";
import type { UseFirehoseResult } from "@hooks/use-firehose";
import { useFirehoseStore } from "@state/firehose.store";
import { render, screen } from "@testing-library/react";
import type { FirehoseRejection } from "@transport/firehose";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
// i18next global bootstrap (registers the "common" namespace the tail uses).
import "@i18n/index";
import { LiveDecisionsRegion } from "../LiveDecisionsRegion";

// The two shared signals the region threads through `useUniversalState`; the
// socket signal and the rejections arrive as the `firehose` prop.
interface Signals {
  posture: { isError: boolean; data: { degraded: boolean } | undefined };
  offline: boolean;
}

const signals = vi.hoisted(
  (): Signals => ({
    posture: { isError: false, data: { degraded: false } },
    offline: false,
  }),
);

vi.mock("@hooks/use-posture", () => ({ usePosture: () => signals.posture }));
vi.mock("@hooks/use-online-status", () => ({ useOnlineStatus: () => signals.offline }));

const LIVE: UseFirehoseResult = { state: "open", connected: true, rejections: [] };

const DECISION_REJECTED: FirehoseRejection = {
  channel: "decision",
  seq: 7,
  reason: "decision_id: Invalid uuid",
};

function decision(): LiveDecision {
  return {
    decision_id: "11111111-1111-4111-8111-111111111111",
    tier: "tier_2",
    confidence: 0.91,
    phase_reached: 3,
    escalated: false,
    selected_action: {},
    timestamp: "2026-06-06T00:00:00.000Z",
    degraded: false,
    is_synthetic: false,
    initiator: "operator",
    agents: [],
  };
}

function renderRegion(firehose: UseFirehoseResult) {
  return render(
    <MemoryRouter>
      <LiveDecisionsRegion firehose={firehose} />
    </MemoryRouter>,
  );
}

/** The `data-universal-state` the region rendered, or null when it rendered its rows. */
function stateOf(container: HTMLElement): string | null {
  const block = container.querySelector("[data-universal-state]");
  return block === null ? null : block.getAttribute("data-universal-state");
}

// Req 8.1–8.5 at the component boundary: the fault-transition e2e asserts these
// exact `data-universal-state` values on Mission Control.
describe("LiveDecisionsRegion", () => {
  beforeEach(() => {
    useFirehoseStore.getState().flushAll();
  });

  afterEach(() => {
    signals.posture = { isError: false, data: { degraded: false } };
    signals.offline = false;
  });

  it("renders the bare live tail when the feed is live, healthy and populated", () => {
    useFirehoseStore.getState().appendDecision(decision(), 1);
    const { container } = renderRegion(LIVE);
    expect(stateOf(container)).toBeNull();
    expect(screen.getByRole("region", { name: "Decision firehose" })).toBeInTheDocument();
  });

  it("renders degraded instead of rows while the socket is not live", () => {
    useFirehoseStore.getState().appendDecision(decision(), 1);
    const { container } = renderRegion({ state: "connecting", connected: false, rejections: [] });
    expect(stateOf(container)).toBe("degraded");
    expect(screen.getByText("Firehose not live")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Decision firehose" })).not.toBeInTheDocument();
  });

  it("keeps the posture signal: degraded when posture is unknown even on a live socket", () => {
    signals.posture = { isError: true, data: undefined };
    useFirehoseStore.getState().appendDecision(decision(), 1);
    const { container } = renderRegion(LIVE);
    expect(stateOf(container)).toBe("degraded");
    // A live socket is not the cause, so the shared posture copy is shown.
    expect(screen.getByText("Running degraded")).toBeInTheDocument();
    expect(screen.queryByText("Firehose not live")).not.toBeInTheDocument();
  });

  it("renders error, never the rows, while a rejected decision payload is unsuperseded", () => {
    useFirehoseStore.getState().appendDecision(decision(), 1);
    const { container } = renderRegion({ ...LIVE, rejections: [DECISION_REJECTED] });
    expect(stateOf(container)).toBe("error");
    expect(screen.getByRole("alert")).toHaveTextContent("decision_id: Invalid uuid");
    expect(screen.queryByRole("region", { name: "Decision firehose" })).not.toBeInTheDocument();
  });

  it("is not put in error by a rejection on a channel it does not render", () => {
    useFirehoseStore.getState().appendDecision(decision(), 1);
    const cognition: FirehoseRejection = {
      channel: "cognition",
      seq: 3,
      reason: "phase: Required",
    };
    const { container } = renderRegion({ ...LIVE, rejections: [cognition] });
    expect(stateOf(container)).toBeNull();
  });

  it("renders offline over a rejection and a dropped socket", () => {
    signals.offline = true;
    const { container } = renderRegion({
      state: "closed",
      connected: false,
      rejections: [DECISION_REJECTED],
    });
    expect(stateOf(container)).toBe("offline");
  });

  it("renders empty, not error, when a live feed has carried no decision yet", () => {
    const { container } = renderRegion(LIVE);
    expect(stateOf(container)).toBe("empty");
    expect(screen.getByText("Waiting for the firehose…")).toBeInTheDocument();
  });
});
