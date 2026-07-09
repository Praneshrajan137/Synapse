import fc from "fast-check";
import { describe, expect, it } from "vitest";
import {
  type ReconcileState,
  type Row,
  type RowStatus,
  emptyReconcileState,
  reconcile,
} from "../reconcile";

// Feature: atlas-console-effectiveness
// Property 8: After reconnect+replay the reconciled row set equals the
// deduplicated union of pre-drop and replayed state with no duplicate, lost, or
// reverted rows.
//
// For any pre-drop `ReconcileState` and any replay burst, `reconcile` produces a
// row set keyed by `seq` that is the deduplicated union of the pre-drop rows and
// the replayed rows: every pre-drop seq and every replayed seq is present exactly
// once (dedup by construction — no duplicates, none lost), and a row that was
// already `acted` is never reverted to `pending` (acted is monotonic/terminal —
// the merged status is `acted` iff the pre-drop row OR any replay entry for that
// seq is `acted`). The `decisionId` of a pre-existing row is preserved.
//
// **Validates: Requirements 7.2, 7.4**

const arbStatus: fc.Arbitrary<RowStatus> = fc.constantFrom<RowStatus>("pending", "acted");

// Small seq domain so pre-drop and replay overlap frequently, exercising the
// dedup/merge path rather than mostly-disjoint unions.
const arbRow = (seqArb: fc.Arbitrary<number>): fc.Arbitrary<Row> =>
  fc.record({
    seq: seqArb,
    decisionId: fc.string({ minLength: 1, maxLength: 8 }),
    status: arbStatus,
  });

const arbSeq = fc.integer({ min: 0, max: 20 });

// Pre-drop rows carry unique seqs (a Map keyed by seq holds one row per seq).
const arbPreDropRows = fc.uniqueArray(arbRow(arbSeq), {
  selector: (r) => r.seq,
  maxLength: 15,
});

// A replay burst may contain duplicate seqs and may overlap pre-drop seqs.
const arbReplay = fc.array(arbRow(arbSeq), { minLength: 0, maxLength: 30 });

function buildState(rows: readonly Row[]): ReconcileState {
  const map = new Map<number, Row>();
  for (const r of rows) {
    map.set(r.seq, r);
  }
  const lastAppliedSeq = rows.length === 0 ? -1 : Math.max(...rows.map((r) => r.seq));
  return { rows: map, lastAppliedSeq };
}

/** Acted-sticky reference: acted iff the pre-drop row OR any replay entry is acted. */
function expectedStatus(state: ReconcileState, replay: readonly Row[], seq: number): RowStatus {
  const fromState = state.rows.get(seq)?.status;
  const anyActed =
    fromState === "acted" || replay.some((r) => r.seq === seq && r.status === "acted");
  return anyActed ? "acted" : "pending";
}

describe("Property 8: reconcile yields the deduplicated union with acted rows preserved", () => {
  it("result key set equals the deduplicated union of pre-drop and replay seqs", () => {
    fc.assert(
      fc.property(arbPreDropRows, arbReplay, (preRows, replay) => {
        const state = buildState(preRows);
        const result = reconcile(state, replay);

        const union = new Set<number>([...preRows.map((r) => r.seq), ...replay.map((r) => r.seq)]);
        const resultSeqs = new Set<number>(result.rows.keys());

        // No duplicates (a Set/Map cannot hold a seq twice) and no seq lost or
        // spuriously introduced: the key sets are exactly equal.
        expect(result.rows.size).toBe(union.size);
        expect(resultSeqs).toEqual(union);
        // Every row is self-consistent: its map key matches its own seq.
        for (const [key, row] of result.rows) {
          expect(row.seq).toBe(key);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("no row is lost: every pre-drop and replayed seq survives reconciliation", () => {
    fc.assert(
      fc.property(arbPreDropRows, arbReplay, (preRows, replay) => {
        const state = buildState(preRows);
        const result = reconcile(state, replay);

        for (const r of preRows) {
          expect(result.rows.has(r.seq)).toBe(true);
        }
        for (const r of replay) {
          expect(result.rows.has(r.seq)).toBe(true);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("an already-acted row is never reverted, and status is the acted-sticky merge", () => {
    fc.assert(
      fc.property(arbPreDropRows, arbReplay, (preRows, replay) => {
        const state = buildState(preRows);
        const result = reconcile(state, replay);

        for (const seq of result.rows.keys()) {
          expect(result.rows.get(seq)?.status).toBe(expectedStatus(state, replay, seq));
        }
        // Explicit no-revert check: any seq acted before reconcile stays acted.
        for (const r of preRows) {
          if (r.status === "acted") {
            expect(result.rows.get(r.seq)?.status).toBe("acted");
          }
        }
      }),
      { numRuns: 100 },
    );
  });

  it("preserves the pre-existing decisionId of a row on merge", () => {
    fc.assert(
      fc.property(arbPreDropRows, arbReplay, (preRows, replay) => {
        const state = buildState(preRows);
        const result = reconcile(state, replay);

        for (const r of preRows) {
          // A pre-drop row keeps the decisionId the operator already acted on;
          // a replay carrying the same seq merges status only, never identity.
          expect(result.rows.get(r.seq)?.decisionId).toBe(r.decisionId);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("advances lastAppliedSeq to the highest sequence seen (the reconnect since_seq)", () => {
    fc.assert(
      fc.property(arbPreDropRows, arbReplay, (preRows, replay) => {
        const state = buildState(preRows);
        const result = reconcile(state, replay);

        const seqs = [state.lastAppliedSeq, ...replay.map((r) => r.seq)];
        expect(result.lastAppliedSeq).toBe(Math.max(...seqs));
      }),
      { numRuns: 100 },
    );
  });

  it("is idempotent: replaying the reconciled rows again changes nothing", () => {
    fc.assert(
      fc.property(arbPreDropRows, arbReplay, (preRows, replay) => {
        const once = reconcile(buildState(preRows), replay);
        const twice = reconcile(once, [...once.rows.values()]);

        expect(twice.rows.size).toBe(once.rows.size);
        expect(twice.lastAppliedSeq).toBe(once.lastAppliedSeq);
        for (const [seq, row] of once.rows) {
          expect(twice.rows.get(seq)).toEqual(row);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("reconciling an empty replay against an empty state is the identity", () => {
    const result = reconcile(emptyReconcileState(), []);
    expect(result.rows.size).toBe(0);
    expect(result.lastAppliedSeq).toBe(-1);
  });
});
