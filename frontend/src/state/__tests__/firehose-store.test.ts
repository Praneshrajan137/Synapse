import type { ConsensusDecision } from "@domain/consensus-decision";
import { useFirehoseStore } from "@state/firehose.store";
import { beforeEach, describe, expect, it } from "vitest";

// FE-INV-016 + FE-INV-017 — firehose store is append-only and city-flushable.

function makeDecision(id: string, confidence = 0.85): ConsensusDecision {
  return {
    decision_id: id,
    timestamp: "2026-05-18T10:00:00.000Z",
    tier: "tier_2",
    proposals: [],
    selected_action: {},
    pareto_weights: {},
    confidence,
    audit_trace: [],
    phase_reached: 1,
    debate_rounds: 0,
    context_messages: [],
    execution_confirmations: [],
  };
}

describe("firehose store (append-only ring buffers)", () => {
  beforeEach(() => {
    useFirehoseStore.getState().flushAll();
  });

  it("appends decisions and exposes seq", () => {
    useFirehoseStore
      .getState()
      .appendDecision(makeDecision("11111111-1111-4111-8111-111111111111"), 1);
    useFirehoseStore
      .getState()
      .appendDecision(makeDecision("22222222-2222-4222-8222-222222222222"), 2);
    const s = useFirehoseStore.getState();
    expect(s.decisions.items).toHaveLength(2);
    expect(s.lastSeq.decision).toBe(2);
  });

  it("respects cap (oldest dropped, never mutated in place)", () => {
    const store = useFirehoseStore.getState();
    const cap = store.decisions.cap;
    const before = store.decisions.items;
    for (let i = 0; i < cap + 5; i++) {
      const padded = String(i).padStart(8, "0");
      store.appendDecision(makeDecision(`${padded}-0000-4000-8000-000000000000`), i + 1);
    }
    const after = useFirehoseStore.getState().decisions.items;
    expect(after).toHaveLength(cap);
    // Original array reference must not have been mutated (immutability).
    expect(before).toHaveLength(0);
  });

  it("flushAll clears every channel and seq map", () => {
    const store = useFirehoseStore.getState();
    store.appendDecision(makeDecision("11111111-1111-4111-8111-111111111111"), 1);
    store.flushAll();
    const s = useFirehoseStore.getState();
    expect(s.decisions.items).toHaveLength(0);
    expect(Object.keys(s.lastSeq)).toHaveLength(0);
  });
});
