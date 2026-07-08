import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { isFreshSeq } from "@transport/ws-multiplex";
import {
  appendEscalationEntry,
  markEscalationActed,
  type EscalationEntry,
} from "../escalation.store";
import type { EscalationMessage } from "@domain/escalation";

// Feature: atlas-console-elevation
// Property 33: Replayed real-time messages apply at most once
//
// `isFreshSeq` guarantees each sequence number is applied at most once (replays
// after a `since_seq` catch-up are dropped), and the escalation reducers keep a
// decision at-most-once — a replay of an already-acted decision never resets it
// to pending.
//
// **Validates: Requirements 10.6**

function mkMessage(id: string): EscalationMessage {
  return {
    type: "escalation",
    decision_id: id,
    confidence: 0.5,
    proposals: [],
    violations: [],
  } as EscalationMessage;
}

describe("Property 33: replayed real-time messages apply at most once", () => {
  it("applies each sequence number at most once across an out-of-order/replayed stream", () => {
    fc.assert(
      fc.property(fc.array(fc.integer({ min: 0, max: 50 }), { maxLength: 200 }), (stream) => {
        let lastSeq: number | undefined;
        const applied: number[] = [];
        for (const seq of stream) {
          if (isFreshSeq(lastSeq, seq)) {
            applied.push(seq);
            lastSeq = seq;
          }
        }
        // No sequence number is ever applied twice...
        expect(new Set(applied).size).toBe(applied.length);
        // ...and applied sequences are strictly increasing (monotonic dedupe).
        for (let k = 1; k < applied.length; k++) {
          expect(applied[k]!).toBeGreaterThan(applied[k - 1]!);
        }
      }),
      { numRuns: 300 },
    );
  });

  it("treats a re-delivered sequence as stale once applied (never fresh twice)", () => {
    fc.assert(
      fc.property(
        fc.option(fc.integer({ min: -1, max: 100 }), { nil: undefined }),
        fc.integer({ min: 0, max: 100 }),
        (lastSeq, seq) => {
          const fresh = isFreshSeq(lastSeq, seq);
          if (fresh) {
            // After applying it, replaying the same seq is no longer fresh.
            expect(isFreshSeq(seq, seq)).toBe(false);
          } else {
            expect(seq).toBeLessThanOrEqual(lastSeq ?? -1);
          }
        },
      ),
      { numRuns: 300 },
    );
  });

  it("never appends the same decision twice (replay is a no-op returning same reference)", () => {
    fc.assert(
      fc.property(fc.uuid(), fc.array(fc.uuid(), { maxLength: 8 }), (dupId, others) => {
        const base: ReadonlyArray<EscalationEntry> = [];
        const once = appendEscalationEntry(base, mkMessage(dupId), 1);
        // Append unrelated entries, then replay the duplicate several times.
        let acc = once;
        for (const o of others) {
          if (o !== dupId) acc = appendEscalationEntry(acc, mkMessage(o), 2);
        }
        const lenBeforeReplay = acc.length;
        const afterReplay = appendEscalationEntry(acc, mkMessage(dupId), 3);
        expect(afterReplay).toBe(acc); // same reference — genuine no-op
        expect(afterReplay.length).toBe(lenBeforeReplay);
        expect(afterReplay.filter((e) => e.id === dupId).length).toBe(1);
      }),
      { numRuns: 200 },
    );
  });

  it("never resets an acted entry back to pending on replay", () => {
    fc.assert(
      fc.property(
        fc.uuid(),
        fc.constantFrom("approved", "rejected", "modified") as fc.Arbitrary<
          "approved" | "rejected" | "modified"
        >,
        (id, action) => {
          const appended = appendEscalationEntry([], mkMessage(id), 1);
          const acted = markEscalationActed(appended, id, action);
          expect(acted.find((e) => e.id === id)?.status).toBe("acted");

          // A replay of the same decision after it was acted must not resurrect
          // it as pending — append is a no-op on the existing (acted) entry.
          const replayed = appendEscalationEntry(acted, mkMessage(id), 2);
          const entry = replayed.find((e) => e.id === id);
          expect(entry?.status).toBe("acted");
          expect(entry?.acted_action).toBe(action);
        },
      ),
      { numRuns: 200 },
    );
  });
});
