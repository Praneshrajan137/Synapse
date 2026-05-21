/**
 * SYNAPSE Atlas Console — Audit Vault search-param schema.
 *
 * Bound to TanStack Router's `validateSearch` so every filter, the
 * open-decision id, and the PII-reveal flag are URL-driven.
 */
import { z } from "zod";

import { OVERRIDE_CODES } from "./override-codes";

const overrideCodes = OVERRIDE_CODES.map((c) => c.code) as [string, ...string[]];

export const AuditSearchSchema = z.object({
  user: z.string().min(1).max(64).optional(),
  since: z.string().datetime({ offset: true }).optional(),
  until: z.string().datetime({ offset: true }).optional(),
  tier: z.enum(["tier_1", "tier_2", "tier_3", "tier_4"]).optional(),
  override_code: z.enum(overrideCodes).optional(),
  /** Decision id for the open detail view. */
  open: z.string().uuid().optional(),
  /** Set when the operator has reauthed for PII reveal. */
  pii: z.coerce.boolean().optional(),
});
export type AuditSearch = z.infer<typeof AuditSearchSchema>;
