import type { CalibrationBin } from "@domain/operations";

/**
 * Pure logic for the Standing Watch surface (ADR-046) — extracted so the
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
 * Confidence samples for the distribution dotplot, segmenting synthetic from
 * real (FE-INV-044): synthetic rows are excluded unless explicitly included.
 */
export function confidenceSamples(
  rows: ReadonlyArray<{ readonly confidence: number; readonly is_synthetic?: boolean | undefined }>,
  includeSynthetic: boolean,
): number[] {
  return rows.filter((r) => includeSynthetic || !r.is_synthetic).map((r) => r.confidence);
}
