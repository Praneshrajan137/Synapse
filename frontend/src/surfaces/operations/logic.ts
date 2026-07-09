import type { CalibrationBin, SloSeverity } from "@domain/operations";
import { formatConfidence } from "@lib/confidence";

/**
 * Pure logic for the Standing Watch surface (ADR-047) — extracted so the
 * honesty-bearing math is unit- and mutation-testable away from React.
 */

export interface OutcomeMix {
  readonly confirmed: number;
  readonly diverged: number;
  readonly unknown: number;
  readonly total: number;
}

/**
 * Derive the tri-state outcome mix from calibration data (FE-INV-041).
 *
 * `unknown` is carried straight through from `nUnknown` and is NEVER folded
 * into `confirmed`. `confirmed` is the expected confirmed count implied by the
 * reliability bins (Σ observed_rate·n), clamped to the scored total so rounding
 * can never imply more confirmations than there were scored decisions.
 */
export function outcomeMix(
  bins: ReadonlyArray<CalibrationBin>,
  nScored: number,
  nUnknown: number,
): OutcomeMix {
  const expectedConfirmed = bins.reduce(
    (s, b) => s + (b.observed_rate !== null ? b.observed_rate * b.n : 0),
    0,
  );
  const confirmed = Math.min(Math.max(0, Math.round(expectedConfirmed)), Math.max(0, nScored));
  const diverged = Math.max(0, nScored - confirmed);
  return { confirmed, diverged, unknown: Math.max(0, nUnknown), total: nScored + nUnknown };
}

/**
 * Format a confidence value as a fixed two-decimal string in the range
 * "0.00".."1.00" (Req 4.1). Re-exported from `@lib/confidence` — the lib layer
 * is the single source of truth so the design-system `ConfidenceChip` compound
 * and this surface share the identical formatter. The output ALWAYS matches
 * `^[01]\.\d{2}$` (Req 4.2, INV-CLR-011): colour can drain, the number never lies.
 */
export { formatConfidence };

/**
 * Exhaustive tri-state audit-chain integrity for one decision (Req 4.10,
 * FE-INV-039). Extracted as a pure helper from `ChainIntegrityChip` so the
 * mapping is unit- and mutation-testable away from React:
 *
 *   true            → "verified"   (single-row hash recompute matches)
 *   false           → "altered"    (row content changed since insert — tamper)
 *   null/undefined  → "pre-chain"  (pre-Sprint-9 legacy row, no chain values)
 *
 * A legacy (null) row is NEVER "verified" — absence of a chain is not proof of
 * integrity.
 */
export type ChainIntegrity = "verified" | "altered" | "pre-chain";

export function chainIntegrity(chainVerified: boolean | null | undefined): ChainIntegrity {
  if (chainVerified === null || chainVerified === undefined) return "pre-chain";
  return chainVerified ? "verified" : "altered";
}

// ─── Calibration statistical-power disclosure (FE-INV-043, Req 4.4/4.5/4.6) ──

/**
 * The provisional threshold (Req 4.4): a calibration display backed by fewer
 * than this many scored outcomes is too thin to read as a stable calibration
 * signal and MUST be flagged provisional. 30 is the statistical-power floor
 * below which the reliability curve / Brier can swing on a single outcome.
 */
export const PROVISIONAL_THRESHOLD = 30;

/**
 * Explicit no-value marker (Req 4.6). A null/absent metric renders this,
 * NEVER `0` — `0` is a real measured value and "—" is the *absence* of one.
 */
export const NO_VALUE_MARKER = "—";

/** "awaiting scored outcomes" copy (Req 4.5) — rendered when no scored
 *  evidence exists yet, rather than drawing a confident-looking empty curve. */
export const AWAITING_SCORED_OUTCOMES = "Awaiting scored outcomes";

/**
 * A calibration display is provisional if and only if it is backed by fewer
 * than {@link PROVISIONAL_THRESHOLD} scored outcomes (Req 4.4). Non-finite or
 * negative counts collapse to 0 and therefore read as provisional — absence of
 * a trustworthy count is never treated as a strong sample.
 */
export function isProvisional(nScored: number | null | undefined): boolean {
  const n = Number.isFinite(nScored) ? (nScored as number) : 0;
  return n < PROVISIONAL_THRESHOLD;
}

/**
 * Whether any scored evidence exists for a calibration metric (Req 4.5).
 * Zero (or a non-finite/absent count) means "awaiting scored outcomes".
 */
export function hasScoredEvidence(nScored: number | null | undefined): boolean {
  const n = Number.isFinite(nScored) ? (nScored as number) : 0;
  return n > 0;
}

/**
 * Render a calibration metric value honestly (Req 4.6): a null/undefined/
 * non-finite value returns the explicit {@link NO_VALUE_MARKER} ("—"), while a
 * real numeric value — INCLUDING `0` — is formatted to `digits` decimals. This
 * is the null-vs-zero distinction: "—" means "no scored evidence"; "0.000"
 * means "measured, and it is zero".
 */
export function formatMetric(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return NO_VALUE_MARKER;
  }
  return (value as number).toFixed(digits);
}

/**
 * Confidence samples for the distribution dotplot, segmenting synthetic from
 * real (FE-INV-044): synthetic rows are excluded unless explicitly included.
 */
export function confidenceSamples(
  rows: ReadonlyArray<{ readonly confidence: number; readonly is_synthetic?: boolean | undefined }>,
  includeSynthetic: boolean,
): number[] {
  return rows.filter((r) => includeSynthetic || !r.is_synthetic).map((r) => r.confidence);
}

// ─── SLO burn honesty (FE-INV-042, Req 10.9) ────────────────────────────────

/** The word rendered next to a tier's burn gauge — the non-color honesty
 *  channel (INV-CLR-011): colour can drain, the word never lies. */
const BURN_WORD: Record<SloSeverity, string> = {
  ok: "healthy",
  warning: "burning",
  critical: "critical",
  unknown: "burn unknown",
};

export function burnSeverityWord(sev: SloSeverity): string {
  return BURN_WORD[sev];
}

export interface BurnSeverityInput {
  /** Fast-window (1h) burn rate; `null` means "no evidence". */
  readonly fast: number | null;
  /** Slow-window (6h) burn rate; `null` means "no evidence". */
  readonly slow: number | null;
  /** The severity the metrics source reported for this tier. */
  readonly reported: SloSeverity;
  /** True when Prometheus is unreachable (fetch error) or reports `source: "unknown"`. */
  readonly sourceUnknown: boolean;
}

/**
 * Derive the severity actually shown for a tier's burn gauge (Req 10.9).
 *
 * Honesty precedence: an unreachable metrics source or a null window is NEVER
 * healthy and NEVER a fabricated 0 — it collapses to "unknown" regardless of
 * the severity the source claimed. Only when the source is reachable AND both
 * windows carry evidence do we trust the reported severity. This is what lets
 * Property 34 hold: null windows / unknown source → "burn unknown", never a
 * healthy bar.
 */
export function deriveBurnSeverity(i: BurnSeverityInput): SloSeverity {
  if (i.sourceUnknown) return "unknown";
  if (i.fast === null || i.slow === null) return "unknown";
  return i.reported;
}
