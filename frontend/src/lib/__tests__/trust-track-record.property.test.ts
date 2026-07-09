// Property-based tests for the pure Trust_Track_Record aggregation
// (`aggregateTrack`, frontend/src/lib/trust-track-record.ts). Distinct from the
// example-based unit tests in trust-track-record.test.ts — this file holds the
// numbered correctness properties from the design (tasks 13.3–13.5). Additional
// property describe blocks (Properties 13 and 14) are appended here by later
// tasks, so each property lives in its own self-contained describe block.

import {
  AWAITING_SCORED_OUTCOMES,
  DEFAULT_WINDOW_LABEL,
  MIN_SCORED,
  type OutcomeState,
  type ScoredOutcome,
  aggregateTrack,
} from "@lib/trust-track-record";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const NOW = "2025-01-01T00:00:00.000Z";

const OUTCOME_STATES: readonly OutcomeState[] = ["confirmed", "diverged", "unknown"];

/**
 * Smart generator for a single {@link ScoredOutcome}. Every field is drawn from
 * its full legal domain so the tri-state partition is exercised across all
 * three outcome states, both approval-confidence flags, and synthetic/real
 * records. `decisionId` is a uuid so records stay individually identifiable.
 */
const scoredOutcomeArb: fc.Arbitrary<ScoredOutcome> = fc.record({
  decisionId: fc.uuid(),
  operatorTokenRef: fc.string({ minLength: 1 }).map((s) => `opk_${s}`),
  approvedAtLowConfidence: fc.boolean(),
  outcome: fc.constantFrom(...OUTCOME_STATES),
  isSynthetic: fc.boolean(),
});

const outcomesArb: fc.Arbitrary<ScoredOutcome[]> = fc.array(scoredOutcomeArb, {
  maxLength: 60,
});

// Feature: atlas-console-effectiveness, Property 12: Trust outcomes partition
// into exactly confirmed/diverged/unknown with unknown never folded into
// confirmed.
//
// For any set of scored outcomes, `aggregateTrack` partitions them into exactly
// `confirmed`, `diverged`, and `unknown` counts whose sum equals the scored
// total, with `unknown` counted distinctly and never folded into `confirmed`,
// and the low-confidence-approved subset broken out into its own distinct
// confirmed/diverged/unknown counts.
//
// **Validates: Requirements 11.2, 11.3**
describe("Property 12: Trust outcomes partition into a tri-state", () => {
  it("partitions the in-scope outcomes so confirmed + diverged + unknown === sampleSize", () => {
    fc.assert(
      fc.property(outcomesArb, fc.boolean(), (outcomes, includeSynthetic) => {
        const rec = aggregateTrack(outcomes, includeSynthetic, NOW);
        expect(rec.confirmed + rec.diverged + rec.unknown).toBe(rec.sampleSize);
        // Counts are non-negative and never exceed the sample.
        expect(rec.confirmed).toBeGreaterThanOrEqual(0);
        expect(rec.diverged).toBeGreaterThanOrEqual(0);
        expect(rec.unknown).toBeGreaterThanOrEqual(0);
      }),
      { numRuns: 100 },
    );
  });

  it("counts unknown distinctly and never folds it into confirmed", () => {
    fc.assert(
      fc.property(outcomesArb, fc.boolean(), (outcomes, includeSynthetic) => {
        const scoped = includeSynthetic ? outcomes : outcomes.filter((o) => !o.isSynthetic);
        const expectedConfirmed = scoped.filter((o) => o.outcome === "confirmed").length;
        const expectedDiverged = scoped.filter((o) => o.outcome === "diverged").length;
        const expectedUnknown = scoped.filter((o) => o.outcome === "unknown").length;

        const rec = aggregateTrack(outcomes, includeSynthetic, NOW);

        // Each state is tallied under its own field only — unknowns are their
        // own bucket, never absorbed into the confirmed count.
        expect(rec.confirmed).toBe(expectedConfirmed);
        expect(rec.diverged).toBe(expectedDiverged);
        expect(rec.unknown).toBe(expectedUnknown);
      }),
      { numRuns: 100 },
    );
  });

  it("breaks out the low-confidence-approved subset into distinct confirmed/diverged/unknown counts", () => {
    fc.assert(
      fc.property(outcomesArb, fc.boolean(), (outcomes, includeSynthetic) => {
        const scoped = includeSynthetic ? outcomes : outcomes.filter((o) => !o.isSynthetic);
        const lca = scoped.filter((o) => o.approvedAtLowConfidence);
        const expectedConfirmed = lca.filter((o) => o.outcome === "confirmed").length;
        const expectedDiverged = lca.filter((o) => o.outcome === "diverged").length;
        const expectedUnknown = lca.filter((o) => o.outcome === "unknown").length;

        const rec = aggregateTrack(outcomes, includeSynthetic, NOW);

        // The subset total is itself a tri-state partition.
        expect(rec.lowConfidenceApproved).toBe(lca.length);
        expect(rec.lowConfidenceApprovedConfirmed).toBe(expectedConfirmed);
        expect(rec.lowConfidenceApprovedDiverged).toBe(expectedDiverged);
        expect(rec.lowConfidenceApprovedUnknown).toBe(expectedUnknown);
        expect(
          rec.lowConfidenceApprovedConfirmed +
            rec.lowConfidenceApprovedDiverged +
            rec.lowConfidenceApprovedUnknown,
        ).toBe(rec.lowConfidenceApproved);

        // The subset never exceeds the full sample it is drawn from.
        expect(rec.lowConfidenceApproved).toBeLessThanOrEqual(rec.sampleSize);
        expect(rec.lowConfidenceApprovedConfirmed).toBeLessThanOrEqual(rec.confirmed);
        expect(rec.lowConfidenceApprovedDiverged).toBeLessThanOrEqual(rec.diverged);
        expect(rec.lowConfidenceApprovedUnknown).toBeLessThanOrEqual(rec.unknown);
      }),
      { numRuns: 100 },
    );
  });
});

