/**
 * SYNAPSE Atlas Console — controlled-vocabulary override reason codes.
 *
 * Plan §5.6: every operator override is tagged with one of these codes
 * before it lands in `audit_consensus.human_override`. New codes
 * require an ADR review (kept here so reviewers see the diff).
 *
 * I-4 (append-only): never delete a code; deprecate by leaving it in
 * place and removing it from the live picker via the `deprecated` flag.
 */
export interface OverrideCode {
  readonly code: string;
  readonly label: string;
  readonly description: string;
  readonly severity: "info" | "warn" | "alert" | "critical";
  readonly deprecated?: boolean;
}

export const OVERRIDE_CODES: readonly OverrideCode[] = [
  {
    code: "OVR-RISK-INSUFFICIENT-EVIDENCE",
    label: "Insufficient evidence",
    description: "Operator declined the proposal because the evidence base was thin.",
    severity: "warn",
  },
  {
    code: "OVR-COMPLIANCE-FSSAI",
    label: "FSSAI compliance",
    description: "Override required to satisfy FSSAI freshness/labelling rules.",
    severity: "alert",
  },
  {
    code: "OVR-COMPLIANCE-DPDPA",
    label: "DPDPA boundary",
    description: "Override required to keep PII inside the data-residency boundary.",
    severity: "alert",
  },
  {
    code: "OVR-OPS-WEATHER",
    label: "Weather window",
    description: "Operator adjusted action because of a weather window the model did not see.",
    severity: "info",
  },
  {
    code: "OVR-OPS-SUPPLIER-COMM",
    label: "Supplier communication",
    description: "Override based on out-of-band supplier signal.",
    severity: "info",
  },
  {
    code: "OVR-SAFETY-PRICE-CAP",
    label: "Pricing essential cap",
    description: "Pricing recommendation breached the I-6 essential cap (≤ 1.3×).",
    severity: "critical",
  },
  {
    code: "OVR-SAFETY-FRESHNESS",
    label: "Freshness floor",
    description: "Inventory action would have shipped product below the freshness floor.",
    severity: "critical",
  },
  {
    code: "OVR-OTHER",
    label: "Other (free-text required)",
    description: "Last-resort code — the reason field must be filled in by the operator.",
    severity: "info",
  },
];

export const OVERRIDE_CODES_INDEX: ReadonlyMap<string, OverrideCode> = new Map(
  OVERRIDE_CODES.map((c) => [c.code, c]),
);
