import { describe, expect, it } from "vitest";
import {
  AWAITING_SCORED_OUTCOMES,
  DEFAULT_WINDOW_LABEL,
  MIN_SCORED,
  type ScoredOutcome,
  aggregateTrack,
} from "../trust-track-record";

const NOW = "2025-01-01T00:00:00.000Z";

function outcome(overrides: Partial<ScoredOutcome> = {}): ScoredOutcome {
  return {
    decisionId: "d-1",
    operatorTokenRef: "opk_abc",
    approvedAtLowConfidence: false,
    outcome: "confirmed",
    isSynthetic: false,
    ...overrides,
  };
}

// Req 11.1–11.6 — the pure Trust_Track_Record aggregation.
describe("aggregateTrack", () => {
  it("partitions outcomes into distinct confirmed / diverged / unknown (Req 11.3)", () => {
    const rec = aggregateTrack(
      [
        outcome({ decisionId: "a", outcome: "confirmed" }),
        outcome({ decisionId: "b", outcome: "confirmed" }),
        outcome({ decisionId: "c", outcome: "diverged" }),
        outcome({ decisionId: "d", outcome: "unknown" }),
      ],
      false,
      NOW,
    );
    expect(rec.confirmed).toBe(2);
    expect(rec.diverged).toBe(1);
    expect(rec.unknown).toBe(1);
    // unknown is never folded into confirmed
    expect(rec.confirmed + rec.diverged + rec.unknown).toBe(rec.sampleSize);
    expect(rec.sampleSize).toBe(4);
  });

  it("reports low-confidence-approved counts as distinct confirmed vs diverged (Req 11.2)", () => {
    const rec = aggregateTrack(
      [
        outcome({ decisionId: "a", approvedAtLowConfidence: true, outcome: "confirmed" }),
        outcome({ decisionId: "b", approvedAtLowConfidence: true, outcome: "confirmed" }),
        outcome({ decisionId: "c", approvedAtLowConfidence: true, outcome: "diverged" }),
        outcome({ decisionId: "d", approvedAtLowConfidence: true, outcome: "unknown" }),
        // A high-confidence approval must not enter the low-confidence subset.
        outcome({ decisionId: "e", approvedAtLowConfidence: false, outcome: "confirmed" }),
      ],
      false,
      NOW,
    );
    expect(rec.lowConfidenceApproved).toBe(4);
    expect(rec.lowConfidenceApprovedConfirmed).toBe(2);
    expect(rec.lowConfidenceApprovedDiverged).toBe(1);
    expect(rec.lowConfidenceApprovedUnknown).toBe(1);
  });

  it("discloses sample size, window, and as-of, and flags provisional below MIN_SCORED (Req 11.4)", () => {
    const rec = aggregateTrack([outcome()], false, NOW);
    expect(rec.sampleSize).toBe(1);
    expect(rec.windowLabel).toBe(DEFAULT_WINDOW_LABEL);
    expect(rec.asOf).toBe(NOW);
    expect(rec.provisional).toBe(true);
    expect(rec.awaiting).toBe(false);
  });

  it("is not provisional once MIN_SCORED outcomes exist (Req 11.4)", () => {
    const many = Array.from({ length: MIN_SCORED }, (_, i) => outcome({ decisionId: `d-${i}` }));
    const rec = aggregateTrack(many, false, NOW);
    expect(rec.sampleSize).toBe(MIN_SCORED);
    expect(rec.provisional).toBe(false);
  });

  it("returns an awaiting record when no scored outcomes exist (Req 11.5)", () => {
    const rec = aggregateTrack([], false, NOW);
    expect(rec.awaiting).toBe(true);
    expect(rec.provisional).toBe(false);
    expect(rec.sampleSize).toBe(0);
    // still discloses window + as-of rather than a fabricated record
    expect(rec.windowLabel).toBe(DEFAULT_WINDOW_LABEL);
    expect(rec.asOf).toBe(NOW);
    expect(AWAITING_SCORED_OUTCOMES).toBe("Awaiting scored outcomes");
  });

  it("excludes Synthetic decisions by default and includes them via the toggle (Req 11.6)", () => {
    const outcomes = [
      outcome({ decisionId: "real", isSynthetic: false, outcome: "confirmed" }),
      outcome({ decisionId: "syn", isSynthetic: true, outcome: "diverged" }),
    ];
    const excluded = aggregateTrack(outcomes, false, NOW);
    expect(excluded.sampleSize).toBe(1);
    expect(excluded.diverged).toBe(0);
    expect(excluded.includeSynthetic).toBe(false);

    const included = aggregateTrack(outcomes, true, NOW);
    expect(included.sampleSize).toBe(2);
    expect(included.diverged).toBe(1);
    expect(included.includeSynthetic).toBe(true);
  });

  it("honours a custom window label (Req 11.4)", () => {
    const rec = aggregateTrack([outcome()], false, NOW, "Last 30 days");
    expect(rec.windowLabel).toBe("Last 30 days");
  });
});
