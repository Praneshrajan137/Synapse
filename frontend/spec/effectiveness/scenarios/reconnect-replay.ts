/**
 * Resilience_Scenario — reconnect and replay reconciliation (Req 7).
 *
 * The harness renders a populated decision surface, has the operator act on one
 * decision, then drops the real-time connection. On reconnect the Console
 * requests replay from its last applied sequence (`since_seq`, Req 7.1) and the
 * harness delivers a replay burst that:
 *
 *   - re-carries the already-acted decision as a stale `pending`, proving the
 *     acted-never-reverted guarantee — an already-acted decision stays acted
 *     and is never reverted to pending (Req 7.2);
 *   - re-carries a sequence the client already holds, proving dedup — a
 *     replayed `seq` never renders a duplicate row (Req 7.1/7.4);
 *   - carries fresh sequences beyond `since_seq` that must be applied once.
 *
 * A resumed live stream then delivers further fresh sequences (Req 7.5). When
 * the scenario completes the rendered row set must equal the deduplicated union
 * of the pre-drop and replayed/live state — no duplicate, lost, or reverted
 * rows (Req 7.4).
 *
 * This descriptor's `replay` plan is the transport-free single source of truth
 * the `reconnect-replay.resilience.spec.ts` E2E drives against (same pattern as
 * `firehose-stress.ts`'s `rates` and `fault-transition.ts`'s `faultChain`), so
 * the adverse condition and its pass criteria stay named and testable rather
 * than hand-kept per test. It maps one-to-one onto the pure `reconcile` reducer
 * (`src/lib/reconcile.ts`, task 8.1) so the E2E's rendered-output assertions and
 * the model-level property test (task 8.2) prove the same guarantees at both
 * ends. The seeded channel (`DecisionEnvelope`) is the Mission Control decision
 * stream so the reconciliation runs against a surface that renders rows.
 */

import { WEB_VITALS_BUDGET, type ResilienceScenario } from "./resilience-types";

export const RECONNECT_REPLAY: ResilienceScenario = {
  id: "resilience.reconnect-replay",
  kind: "reconnect-replay",
  seed: 70701,
  title: "Reconnect + replay keeps acted decisions acted with no duplicate rows",
  narrative:
    "Render a populated decision surface with one already-acted decision, drop the connection, and on reconnect request replay from since_seq; the replay burst re-carries the acted decision as a stale pending and re-carries an already-held sequence, then a live stream resumes. At the rendered output the acted decision stays acted (never reverts to pending), no replayed sequence renders a duplicate row, and the final row set equals the deduplicated union of the pre-drop and replayed/live state with no lost or reverted rows.",
  budget: WEB_VITALS_BUDGET,
  seedSchemaIds: ["DecisionEnvelope"],
  replay: {
    // Baseline: three rows rendered before the drop; the operator has acted on
    // seq 2. The highest applied sequence is 3, so since_seq === 3 (Req 7.1).
    preDrop: [
      { seq: 1, decisionId: "dec-1", status: "pending" },
      { seq: 2, decisionId: "dec-2", status: "acted" },
      { seq: 3, decisionId: "dec-3", status: "pending" },
    ],
    sinceSeq: 3,
    // The replay burst re-carries seq 2 (the acted decision) as a STALE pending
    // — reconcile must keep it acted (Req 7.2) — and re-carries seq 3 (an
    // already-held row) — dedup must not render it twice (Req 7.1/7.4). Seq 4
    // and 5 are fresh sequences past since_seq that must be applied once.
    replay: [
      { seq: 2, decisionId: "dec-2", status: "pending" },
      { seq: 3, decisionId: "dec-3", status: "pending" },
      { seq: 4, decisionId: "dec-4", status: "pending" },
      { seq: 5, decisionId: "dec-5", status: "pending" },
    ],
    // The resumed live stream appends fresh sequences after the burst drains.
    live: [
      { seq: 6, decisionId: "dec-6", status: "pending" },
      { seq: 7, decisionId: "dec-7", status: "pending" },
    ],
  },
};
