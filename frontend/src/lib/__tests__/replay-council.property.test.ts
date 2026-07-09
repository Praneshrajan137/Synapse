// Feature: atlas-console-elevation, Property 38: Council reconstruction never fabricates deliberation
//
// Property 38 (Validates: Requirements 11.4) — `reconstructCouncil` (FE-INV-045)
// reconstructs Council Theater state honestly:
//   • the reconstructed phases are exactly [MIN_PHASE .. clampPhase(phase_reached)]
//     — a subset of the recorded range, never fabricated beyond it,
//   • a zero-debate (or empty-transcript) decision renders an explicit
//     "no debate — fast path" empty state rather than an invented transcript, and
//   • a null/empty Pareto front renders an explicit "null-front" empty state.

import type { ConsensusDecision } from "@domain/consensus-decision";
import { MAX_PHASE, MIN_PHASE, clampPhase, reconstructCouncil } from "@lib/replay";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const recordArb = fc.dictionary(fc.string(), fc.jsonValue(), { maxKeys: 3 });

// phase_reached is deliberately widened beyond [1, 5] so clamping is exercised.
const decisionArb: fc.Arbitrary<ConsensusDecision> = fc
  .record({
    decision_id: fc.uuid(),
    timestamp: fc.date({ noInvalidDate: true }).map((d) => d.toISOString()),
    tier: fc.constantFrom("tier_1", "tier_2", "tier_3", "tier_4"),
    proposals: fc.array(recordArb, { maxLength: 4 }),
    selected_action: recordArb,
    pareto_weights: fc.dictionary(fc.string(), fc.double({ noNaN: true }), { maxKeys: 3 }),
    confidence: fc.double({ min: 0, max: 1, noNaN: true }),
    audit_trace: fc.array(fc.string(), { maxLength: 8 }),
    phase_reached: fc.integer({ min: -5, max: 10 }),
    debate_rounds: fc.integer({ min: 0, max: 6 }),
    pareto_front: fc.option(fc.array(recordArb, { maxLength: 5 }), { nil: null }),
    context_messages: fc.array(recordArb, { maxLength: 6 }),
    execution_confirmations: fc.array(fc.string(), { maxLength: 3 }),
    human_override: fc.option(recordArb, { nil: null }),
    escalated_to_human: fc.boolean(),
  })
  .map((d) => d as unknown as ConsensusDecision);

describe("reconstructCouncil — Property 38: honest reconstruction", () => {
  it("reconstructs exactly the recorded phases, never beyond phase_reached", () => {
    fc.assert(
      fc.property(decisionArb, (decision) => {
        const { maxPhase, recordedPhases } = reconstructCouncil(decision);
        const bound = clampPhase(decision.phase_reached);

        expect(maxPhase).toBe(bound);
        expect(recordedPhases).toStrictEqual(
          Array.from({ length: bound - MIN_PHASE + 1 }, (_, i) => MIN_PHASE + i),
        );
        // Every reconstructed phase is inside the recorded, clamped range.
        for (const p of recordedPhases) {
          expect(p).toBeGreaterThanOrEqual(MIN_PHASE);
          expect(p).toBeLessThanOrEqual(bound);
          expect(p).toBeLessThanOrEqual(MAX_PHASE);
        }
      }),
      { numRuns: 200 },
    );
  });

  it("classifies debate as recorded only with rounds AND a transcript, else fast-path empty", () => {
    fc.assert(
      fc.property(decisionArb, (decision) => {
        const { debate } = reconstructCouncil(decision);
        const hasDeliberation = decision.debate_rounds > 0 && decision.context_messages.length > 0;

        if (hasDeliberation) {
          expect(debate.kind).toBe("recorded");
          if (debate.kind === "recorded") {
            expect(debate.rounds).toBe(decision.debate_rounds);
            expect(debate.transcriptLength).toBe(decision.context_messages.length);
          }
        } else {
          expect(debate.kind).toBe("empty");
          if (debate.kind === "empty") {
            expect(debate.reason).toBe("no-debate-fast-path");
          }
        }
      }),
      { numRuns: 200 },
    );
  });

  it("renders an explicit null-front empty state when no Pareto front was recorded", () => {
    fc.assert(
      fc.property(decisionArb, (decision) => {
        const { paretoFront } = reconstructCouncil(decision);
        const front = decision.pareto_front;
        const hasFront = front != null && front.length > 0;

        if (hasFront) {
          expect(paretoFront.kind).toBe("recorded");
          if (paretoFront.kind === "recorded") {
            expect(paretoFront.size).toBe(front!.length);
          }
        } else {
          expect(paretoFront.kind).toBe("empty");
          if (paretoFront.kind === "empty") {
            expect(paretoFront.reason).toBe("null-front");
          }
        }
      }),
      { numRuns: 200 },
    );
  });
});
