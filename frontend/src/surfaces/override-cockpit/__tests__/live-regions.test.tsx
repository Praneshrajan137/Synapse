// Feature: atlas-console-elevation — live-region announcements + Feedback_Window
//
// Task 17.5 (Requirements 8.3, 9.3) — must-notice state changes are announced
// to assistive tech through appropriate live regions, and mutating actions
// present explicit success/failure feedback within the Feedback_Window (≤ 1s):
//
//   • ESCALATION ARRIVAL (Req 9.3): the Cockpit's assertive live region names
//     the newly-arrived escalation so a screen-reader operator is told an
//     escalation needs judgement even while focus is elsewhere.
//   • DEGRADATION (Req 9.3): the DegradedBanner is a polite live region that
//     names what is degraded, and renders "posture unknown" rather than going
//     silently green when the posture fetch fails.
//   • ACTION OUTCOME (Req 8.3 / 9.3): the override mutation surfaces an explicit
//     success or failure toast the instant the request settles — inside the
//     Feedback_Window — for both the success and the error paths.

import type { EscalationMessage } from "@domain/escalation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Register the i18n `common` namespace (DegradedBanner/ConnectionPill use it).
import "@i18n/index";

// ─── Module mocks ──────────────────────────────────────────────────────────

const toastSuccess = vi.hoisted(() => vi.fn());
const toastError = vi.hoisted(() => vi.fn());
const toastWarning = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: { success: toastSuccess, error: toastError, warning: toastWarning },
}));

// The Cockpit's transport hooks are stubbed — no real sockets in jsdom.
vi.mock("@hooks/use-ws", () => ({
  useWs: () => ({ state: "open", connected: true, send: vi.fn(), on: () => () => {} }),
}));
vi.mock("@hooks/use-firehose", () => ({ useFirehose: () => undefined }));

const submitOverride = vi.hoisted(() => vi.fn());
vi.mock("@hooks/use-synapse-api", () => ({
  useSynapseApi: () => ({ submitOverride }),
}));

const mockPosture = vi.hoisted(() => vi.fn());
vi.mock("@hooks/use-posture", () => ({ usePosture: mockPosture }));

import { DegradedBanner } from "@ds/compounds/DegradedBanner";
import { useEscalationStore } from "@state/escalation.store";
import { Cockpit } from "@surfaces/override-cockpit/Cockpit";
import { useOverrideMutation } from "@surfaces/override-cockpit/useOverrideMutation";

const DECISION_ID = "11111111-1111-4111-8111-111111111111";

function seedEscalation(): void {
  const message = {
    type: "escalation",
    decision_id: DECISION_ID,
    confidence: 0.42,
    proposals: [],
    violations: [],
  } as EscalationMessage;
  useEscalationStore.setState({
    entries: [{ id: DECISION_ID, received_at: Date.now(), message, status: "pending" }],
    connected: true,
  });
}

function withQueryClient(children: ReactNode): ReactNode {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useEscalationStore.setState({ entries: [], connected: false });
});

// ─── Escalation arrival (Req 9.3) ────────────────────────────────────────────

describe("Cockpit — escalation-arrival live region (Req 9.3)", () => {
  it("announces the newly-arrived escalation through an assertive live region", () => {
    seedEscalation();
    render(withQueryClient(<Cockpit />));

    const region = screen.getByTestId("escalation-arrival");
    // Assertive so it interrupts — an escalation needs immediate judgement.
    expect(region.getAttribute("aria-live")).toBe("assertive");
    expect(region.textContent).toMatch(/escalation arrived/i);
    expect(region.textContent).toContain(DECISION_ID.slice(0, 8));
    expect(region.textContent).toContain("0.42");
    expect(region.textContent).toMatch(/needs human judgement/i);
  });

  it("holds an empty announcement when nothing is pending", () => {
    render(withQueryClient(<Cockpit />));
    const region = screen.getByTestId("escalation-arrival");
    expect(region.getAttribute("aria-live")).toBe("assertive");
    expect(region.textContent).toBe("");
  });
});

// ─── Degradation (Req 9.3) ───────────────────────────────────────────────────

describe("DegradedBanner — degradation live region (Req 9.3)", () => {
  it("names the degradation through a polite live region", () => {
    mockPosture.mockReturnValue({
      isPending: false,
      isError: false,
      data: {
        brownout: { bengaluru: "SHED_T4" },
        breakers: { ollama: "open" },
        degraded: true,
      },
    });
    render(<DegradedBanner />);
    const banner = screen.getByRole("status");
    expect(banner.getAttribute("aria-live")).toBe("polite");
    expect(banner).toHaveTextContent(/bengaluru/i);
    expect(banner).toHaveTextContent(/ollama/i);
  });

  it("announces 'posture unknown' rather than going silently green on fetch failure", () => {
    mockPosture.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
    });
    render(<DegradedBanner />);
    const banner = screen.getByRole("status");
    expect(banner.getAttribute("aria-live")).toBe("polite");
    expect(banner).toHaveTextContent(/posture unknown/i);
  });
});

// ─── Action outcome within the Feedback_Window (Req 8.3 / 9.3) ───────────────

describe("useOverrideMutation — action-outcome feedback within the Feedback_Window", () => {
  beforeEach(() => {
    seedEscalation();
  });

  it("presents an explicit success toast the instant the request settles (≤ 1s)", async () => {
    submitOverride.mockResolvedValueOnce({ audit_escalation_id: 987 });
    const { result } = renderHook(() => useOverrideMutation(), {
      wrapper: ({ children }) => <>{withQueryClient(children)}</>,
    });

    const start = performance.now();
    await act(async () => {
      await result.current.mutateAsync({
        decision_id: DECISION_ID,
        action: "approved",
        reason: "looks correct",
      });
    });
    const elapsedMs = performance.now() - start;

    expect(toastSuccess).toHaveBeenCalledOnce();
    expect(toastSuccess.mock.calls[0]![0]).toMatch(/override committed/i);
    // Feedback_Window: feedback is presented well within the ≤ 1s bound.
    expect(elapsedMs).toBeLessThan(1000);
    // The audit row committed before the local store flipped to acted.
    expect(useEscalationStore.getState().entries[0]!.status).toBe("acted");
  });

  it("presents an explicit failure toast on the error path (≤ 1s)", async () => {
    submitOverride.mockRejectedValueOnce(new Error("boom"));
    const { result } = renderHook(() => useOverrideMutation(), {
      wrapper: ({ children }) => <>{withQueryClient(children)}</>,
    });

    const start = performance.now();
    await act(async () => {
      await result.current
        .mutateAsync({ decision_id: DECISION_ID, action: "rejected", reason: "no" })
        .catch(() => {});
    });
    const elapsedMs = performance.now() - start;

    expect(toastError).toHaveBeenCalledOnce();
    expect(elapsedMs).toBeLessThan(1000);
    // A failed mutation never optimistically marks the entry acted.
    expect(useEscalationStore.getState().entries[0]!.status).toBe("pending");
  });
});
