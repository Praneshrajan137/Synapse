// FE-INV-027 — decision-safe audit export. The Audit Vault CSV export must carry
// ONLY the decision-safe field set and never leak operator personally-identifying
// data (Req 11.5). This module is the single, property-testable source of truth
// for the export row shape so the field set can never drift from the CSV writer.
//
// Decision-safe fields (exactly): audit_id, decision_id, tier, confidence, city,
// created_at, escalated. Explicitly excluded operator/PII-adjacent fields that
// live on AuditRow: operator_token_ref, human_override, and any passthrough keys.

import type { AuditRow } from "@domain/audit-row";
import type { Tier } from "@domain/primitives";

/**
 * The exact, ordered set of keys emitted by a decision-safe audit export.
 * Used as the CSV header and as the property-test oracle for Property 39.
 */
export const AUDIT_EXPORT_FIELDS = [
  "audit_id",
  "decision_id",
  "tier",
  "confidence",
  "city",
  "created_at",
  "escalated",
] as const;

export type AuditExportField = (typeof AUDIT_EXPORT_FIELDS)[number];

/**
 * A decision-safe export row — the complete, closed shape of an exported audit
 * record. It contains no operator identity, override reason, or other PII.
 */
export interface AuditExportRow {
  audit_id: string;
  decision_id: string;
  tier: Tier;
  confidence: number;
  city: string;
  created_at: string;
  escalated: boolean;
}

/**
 * Project an {@link AuditRow} onto the decision-safe export shape. Pure and
 * total: it reads only the seven decision-safe fields and constructs a fresh
 * object literal, so no operator PII or passthrough field can ever be carried
 * into the export regardless of what the source row contains.
 *
 * `city` is optional on the wire; a missing city collapses to an empty string
 * so the exported column is always present and never `undefined`.
 */
export function toAuditExportRow(row: AuditRow): AuditExportRow {
  return {
    audit_id: row.audit_id,
    decision_id: row.decision_id,
    tier: row.tier,
    confidence: row.confidence,
    city: row.city ?? "",
    created_at: row.created_at,
    escalated: row.escalated,
  };
}
