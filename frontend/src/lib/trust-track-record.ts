// Trust_Track_Record aggregation — the pure, I/O-free model behind the
// authenticated operator's longitudinal view of their own past judgments and
// how they turned out (design "J. lib — trust-track-record aggregation",
// Req 11).
//
// Codebase reality (design finding #7): there is NO per-operator longitudinal
// `decision_outcomes` endpoint today. This module aggregates only the scored
// outcomes it is handed — distilled from the signal that DOES exist
// (`DecisionDetailResponse.outcome`, `CalibrationResponse` bins, and
// `AuditRow.operator_token_ref`) — and renders an honest "awaiting scored
// outcomes" state when none exist rather than fabricating or zeroing a record
// (Req 11.5).
//
// The function is TOTAL (every input yields a record) and PURE: it performs no
// I/O, reads no clock (the "as of" timestamp is passed in), and never mutates
// its inputs. Every honesty guarantee is derived structurally so it can be
// property-tested (tasks 13.3–13.5):
//   • outcomes partition into exactly confirmed / diverged / unknown, and
//     `unknown` is NEVER folded into `confirmed` (Req 11.3).
//   • low-confidence-approved outcomes are reported as distinct confirmed vs
//     diverged counts (Req 11.2).
//   • sample size, evaluation window, and an "as of" timestamp are always
//     disclosed, and the record is flagged provisional below MIN_SCORED
//     (Req 11.4).
//   • Synthetic decisions are excluded by default; a labelled include toggle
//     adds exactly those records (Req 11.6).

/** The three distinct realized-outcome states a scored decision can hold.
 *  `unknown` = not yet realized; it is a first-class state and is never folded
 *  into `confirmed` (Req 11.3). */
export type OutcomeState = "confirmed" | "diverged" | "unknown";

/**
 * A single scored outcome for one of the operator's past judgments, distilled
 * from the available backend signal.
 */
export interface ScoredOutcome {
  /** The decision this outcome belongs to. */
  readonly decisionId: string;
  /** The operator's opaque token reference — never a raw username
   *  (inherited FE-INV-019). */
  readonly operatorTokenRef: string;
  /** Whether the operator approved this decision while its confidence was below
   *  the autonomy gate — the low-confidence-approval subset Req 11.2 breaks out. */
  readonly approvedAtLowConfidence: boolean;
  /** The realized outcome state. */
  readonly outcome: OutcomeState;
  /** Whether the underlying decision is Synthetic (excluded by default, Req 11.6). */
  readonly isSynthetic: boolean;
}

/**
 * The aggregated, disclosure-complete track record rendered for the operator.
 *
 * `confirmed + diverged + unknown === sampleSize` always holds (the tri-state
 * partition, Req 11.3). The `lowConfidenceApproved*` fields are the distinct
 * confirmed/diverged/unknown breakdown of the low-confidence-approval subset
 * that Req 11.2 requires ("12 approved → 10 confirmed, 2 diverged").
 */
export interface TrustTrackRecord {
  readonly confirmed: number;
  readonly diverged: number;
  /** Distinct; never folded into `confirmed` (Req 11.3). */
  readonly unknown: number;

  /** Total low-confidence-approved outcomes in scope (Req 11.2). */
  readonly lowConfidenceApproved: number;
  /** Low-confidence-approved outcomes later confirmed (Req 11.2). */
  readonly lowConfidenceApprovedConfirmed: number;
  /** Low-confidence-approved outcomes later diverged (Req 11.2). */
  readonly lowConfidenceApprovedDiverged: number;
  /** Low-confidence-approved outcomes not yet realized — distinct, never folded
   *  into confirmed (Req 11.2, 11.3). */
  readonly lowConfidenceApprovedUnknown: number;

  /** Total scored outcomes in scope = confirmed + diverged + unknown (Req 11.4). */
  readonly sampleSize: number;
  /** Human-readable evaluation window disclosure (Req 11.4). */
  readonly windowLabel: string;
  /** ISO "as of" timestamp the aggregate reflects (Req 11.4). */
  readonly asOf: string;
  /** True iff 0 < sampleSize < MIN_SCORED — too few to be trusted (Req 11.4). */
  readonly provisional: boolean;
  /** True iff no scored outcomes exist → render "awaiting scored outcomes"
   *  rather than a fabricated/zeroed record (Req 11.5). */
  readonly awaiting: boolean;
  /** Whether Synthetic decisions are included in this aggregate (labelled toggle,
   *  default false, Req 11.6). */
  readonly includeSynthetic: boolean;
}

