import type { EscalationMessage } from "@domain/escalation";
import { useEscalationStore } from "@state/escalation.store";
import { beforeEach, describe, expect, it } from "vitest";

// FE-INV-017 — escalation store is append-only. The store exposes no
// .remove/.pop/.clear path; markActed mutates a single entry's status.

function fixture(decision_id: string, confidence = 0.5): EscalationMessage {
  return {
    type: "escalation",
    decision_id,
    confidence,
    proposals: [],
    violations: [],
  };
}

describe("escalation store (append-only, I-14 mirror)", () => {
  beforeEach(() => {
    useEscalationStore.setState({ entries: [], connected: false });
  });

  it("appends entries; never shrinks", () => {
    const store = useEscalationStore.getState();
    store.append(fixture("11111111-1111-4111-8111-111111111111"));
    store.append(fixture("22222222-2222-4222-8222-222222222222"));
    expect(useEscalationStore.getState().entries).toHaveLength(2);
  });

  it("markActed mutates a status field but keeps the entry", () => {
    const store = useEscalationStore.getState();
    store.append(fixture("11111111-1111-4111-8111-111111111111"));
    store.markActed("11111111-1111-4111-8111-111111111111", "approved");
    const entries = useEscalationStore.getState().entries;
    expect(entries).toHaveLength(1);
    expect(entries[0]?.status).toBe("acted");
    expect(entries[0]?.acted_action).toBe("approved");
  });

  it("exposes no destructive method", () => {
    const store = useEscalationStore.getState();
    expect((store as unknown as { clear?: unknown }).clear).toBeUndefined();
    expect((store as unknown as { remove?: unknown }).remove).toBeUndefined();
    expect((store as unknown as { pop?: unknown }).pop).toBeUndefined();
  });

  // ADR-044 / FE-INV-037: the same escalation can arrive via BOTH the legacy
  // /ws/escalation socket and the firehose `escalation` channel, and replays
  // after reconnect re-deliver. At-most-once per decision_id.
  it("ignores a duplicate decision_id (dual-path delivery + replays)", () => {
    const store = useEscalationStore.getState();
    store.append(fixture("11111111-1111-4111-8111-111111111111", 0.5));
    store.append(fixture("11111111-1111-4111-8111-111111111111", 0.6));
    const entries = useEscalationStore.getState().entries;
    expect(entries).toHaveLength(1);
    // First delivery wins — the duplicate never overwrites.
    expect(entries[0]?.message.confidence).toBe(0.5);
  });

  it("dedup does not lose acted status on replay", () => {
    const store = useEscalationStore.getState();
    store.append(fixture("11111111-1111-4111-8111-111111111111"));
    store.markActed("11111111-1111-4111-8111-111111111111", "rejected");
    store.append(fixture("11111111-1111-4111-8111-111111111111"));
    const entries = useEscalationStore.getState().entries;
    expect(entries).toHaveLength(1);
    expect(entries[0]?.status).toBe("acted");
  });
});
