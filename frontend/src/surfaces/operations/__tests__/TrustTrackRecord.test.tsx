import type { ScoredOutcome } from "@lib/trust-track-record";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TrustTrackRecord } from "../TrustTrackRecord";

const AS_OF = "2024-01-01T00:00:00.000Z";

function outcome(over: Partial<ScoredOutcome> = {}): ScoredOutcome {
  return {
    decisionId: "d1",
    operatorTokenRef: "vault:ref",
    approvedAtLowConfidence: false,
    outcome: "confirmed",
    isSynthetic: false,
    ...over,
  };
}

describe("TrustTrackRecord surface (Req 11)", () => {
  it("renders the honest 'awaiting scored outcomes' empty state when no data exists (Req 11.5)", () => {
    render(<TrustTrackRecord nowIso={AS_OF} />);
    // Copy appears in the body; the disclosure line always states n=0.
    expect(screen.getAllByText(/awaiting scored outcomes/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/n=0 scored/)).toBeInTheDocument();
  });

  it("renders the three distinct outcome states without folding unknown into confirmed (Req 11.3)", () => {
    render(
      <TrustTrackRecord
        nowIso={AS_OF}
        outcomes={[
          outcome({ decisionId: "a", outcome: "confirmed" }),
          outcome({ decisionId: "b", outcome: "diverged" }),
          outcome({ decisionId: "c", outcome: "unknown" }),
        ]}
      />,
    );
    expect(screen.getByText(/1 confirmed/)).toBeInTheDocument();
    expect(screen.getByText(/1 diverged/)).toBeInTheDocument();
    expect(screen.getByText(/1 unknown/)).toBeInTheDocument();
  });

  it("breaks out low-confidence approvals as distinct confirmed vs diverged counts (Req 11.2)", () => {
    render(
      <TrustTrackRecord
        nowIso={AS_OF}
        outcomes={[
          // Mix of low-confidence-approved (broken out) and normal (not) so the
          // low-confidence line carries different counts than the overall band.
          outcome({ decisionId: "a", approvedAtLowConfidence: true, outcome: "confirmed" }),
          outcome({ decisionId: "b", approvedAtLowConfidence: true, outcome: "diverged" }),
          outcome({ decisionId: "c", approvedAtLowConfidence: false, outcome: "confirmed" }),
        ]}
      />,
    );
    // The breakout line reports the distinct confirmed/diverged counts for the
    // low-confidence-approved subset — "2 approved → 1 confirmed, 1 diverged".
    const breakout = screen.getByText(/approved/).closest("p");
    expect(breakout).not.toBeNull();
    expect(breakout).toHaveTextContent(/2\s*approved/);
    expect(breakout).toHaveTextContent(/1\s*confirmed/);
    expect(breakout).toHaveTextContent(/1\s*diverged/);
    expect(screen.getByText(/Low-confidence approvals/i)).toBeInTheDocument();
  });

  it("flags a thin sample as provisional and always discloses window + as-of (Req 11.4)", () => {
    render(
      <TrustTrackRecord
        nowIso={AS_OF}
        windowLabel="Last 30 days"
        outcomes={[outcome()]}
      />,
    );
    expect(screen.getByText(/provisional/i)).toBeInTheDocument();
    expect(screen.getByText(/Last 30 days/)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(AS_OF))).toBeInTheDocument();
  });

  it("excludes synthetic decisions by default and includes them via the labelled toggle (Req 11.6)", () => {
    render(
      <TrustTrackRecord
        nowIso={AS_OF}
        outcomes={[
          outcome({ decisionId: "a", outcome: "confirmed", isSynthetic: false }),
          outcome({ decisionId: "b", outcome: "confirmed", isSynthetic: true }),
        ]}
      />,
    );
    // Default: only the real decision is counted.
    expect(screen.getByText(/n=1 scored/)).toBeInTheDocument();

    const toggle = screen.getByRole("button", { name: /include synthetic decisions/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);

    // Including synthetic: both are counted.
    expect(screen.getByText(/n=2 scored/)).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });
});