/**
 * The minimum number of scored outcomes required before the track record is
 * presented as anything other than provisional (Req 11.4).
 *
 * Below this count a confirmation/divergence ratio is dominated by sampling
 * noise, so the display must flag itself provisional rather than imply a
 * calibrated track record. Twenty mirrors the "enough to be indicative, not yet
 * conclusive" threshold used for calibration evidence elsewhere in the Console.
 */
export const MIN_SCORED = 20;

/** Default evaluation-window disclosure when a caller does not supply one. */
export const DEFAULT_WINDOW_LABEL = "Last 90 days";

/**
 * Copy rendered when no scored outcomes exist for the operator in the window
 * (Req 11.5). Exposed so the surface and its tests share one source of truth.
 */
export const AWAITING_SCORED_OUTCOMES = "Awaiting scored outcomes";

/**
 * Aggregate a set of scored outcomes into an operator Trust_Track_Record.
 *
 * By default Synthetic decisions are excluded (Req 11.6); pass
 * `includeSynthetic = true` (the labelled toggle) to add exactly those records.
 * The aggregate partitions the in-scope outcomes into the three distinct states
 * (Req 11.3), breaks out the low-confidence-approval subset (Req 11.2), and
 * discloses sample size, window, and "as of" — flagging the record provisional
 * below {@link MIN_SCORED} and awaiting when empty (Req 11.4, 11.5).
 *
 * @param outcomes        The scored outcomes already scoped to the evaluation window.
 * @param includeSynthetic Whether to include Synthetic decisions (Req 11.6).
 * @param nowIso          The "as of" timestamp to disclose (Req 11.4). Passed in
 *                        to keep the function pure and deterministic.
 * @param windowLabel     Human-readable window disclosure (Req 11.4).
 */
export function aggregateTrack(
  outcomes: readonly ScoredOutcome[],
  includeSynthetic: boolean,
  nowIso: string,
  windowLabel: string = DEFAULT_WINDOW_LABEL,
): TrustTrackRecord {
  // Synthetic decisions are excluded by default; the labelled toggle adds
  // exactly those records and no others (Req 11.6).
  const scoped = includeSynthetic ? outcomes : outcomes.filter((o) => !o.isSynthetic);

  let confirmed = 0;
  let diverged = 0;
  let unknown = 0;
  let lowConfidenceApproved = 0;
  let lowConfidenceApprovedConfirmed = 0;
  let lowConfidenceApprovedDiverged = 0;
  let lowConfidenceApprovedUnknown = 0;

  for (const o of scoped) {
    // Tri-state partition — `unknown` is tallied distinctly and never folded
    // into `confirmed` (Req 11.3).
    switch (o.outcome) {
      case "confirmed":
        confirmed += 1;
        break;
      case "diverged":
        diverged += 1;
        break;
      case "unknown":
        unknown += 1;
        break;
    }

    // Distinct confirmed-vs-diverged breakdown of the low-confidence-approval
    // subset (Req 11.2).
    if (o.approvedAtLowConfidence) {
      lowConfidenceApproved += 1;
      switch (o.outcome) {
        case "confirmed":
          lowConfidenceApprovedConfirmed += 1;
          break;
        case "diverged":
          lowConfidenceApprovedDiverged += 1;
          break;
        case "unknown":
          lowConfidenceApprovedUnknown += 1;
          break;
      }
    }
  }

  const sampleSize = scoped.length;
  const awaiting = sampleSize === 0;
  // Provisional only when there IS evidence but not enough of it — an empty set
  // is `awaiting`, not `provisional` (Req 11.4, 11.5).
  const provisional = sampleSize > 0 && sampleSize < MIN_SCORED;

  return {
    confirmed,
    diverged,
    unknown,
    lowConfidenceApproved,
    lowConfidenceApprovedConfirmed,
    lowConfidenceApprovedDiverged,
    lowConfidenceApprovedUnknown,
    sampleSize,
    windowLabel,
    asOf: nowIso,
    provisional,
    awaiting,
    includeSynthetic,
  };
}
