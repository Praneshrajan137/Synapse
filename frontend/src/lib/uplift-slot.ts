// Operations uplift slot — the pure, I/O-free resolver behind the reserved
// system-level uplift display (design "N. surfaces/operations — uplift slot",
// Req 17).
//
// Codebase reality: the Backend_Contract exposes NO system-level uplift measure
// today — it is a Cross_Boundary_Dependency. This module resolves whatever the
// contract hands it (a measure, or null when none exists) into an honest slot
// state: a `present` state carrying the value with its sample size, evaluation
// window, and "as of" timestamp when a real measure is exposed (Req 17.2), and
// an `awaiting` state when it is not (Req 17.3). The slot is NEVER hidden and a
// value is NEVER fabricated (Req 17.1, 17.4); when the measure is absent the
// caller records {@link UPLIFT_BACKEND_GAP} in the contract-fidelity drift
// report so the missing capability is tracked rather than concealed (Req 17.3).
//
// The function is TOTAL (every input yields a state) and PURE: it performs no
// I/O, reads no clock (the "as of" timestamp is carried on the measure), and
// never mutates its input — so every honesty guarantee is structurally
// property-testable.

/**
 * A system-level uplift measure as exposed by the Backend_Contract. Every
 * `present` render MUST disclose the sample size, window, and "as of" timestamp
 * alongside the value (Req 17.2) — so the raw measure carries all four.
 */
export interface UpliftMeasure {
  /** The measured system-level uplift value. */
  readonly value: number;
  /** How many observations back the measure — its statistical weight. */
  readonly sampleSize: number;
  /** Human-readable evaluation window disclosure (e.g. "Last 30 days"). */
  readonly windowLabel: string;
  /** ISO "as of" timestamp the measure reflects. */
  readonly asOf: string;
}

/**
 * The state of the reserved Operations uplift slot.
 *
 *  • `present`  — the contract exposed a trustworthy measure; render the value
 *    with its sample size, window, and "as of" (Req 17.2).
 *  • `awaiting` — no measure is exposed (a Cross_Boundary_Dependency); render
 *    "awaiting uplift measure" and record the backend gap (Req 17.3, 17.4).
 *
 * There is no third "hidden" state — the slot is always rendered (Req 17.1).
 */
export type UpliftSlotState =
  | { kind: "present"; value: number; sampleSize: number; windowLabel: string; asOf: string }
  | { kind: "awaiting" };

/**
 * Copy rendered in the slot when no uplift measure is exposed (Req 17.3).
 * Exposed so the surface and its tests share one source of truth.
 */
export const AWAITING_UPLIFT_MEASURE = "Awaiting uplift measure";

/**
 * The backend gap the Operations surface records when the Backend_Contract
 * exposes no system-level uplift measure (Req 17.3, 17.4). Consumed by the
 * contract-fidelity drift report (`spec/contract-fidelity/*`) so the missing
 * capability is *tracked*, never fabricated and never silently hidden.
 */
export const UPLIFT_BACKEND_GAP = {
  kind: "uplift" as const,
  name: "system-level-uplift-measure",
  rationale:
    "The Backend_Contract exposes no system-level uplift measure; the " +
    'Operations uplift slot renders "awaiting uplift measure" and records ' +
    "this Cross_Boundary_Dependency as a backend gap rather than fabricating a value.",
} as const;

/**
 * Resolve an uplift measure (or its absence) into an honest slot state.
 *
 * A `null` measure — or one whose disclosures cannot be trusted (a non-finite
 * value, a non-positive/non-finite sample size, or an empty window or "as of"
 * disclosure) — resolves to `awaiting` rather than a fabricated-looking
 * `present` value (Req 17.4). Only a fully-disclosed, finite measure is
 * presented (Req 17.2). The function is total: every input yields a state, so
 * the slot is never hidden (Req 17.1).
 */
export function resolveUpliftSlot(measure: UpliftMeasure | null): UpliftSlotState {
  if (measure === null) return { kind: "awaiting" };

  const disclosuresComplete =
    Number.isFinite(measure.value) &&
    Number.isFinite(measure.sampleSize) &&
    measure.sampleSize > 0 &&
    measure.windowLabel.trim() !== "" &&
    measure.asOf.trim() !== "";

  if (!disclosuresComplete) return { kind: "awaiting" };

  return {
    kind: "present",
    value: measure.value,
    // A sample size is a count; truncate any fractional part rather than
    // rendering a nonsensical fractional observation count.
    sampleSize: Math.trunc(measure.sampleSize),
    windowLabel: measure.windowLabel,
    asOf: measure.asOf,
  };
}
