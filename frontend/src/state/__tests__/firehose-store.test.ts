import type { LiveDecision } from "@domain/decision-envelope";
import { useFirehoseStore } from "@state/firehose.store";
import { beforeEach, describe, expect, it } from "vitest";

// FE-INV-016 + FE-INV-017 — firehose store is append-only and city-flushable.
// The buffer holds LEAN decision envelopes (ADR-044), not full audit rows.

function makeDecision(id: string, confidence = 0.85): LiveDecision {
  return {
    decision_id: id,
    timestamp: "2026-05-18T10:00:00.000Z",
    tier: "tier_2",
    selected_action: {},
    confidence,
    phase_reached: 1,
    escalated: false,
    degraded: false,
    is_synthetic: false,
    initiator: "operator",
    agents: [],
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
    store.appendPricing({ pricing_id: "p1" } as never, 9);
    store.flushAll();
    const s = useFirehoseStore.getState();
    expect(s.decisions.items).toHaveLength(0);
    expect(s.pricing.items).toHaveLength(0);
    expect(Object.keys(s.lastSeq)).toHaveLength(0);
  });

  // Sprint 17/18 channels — each appender must store the item and stamp its seq
  // (these are Stryker mutate targets in firehose.store.ts).
  it("appends pricing / freshness / route / demand / twin with their seq keys", () => {
    const store = useFirehoseStore.getState();
    store.appendPricing({ pricing_id: "p1" } as never, 1);
    store.appendFreshness({ alert_id: "f1" } as never, 2);
    store.appendRoute({ plan_id: "r1" } as never, 3);
    store.appendDemand({ sku_id: "d1" } as never, 4);
    store.appendTwin({ kl_divergence: 0.2 } as never, 5);
    const s = useFirehoseStore.getState();
    expect(s.pricing.items).toHaveLength(1);
    expect(s.freshness.items).toHaveLength(1);
    expect(s.routes.items).toHaveLength(1);
    expect(s.demand.items).toHaveLength(1);
    expect(s.twin.items).toHaveLength(1);
    expect(s.lastSeq.pricing).toBe(1);
    expect(s.lastSeq.freshness).toBe(2);
    expect(s.lastSeq.routing).toBe(3);
    expect(s.lastSeq.demand).toBe(4);
    expect(s.lastSeq.twin).toBe(5);
  });

  it("setConnection records the live WS state (drives the attention beacon)", () => {
    expect(useFirehoseStore.getState().connection).toBe("idle");
    useFirehoseStore.getState().setConnection("open");
    expect(useFirehoseStore.getState().connection).toBe("open");
    useFirehoseStore.getState().setConnection("closed");
    expect(useFirehoseStore.getState().connection).toBe("closed");
  });
});
