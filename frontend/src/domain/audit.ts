import type { Decision } from "@/domain/decision";

/**
 * Audit domain — the immutable provenance record (invariant I-4).
 *
 * An audit row is a decision plus tamper-evidence: a content hash and
 * the DB-immutable timestamp. The Replay surface renders these with
 * deliberate ceremony (tenet T-1).
 */

export interface AuditRow {
  readonly id: string;
  readonly decision: Decision;
  /** Content hash for tamper-evidence (sha256, hex). */
  readonly contentHash: string;
  /** Epoch ms when the row became DB-immutable. */
  readonly immutableSince: number;
  /** Audit trace breadcrumbs, e.g. ["tier=tier_3", "phase=4", ...]. */
  readonly trace: readonly string[];
}

/** A tick on the Replay scrubber timeline. */
export interface AuditTimelineEntry {
  readonly auditId: string;
  readonly decisionId: string;
  readonly tier: Decision["tier"];
  readonly escalated: boolean;
  readonly createdAt: number;
  readonly summary: string;
}
