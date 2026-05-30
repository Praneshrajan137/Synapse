import { CONFIDENCE_GATE } from "@lib/chromatics";
import type { EscalationEntry } from "@state/escalation.store";
import { useMemo } from "react";

/**
 * CalibrationMirror — closes the trust-calibration loop (SENSORIUM P1).
 *
 * The danger of human-on-the-loop supervision is mis-calibrated trust:
 *   • OVERTRUST  — rubber-stamping low-confidence escalations (approving things
 *     the machine itself flagged as doubtful).
 *   • UNDERTRUST — overriding high-confidence decisions the machine got right,
 *     which destroys the value of autonomy.
 *
 * This panel reflects the operator's OWN behaviour back at them, computed
 * honestly from this session's acted escalations (P7): it never invents an
 * outcome/"hit-rate" we don't have. It shows the average confidence of the
 * decisions you APPROVED vs the ones you OVERRODE, and flags the two failure
 * modes when the pattern appears.
 */

export interface CalibrationSummary {
  readonly approvedCount: number;
  readonly overriddenCount: number;
  readonly avgConfidenceApproved: number | null;
  readonly avgConfidenceOverridden: number | null;
  readonly signal: "calibrated" | "overtrust" | "undertrust" | "insufficient";
}

const MIN_SAMPLE = 3;

export function summarizeCalibration(entries: ReadonlyArray<EscalationEntry>): CalibrationSummary {
  const acted = entries.filter((e) => e.status === "acted" && e.acted_action);
  const approved = acted.filter((e) => e.acted_action === "approved");
  const overridden = acted.filter(
    (e) => e.acted_action === "rejected" || e.acted_action === "modified",
  );

  const mean = (xs: ReadonlyArray<EscalationEntry>): number | null =>
    xs.length === 0 ? null : xs.reduce((acc, e) => acc + e.message.confidence, 0) / xs.length;

  const avgConfidenceApproved = mean(approved);
  const avgConfidenceOverridden = mean(overridden);

  let signal: CalibrationSummary["signal"] = "calibrated";
  if (acted.length < MIN_SAMPLE) {
    signal = "insufficient";
  } else if (
    avgConfidenceApproved !== null &&
    approved.length >= MIN_SAMPLE &&
    avgConfidenceApproved < CONFIDENCE_GATE.low
  ) {
    signal = "overtrust";
  } else if (
    avgConfidenceOverridden !== null &&
    overridden.length >= MIN_SAMPLE &&
    avgConfidenceOverridden >= CONFIDENCE_GATE.high
  ) {
    signal = "undertrust";
  }

  return {
    approvedCount: approved.length,
    overriddenCount: overridden.length,
    avgConfidenceApproved,
    avgConfidenceOverridden,
    signal,
  };
}

const SIGNAL_READ: Record<CalibrationSummary["signal"], string> = {
  calibrated: "Calibrated — your interventions track the machine's own confidence.",
  overtrust: "Overtrust watch — you're approving low-confidence escalations.",
  undertrust: "Undertrust watch — you're overriding high-confidence decisions.",
  insufficient: "Not enough acted escalations this session to assess calibration.",
};

const SIGNAL_TONE: Record<CalibrationSummary["signal"], string> = {
  calibrated: "text-signal-success",
  overtrust: "text-signal-warning",
  undertrust: "text-signal-warning",
  insufficient: "text-ink-subtle",
};

function pct(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

export interface CalibrationMirrorProps {
  readonly entries: ReadonlyArray<EscalationEntry>;
  readonly className?: string | undefined;
}

export function CalibrationMirror({ entries, className }: CalibrationMirrorProps) {
  const summary = useMemo(() => summarizeCalibration(entries), [entries]);

  return (
    <section
      className={`syn-card space-y-2 p-3 ${className ?? ""}`}
      aria-label="Trust calibration mirror (this session)"
    >
      <h3 className="text-2xs uppercase tracking-wide text-ink-muted">
        Your calibration · session
      </h3>
      <dl className="grid grid-cols-2 gap-2 text-2xs">
        <div>
          <dt className="text-ink-subtle">Approved (avg conf.)</dt>
          <dd className="font-mono tabular-nums text-ink">
            {summary.approvedCount} · {pct(summary.avgConfidenceApproved)}
          </dd>
        </div>
        <div>
          <dt className="text-ink-subtle">Overridden (avg conf.)</dt>
          <dd className="font-mono tabular-nums text-ink">
            {summary.overriddenCount} · {pct(summary.avgConfidenceOverridden)}
          </dd>
        </div>
      </dl>
      <p className={`text-2xs ${SIGNAL_TONE[summary.signal]}`}>{SIGNAL_READ[summary.signal]}</p>
    </section>
  );
}
