// Interruption_Precision — the North-Star effectiveness metric (Req 13).
//
// WHY THIS EXISTS
// ---------------
// Of the decisions for which the Atlas_Console demanded human judgment
// (escalated / interrupted the operator), Interruption_Precision is the
// fraction whose review was *warranted* — i.e. the review changed the outcome,
// or it confirmed a genuinely uncertain, irreversible, or high-blast-radius
// decision. Formally:
//
//     Interruption_Precision = warranted interruptions ÷ total interruptions
//
// over a defined window (Req 13.1). It is the single most important
// effectiveness metric: it holds the Console to demanding human judgment only
// when it is worth it, and it is recorded in the Effectiveness_Scorecard as the
// primary (North-Star) metric (Req 13.4) and gated by the Effectiveness_Ratchet
// (Req 13.3, wired in task 15.2).
//
// HONEST CEILING (Req 13.5 / 20.5)
// --------------------------------
// The value this module computes is measured over a `Scripted_Proxy` — the
// seeded Task_Completion_Test scenarios, not real operators. A scripted proxy
// proves an operator path EXISTS and is EFFICIENT and lets the metric be
// computed deterministically, but it CANNOT model the false alarms and missed
// stakes a real operator experiences. The real-world Interruption_Precision
// therefore requires validation with real operators (RITE testing with 3–5
// operators). {@link INTERRUPTION_PRECISION_PROXY_CEILING} states this verbatim
// and is surfaced wherever the metric is presented.
//
// Every function here is pure, total, and side-effect-free so the property test
// (Property 18, task 15.3) and the scorecard emitter share one implementation.

/**
 * A single interruption the Atlas_Console raised — a decision for which it
 * demanded human judgment. `warranted` is true when the human review was worth
 * it: the review changed the outcome, or it confirmed a genuinely uncertain,
 * irreversible, or high-blast-radius decision (Req 13.1).
 */
export interface Interruption {
  readonly warranted: boolean;
}

/**
 * Interruption_Precision = warranted ÷ total over the window (Req 13.1).
 *
 * The result always lies within `[0, 1]`. When there are no interruptions
 * (`total === 0`) the ratio is undefined, so this returns `null` rather than
 * `0/0` or a fabricated value — the same honest-absence convention the
 * scorecard's reserved field uses. Pure and total.
 */
export function interruptionPrecision(interruptions: readonly Interruption[]): number | null {
  const total = interruptions.length;
  if (total === 0) return null;
  let warranted = 0;
  for (const interruption of interruptions) {
    if (interruption.warranted) warranted += 1;
  }
  return warranted / total;
}

/**
 * The honest ceiling recorded wherever Interruption_Precision is presented
 * (Req 13.5, 20.5). Kept verbatim so the scorecard, the harness report, and any
 * surface that shows the North-Star metric state the identical caveat.
 */
export const INTERRUPTION_PRECISION_PROXY_CEILING =
  "Interruption_Precision is measured over a Scripted_Proxy of seeded scenarios, not real " +
  "operators. It proves the metric is computable and holds on the seeded paths, but its " +
  "real-world value requires validation with real operators (RITE testing with 3–5 operators).";

/**
 * The interruptions the Atlas_Console raised across the seeded Task_Completion_Test
 * scenarios (`spec/effectiveness/scenarios/*.ts`), over which the North-Star
 * metric is computed (Req 13.2). This is the `Scripted_Proxy` sample: a
 * deterministic, documented set standing in for the real stream of operator
 * interruptions, bounded by {@link INTERRUPTION_PRECISION_PROXY_CEILING}.
 *
 * Each entry names the seeded scenario that raised it and why the review was or
 * was not warranted, so the sample is auditable rather than an opaque constant.
 */
export const SEEDED_INTERRUPTIONS: readonly Interruption[] = [
  // jtbd.resolve-escalation (seed 30101): the seeded escalation is an
  // irreversible / high-blast decision — the review confirmed genuine stakes.
  { warranted: true },
  // jtbd.catch-disruption (seed 30505): the Console interrupted to flag a
  // cascading disruption in time — the review changed the outcome.
  { warranted: true },
  // jtbd.adjust-steering (seed 30404): the Console demanded confirmation of a
  // steering change with a broad blast radius — genuine stakes.
  { warranted: true },
  // jtbd.identify-degraded-agent (seed 30202): the Console interrupted on an
  // agent-health blip that resolved on its own — the review was NOT warranted
  // (a false interruption the scripted proxy models so the metric has headroom).
  { warranted: false },
];

/**
 * Interruption_Precision computed over the {@link SEEDED_INTERRUPTIONS}
 * scripted proxy (Req 13.2). This is the North-Star value the
 * Task_Completion_Tests record in the Effectiveness_Scorecard's
 * `interruptionPrecision` field. `null` only if the seeded sample is empty.
 */
export function seededInterruptionPrecision(): number | null {
  return interruptionPrecision(SEEDED_INTERRUPTIONS);
}
