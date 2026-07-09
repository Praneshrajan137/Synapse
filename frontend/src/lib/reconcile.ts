/**
 * Acted-never-reverted reconcile reducer — design "F. lib — reconcile reducer
 * (Req 7)".
 *
 * On reconnect the Atlas_Console requests replay from its last applied sequence
 * (`since_seq`, Req 7.1) and must reconcile the replayed burst against the rows
 * it already holds. This module is the pure core of that reconciliation:
 *
 *   • {@link reconcile} merges a replay burst into state, deduplicating by
 *     `seq` (rows are keyed by `seq`, so a replayed sequence can never produce
 *     a duplicate row — Req 7.2/7.4) and treating `acted` as a monotonic,
 *     terminal state: an already-acted decision is never reverted to `pending`,
 *     regardless of what the replay says (Req 7.2). The reconciled set is the
 *     deduplicated union of the pre-drop and replayed rows with no lost or
 *     reverted rows (Req 7.4).
 *
 *   • {@link reconnectDelayMs} produces the bounded Full-Jitter reconnect delay
 *     (Req 7.3), reusing the exact `fullJitterDelay` policy `ws-multiplex`
 *     schedules reconnects with, so the reducer and the live transport agree on
 *     the backoff shape.
 *
 * The dedup decision reuses `isFreshSeq` from `transport/ws-multiplex.ts` so
 * "which sequence advances the `since_seq` watermark" is decided by the same
 * pure predicate the live socket uses (FE-INV-008/037).
 *
 * Everything here is pure and I/O-free: the rendered-output guarantee (that
 * acted decisions stay acted and no duplicate rows appear) is verified end to
 * end by the Resilience_Scenario E2E in task 8.4; this module is the unit the
 * property tests in task 8.2 (dedup union) and 8.3 (bounded backoff) exercise.
 */

import { fullJitterDelay } from "@lib/jitter-retry";
import { isFreshSeq } from "@transport/ws-multiplex";

/** The two terminal render states a reconciled row can hold. */
export type RowStatus = "pending" | "acted";

/** A single decision row identified by its stream `seq`. */
export interface Row {
  readonly seq: number;
  readonly decisionId: string;
  readonly status: RowStatus;
}

/**
 * The reconcilable slice of client state. `rows` is keyed by `seq`, so dedup is
 * structural — a replayed sequence overwrites (or, per the acted-sticky rule,
 * merges into) the existing entry rather than appending a duplicate.
 * `lastAppliedSeq` is the `since_seq` the client requests on reconnect (Req
 * 7.1); it is the highest sequence applied so far, or `-1` when nothing has
 * been applied yet.
 */
export interface ReconcileState {
  readonly rows: ReadonlyMap<number, Row>;
  readonly lastAppliedSeq: number;
}

/** A fresh, empty reconcile state whose `since_seq` requests everything. */
export function emptyReconcileState(): ReconcileState {
  return { rows: new Map(), lastAppliedSeq: -1 };
}

/**
 * The `since_seq` value a client should send on reconnect to request replay
 * from just after its last applied sequence (Req 7.1).
 */
export function sinceSeq(state: ReconcileState): number {
  return state.lastAppliedSeq;
}

/**
 * `acted` is a monotonic, terminal state: once a decision is acted it stays
 * acted. Merging two views of the same row therefore yields `acted` iff either
 * side is acted, so a replay carrying a stale `pending` can never revert an
 * already-acted row (Req 7.2) and a replay carrying a fresh `acted` upgrades a
 * locally-pending row.
 */
function mergeStatus(a: RowStatus, b: RowStatus): RowStatus {
  return a === "acted" || b === "acted" ? "acted" : "pending";
}

/**
 * Merges a replay burst into `state`.
 *
 * Rows are keyed by `seq`, so the result is the deduplicated union of the
 * pre-drop rows and the replayed rows — no sequence appears twice (Req
 * 7.2/7.4). For a sequence already present, the row's status is merged with
 * {@link mergeStatus} so an acted decision is never reverted to pending (Req
 * 7.2); the original `decisionId` is preserved because the existing row was the
 * one the operator already acted on. The `since_seq` watermark advances to the
 * highest sequence seen via {@link isFreshSeq}, the same freshness predicate
 * `ws-multiplex` applies to live messages.
 */
export function reconcile(state: ReconcileState, replay: readonly Row[]): ReconcileState {
  const rows = new Map(state.rows);
  let lastAppliedSeq = state.lastAppliedSeq;

  for (const row of replay) {
    const existing = rows.get(row.seq);
    if (existing) {
      const status = mergeStatus(existing.status, row.status);
      if (status !== existing.status) {
        rows.set(row.seq, { ...existing, status });
      }
    } else {
      rows.set(row.seq, row);
    }
    if (isFreshSeq(lastAppliedSeq, row.seq)) {
      lastAppliedSeq = row.seq;
    }
  }

  return { rows, lastAppliedSeq };
}

/** Options for {@link reconnectDelayMs}, mirroring the `ws-multiplex` defaults. */
export interface ReconnectBackoffOptions {
  readonly baseMs?: number;
  readonly capMs?: number;
  /** Injectable RNG for deterministic property tests; defaults to `Math.random`. */
  readonly random?: () => number;
}

/** Base delay, matching `ws-multiplex` `baseReconnectMs` default. */
const RECONNECT_BASE_MS = 500;
/** Cap, matching `ws-multiplex` `maxReconnectMs` default. */
const RECONNECT_CAP_MS = 30_000;

/**
 * Bounded Full-Jitter reconnect delay for `attempt` (0-based): a uniform draw
 * from `[0, min(base · 2^attempt, cap)]` (Req 7.3). Delegates to the shared
 * `fullJitterDelay` policy so the reducer's backoff is identical to the one
 * `ws-multiplex` schedules reconnects with.
 */
export function reconnectDelayMs(attempt: number, opts: ReconnectBackoffOptions = {}): number {
  const baseMs = opts.baseMs ?? RECONNECT_BASE_MS;
  const capMs = opts.capMs ?? RECONNECT_CAP_MS;
  return fullJitterDelay(
    attempt,
    opts.random ? { baseMs, capMs, random: opts.random } : { baseMs, capMs },
  );
}
