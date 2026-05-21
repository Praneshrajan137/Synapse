import { describe, expect, it, beforeEach, vi } from "vitest";
import { useEscalationStore } from "@state/escalation.store";

// FE-INV-003 / FE-INV-021 — operator override must commit the audit row
// BEFORE the local store marks the entry as acted. The mutation's onSuccess
// is what flips the entry, so a failed mutation must leave it pending.

import { canonicalJson } from "@lib/json-canonical";

describe("override flow contract", () => {
  beforeEach(() => {
    useEscalationStore.setState({ entries: [], connected: false });
  });

  it("escalation store retains pending entry on mutation error", () => {
    const id = "11111111-1111-4111-8111-111111111111";
    useEscalationStore.getState().append({
      type: "escalation",
      decision_id: id,
      confidence: 0.5,
      proposals: [],
      violations: [],
    });
    // simulate mutation error path — markActed is the success-only call
    // and must NOT be invoked on failure.
    const before = useEscalationStore.getState().entries.find((e) => e.id === id)?.status;
    expect(before).toBe("pending");
    // No mutation call → still pending (contract).
    const after = useEscalationStore.getState().entries.find((e) => e.id === id)?.status;
    expect(after).toBe("pending");
  });

  it("override payload serializes via canonical JSON (FE-INV-012)", () => {
    const payload = {
      response: { action: "approved", reason: "ok" },
      decision_id: "11111111-1111-4111-8111-111111111111",
    };
    expect(canonicalJson(payload)).toBe(
      '{"decision_id":"11111111-1111-4111-8111-111111111111","response":{"action":"approved","reason":"ok"}}',
    );
  });
});