// Feature: atlas-console-effectiveness, Property 13: The track record is flagged
// provisional iff scored outcomes are below the minimum and renders "awaiting
// scored outcomes" when none exist, always disclosing sample size/window/as-of.
//
// For any set of scored outcomes, `aggregateTrack` flags the record
// `provisional` exactly when there is some but too little evidence
// (0 < sampleSize < MIN_SCORED), flags it `awaiting` exactly when no scored
// outcomes exist (sampleSize === 0) — the state the surface renders as
// "awaiting scored outcomes" rather than a fabricated/zeroed record — and always
// discloses sample size, evaluation window, and the "as of" timestamp.
//
// **Validates: Requirements 11.4, 11.5**
describe("Property 13: provisional/awaiting honesty with full disclosure", () => {
  it("flags provisional iff 0 < sampleSize < MIN_SCORED", () => {
    fc.assert(
      fc.property(outcomesArb, fc.boolean(), (outcomes, includeSynthetic) => {
        const rec = aggregateTrack(outcomes, includeSynthetic, NOW);
        const expectedProvisional = rec.sampleSize > 0 && rec.sampleSize < MIN_SCORED;
        expect(rec.provisional).toBe(expectedProvisional);
        // A record can never be both awaiting (empty) and provisional at once.
        if (rec.awaiting) {
          expect(rec.provisional).toBe(false);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("flags awaiting iff no scored outcomes exist", () => {
    fc.assert(
      fc.property(outcomesArb, fc.boolean(), (outcomes, includeSynthetic) => {
        const rec = aggregateTrack(outcomes, includeSynthetic, NOW);
        expect(rec.awaiting).toBe(rec.sampleSize === 0);
        // The awaiting state is the one the surface renders as this copy; the
        // constant is a non-empty single source of truth for that rendering.
        if (rec.awaiting) {
          expect(AWAITING_SCORED_OUTCOMES.length).toBeGreaterThan(0);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("always discloses sample size, evaluation window, and as-of timestamp", () => {
    fc.assert(
      fc.property(
        outcomesArb,
        fc.boolean(),
        fc.option(fc.string({ minLength: 1 }), { nil: undefined }),
        (outcomes, includeSynthetic, windowLabel) => {
          const rec =
            windowLabel === undefined
              ? aggregateTrack(outcomes, includeSynthetic, NOW)
              : aggregateTrack(outcomes, includeSynthetic, NOW, windowLabel);

          // Sample size is always a concrete non-negative count — even the
          // awaiting/empty case discloses 0 rather than omitting the figure.
          expect(rec.sampleSize).toBeGreaterThanOrEqual(0);
          expect(Number.isInteger(rec.sampleSize)).toBe(true);

          // The "as of" timestamp is always the one supplied — never dropped.
          expect(rec.asOf).toBe(NOW);

          // The evaluation window is always disclosed as a non-empty label,
          // falling back to the default when the caller omits one.
          expect(typeof rec.windowLabel).toBe("string");
          expect(rec.windowLabel.length).toBeGreaterThan(0);
          expect(rec.windowLabel).toBe(
            windowLabel === undefined ? DEFAULT_WINDOW_LABEL : windowLabel,
          );
        },
      ),
      { numRuns: 100 },
    );
  });
});

// Feature: atlas-console-effectiveness, Property 14: The default aggregate
// excludes every Synthetic decision and the labelled toggle adds exactly those
// records.
//
// For any set of scored outcomes, `aggregateTrack` with includeSynthetic=false
// excludes every synthetic record (its sampleSize equals the count of
// non-synthetic outcomes), while includeSynthetic=true counts all outcomes, and
// the difference between the two aggregates is exactly the set of synthetic
// records — no real record is dropped and no synthetic record leaks into the
// default view.
//
// **Validates: Requirements 11.6**
describe("Property 14: synthetic decisions excluded by default, toggle adds exactly them", () => {
  it("default (includeSynthetic=false) excludes every synthetic record", () => {
    fc.assert(
      fc.property(outcomesArb, (outcomes) => {
        const nonSyntheticCount = outcomes.filter((o) => !o.isSynthetic).length;
        const rec = aggregateTrack(outcomes, false, NOW);

        // The default aggregate's sample equals exactly the non-synthetic count.
        expect(rec.sampleSize).toBe(nonSyntheticCount);
        expect(rec.includeSynthetic).toBe(false);
        // Every tri-state count is drawn only from non-synthetic records.
        const nonSynthetic = outcomes.filter((o) => !o.isSynthetic);
        expect(rec.confirmed).toBe(nonSynthetic.filter((o) => o.outcome === "confirmed").length);
        expect(rec.diverged).toBe(nonSynthetic.filter((o) => o.outcome === "diverged").length);
        expect(rec.unknown).toBe(nonSynthetic.filter((o) => o.outcome === "unknown").length);
      }),
      { numRuns: 100 },
    );
  });

  it("toggle (includeSynthetic=true) counts all records", () => {
    fc.assert(
      fc.property(outcomesArb, (outcomes) => {
        const rec = aggregateTrack(outcomes, true, NOW);

        // With the toggle on, the sample is the entire set — nothing excluded.
        expect(rec.sampleSize).toBe(outcomes.length);
        expect(rec.includeSynthetic).toBe(true);
        expect(rec.confirmed).toBe(outcomes.filter((o) => o.outcome === "confirmed").length);
        expect(rec.diverged).toBe(outcomes.filter((o) => o.outcome === "diverged").length);
        expect(rec.unknown).toBe(outcomes.filter((o) => o.outcome === "unknown").length);
      }),
      { numRuns: 100 },
    );
  });

  it("the labelled toggle adds exactly the synthetic records and no others", () => {
    fc.assert(
      fc.property(outcomesArb, (outcomes) => {
        const syntheticCount = outcomes.filter((o) => o.isSynthetic).length;

        const excluded = aggregateTrack(outcomes, false, NOW);
        const included = aggregateTrack(outcomes, true, NOW);

        // The difference between the two views is exactly the synthetic set —
        // real records are never dropped and synthetics never leak by default.
        expect(included.sampleSize - excluded.sampleSize).toBe(syntheticCount);

        // The per-state deltas also equal exactly the synthetic records in each
        // state, so the toggle adds those records and nothing else.
        const synthetic = outcomes.filter((o) => o.isSynthetic);
        expect(included.confirmed - excluded.confirmed).toBe(
          synthetic.filter((o) => o.outcome === "confirmed").length,
        );
        expect(included.diverged - excluded.diverged).toBe(
          synthetic.filter((o) => o.outcome === "diverged").length,
        );
        expect(included.unknown - excluded.unknown).toBe(
          synthetic.filter((o) => o.outcome === "unknown").length,
        );

        // The low-confidence-approved subset shifts by exactly the synthetic
        // low-confidence-approved records too.
        const syntheticLca = synthetic.filter((o) => o.approvedAtLowConfidence);
        expect(included.lowConfidenceApproved - excluded.lowConfidenceApproved).toBe(
          syntheticLca.length,
        );
      }),
      { numRuns: 100 },
    );
  });
});
