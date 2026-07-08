// Feature: atlas-console-elevation, Property 35: Decision replay is referentially transparent
//
// Property 35 (Validates: Requirements 11.1) — `replayDecision` is a pure
// function: for any recorded decision and any phase index, invoking it twice
// yields deeply-equal slices. This is the runtime witness for FE-INV-009 /
// FE-INV-028 — a decision loaded by id renders identically on every load
// because replay computes with no `Date.now`, no `Math.random`, and no I/O.

import type { ConsensusDecision } from "@domain/consensus-decision";
import { replayDecision } from "@lib/replay";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

// ── Arbitraries ────────────────────────────────────────────────────────────

const recordArb = fc.dictionary(fc.string(), fc.jsonValue(), { maxKeys: 4 });

const proposalArb = fc.record({
  agent_name: fc.string(),
  status: fc.constantFrom("proposed", "rejected", "selected", "modified"),
  confidence: fc.double({ min: 0, max: 1, noNaN: true }),
  utility_score: fc.double({ min: 0, max: 1, noNaN: true }),
});

const decisionArb: fc.Arbitrary<ConsensusDecision> = fc
  .record({
    decision_id: fc.uuid(),
    timestamp: fc.date({ noInvalidDate: true }).map((d) => d.toISOString()),
    tier: fc.constantFrom("tier_1", "tier_2", "tier_3", "tier_4"),
    proposals: fc.array(proposalArb, { maxLength: 6 }),
    selected_action: recordArb,
    pareto_weights: fc.dictionary(fc.string(), fc.double({ noNaN: true }), { maxKeys: 4 }),
    confidence: fc.double({ min: 0, max: 1, noNaN: true }),
    audit_trace: fc.array(fc.string(), { maxLength: 12 }),
    phase_reached: fc.integer({ min: 1, max: 5 }),
    debate_rounds: fc.integer({ min: 0, max: 5 }),
    pareto_front: fc.option(fc.array(recordArb, { maxLength: 4 }), { nil: null }),
    context_messages: fc.array(recordArb, { maxLength: 4 }),
    execution_confirmations: fc.array(fc.string(), { maxLength: 4 }),
    human_override: fc.option(recordArb, { nil: null }),
    escalated_to_human: fc.boolean(),
  })
  .map((d) => d as unknown as ConsensusDecision);

// A phase generator that spans in-range, out-of-range, and non-finite inputs
// so transparency is exercised across the whole clamp domain.
const phaseArb = fc.oneof(
  fc.integer({ min: -8, max: 12 }),
  fc.double({ min: -8, max: 12, noNaN: true }),
  fc.constantFrom(Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY),
);

describe("replayDecision — Property 35: referential transparency", () => {
  it("produces deeply-equal slices for two invocations with identical inputs", () => {
    fc.assert(
      fc.property(decisionArb, phaseArb, (decision, phase) => {
        const first = replayDecision(decision, phase);
        const second = replayDecision(decision, phase);
        expect(first).toStrictEqual(second);
      }),
      { numRuns: 200 },
    );
  });

  it("is stable across repeated invocations (no accumulated/hidden state)", () => {
    fc.assert(
      fc.property(decisionArb, phaseArb, (decision, phase) => {
        const baseline = replayDecision(decision, phase);
        for (let i = 0; i < 5; i++) {
          expect(replayDecision(decision, phase)).toStrictEqual(baseline);
        }
      }),
      { numRuns: 100 },
    );
  });
});
