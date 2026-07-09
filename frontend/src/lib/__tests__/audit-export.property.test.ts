// Feature: atlas-console-elevation, Property 39: Audit export contains decision-safe fields only
//
// Property 39 (Validates: Requirements 11.5) — `toAuditExportRow` (FE-INV-027)
// projects an AuditRow onto the decision-safe export shape:
//   • the exported keys are EXACTLY the decision-safe set (AUDIT_EXPORT_FIELDS),
//     regardless of what the source row carries,
//   • no operator PII / passthrough field (operator_token_ref, human_override,
//     or arbitrary extra keys) ever leaks into the export, and
//   • each safe field is copied faithfully, with a missing city collapsing to "".

import type { AuditRow } from "@domain/audit-row";
import { AUDIT_EXPORT_FIELDS, toAuditExportRow } from "@lib/audit-export";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const SAFE_FIELDS = new Set<string>(AUDIT_EXPORT_FIELDS);

// Extra keys that must NEVER appear in the export (operator PII + passthrough).
const piiKeyArb = fc.string({ minLength: 1 }).filter((k) => !SAFE_FIELDS.has(k));

const auditRowArb: fc.Arbitrary<AuditRow> = fc
  .record({
    audit_id: fc.uuid(),
    decision_id: fc.uuid(),
    tier: fc.constantFrom("tier_1", "tier_2", "tier_3", "tier_4"),
    phase_reached: fc.integer({ min: 1, max: 5 }),
    confidence: fc.double({ min: 0, max: 1, noNaN: true }),
    escalated: fc.boolean(),
    // city is optional on the wire — include present + absent.
    city: fc.option(fc.constantFrom("bengaluru", "mumbai"), { nil: undefined }),
    created_at: fc.date({ noInvalidDate: true }).map((d) => d.toISOString()),
    // Operator-PII / sensitive fields that live on AuditRow but MUST be dropped.
    operator_token_ref: fc.option(fc.string(), { nil: null }),
    human_override: fc.option(fc.dictionary(fc.string(), fc.jsonValue(), { maxKeys: 3 }), {
      nil: null,
    }),
    // Arbitrary passthrough keys (unknown additive fields) that must not leak.
    passthrough: fc.dictionary(piiKeyArb, fc.jsonValue(), { maxKeys: 4 }),
  })
  .map(({ passthrough, ...row }) => ({ ...passthrough, ...row }) as unknown as AuditRow);

describe("toAuditExportRow — Property 39: decision-safe fields only", () => {
  it("emits exactly the decision-safe key set, regardless of source shape", () => {
    fc.assert(
      fc.property(auditRowArb, (row) => {
        const exported = toAuditExportRow(row);
        expect(Object.keys(exported).sort()).toStrictEqual([...AUDIT_EXPORT_FIELDS].sort());
      }),
      { numRuns: 200 },
    );
  });

  it("never leaks operator PII or passthrough fields into the export", () => {
    fc.assert(
      fc.property(auditRowArb, (row) => {
        const exported = toAuditExportRow(row) as unknown as Record<string, unknown>;
        expect(Object.hasOwn(exported, "operator_token_ref")).toBe(false);
        expect(Object.hasOwn(exported, "human_override")).toBe(false);
        // Only decision-safe keys are present.
        for (const key of Object.keys(exported)) {
          expect(SAFE_FIELDS.has(key)).toBe(true);
        }
      }),
      { numRuns: 200 },
    );
  });

  it('copies each safe field faithfully and collapses a missing city to ""', () => {
    fc.assert(
      fc.property(auditRowArb, (row) => {
        const exported = toAuditExportRow(row);
        expect(exported.audit_id).toBe(row.audit_id);
        expect(exported.decision_id).toBe(row.decision_id);
        expect(exported.tier).toBe(row.tier);
        expect(exported.confidence).toBe(row.confidence);
        expect(exported.created_at).toBe(row.created_at);
        expect(exported.escalated).toBe(row.escalated);
        expect(exported.city).toBe(row.city ?? "");
      }),
      { numRuns: 200 },
    );
  });
});
