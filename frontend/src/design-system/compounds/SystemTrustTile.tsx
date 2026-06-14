import { usePosture } from "@hooks/use-posture";
import { cn } from "@lib/cn";
import { useEscalationStore } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import { useMemo } from "react";

// The missing system-level trust signal (Sprint 18). Per-decision confidence and
// per-agent calibration already existed, but nothing answered the operator's
// first question — "can I trust the system to run itself right now?" This tile
// aggregates the live autonomy record into ONE honest verdict + its evidence:
// autonomy rate (auto-resolved vs escalated), avg confidence vs the I-5 gate,
// and degradation posture. It is the "Reassure" job made glanceable.

const I5_HIGH_GATE = 0.8; // autonomous-action gate

type TrustTone = "ok" | "warn" | "risk" | "neutral";
const TONE: Record<TrustTone, { rail: string; text: string; dot: string }> = {
  ok: { rail: "border-confidence-ok/70", text: "text-confidence-ok", dot: "bg-confidence-ok" },
  warn: {
    rail: "border-confidence-warn/70",
    text: "text-confidence-warn",
    dot: "bg-confidence-warn",
  },
  risk: {
    rail: "border-confidence-risk/80",
    text: "text-confidence-risk",
    dot: "bg-confidence-risk",
  },
  neutral: { rail: "border-border", text: "text-ink-muted", dot: "bg-ink-subtle" },
};

export function SystemTrustTile() {
  const decisions = useFirehoseStore((s) => s.decisions.items);
  const pending = useEscalationStore((s) => s.entries.filter((e) => e.status === "pending").length);
  const posture = usePosture();

  const verdict = useMemo(() => {
    const recent = decisions.slice(-60);
    const total = recent.length;
    const escalated = recent.filter((d) => d.escalated).length;
    const degradedCount = recent.filter((d) => d.degraded).length;
    const autonomyRate = total > 0 ? (total - escalated) / total : null;
    const avgConfidence =
      total > 0 ? recent.reduce((acc, d) => acc + d.confidence, 0) / total : null;
    const degradedRate = total > 0 ? degradedCount / total : 0;

    const breakersOpen = posture.data
      ? Object.values(posture.data.breakers).filter((s) => String(s).toLowerCase() === "open")
          .length
      : 0;
    const postureBad = posture.isError || Boolean(posture.data?.degraded) || breakersOpen > 0;

    let word = "Autonomous";
    let tone: TrustTone = "ok";
    let detail = "Operating within the confidence gate — no action needed.";

    if (postureBad) {
      word = "Degraded";
      tone = "risk";
      detail = posture.isError
        ? "System posture is unknown — treat as degraded."
        : breakersOpen > 0
          ? `${breakersOpen} circuit breaker${breakersOpen === 1 ? "" : "s"} open — agents running on fallbacks.`
          : "Running degraded — some outputs are on fallback paths.";
    } else if (degradedRate > 0.2) {
      word = "Degraded";
      tone = "risk";
      detail = "A large share of recent decisions ran on fallback data.";
    } else if (pending > 0) {
      word = "Supervised";
      tone = "warn";
      detail = `${pending} decision${pending === 1 ? "" : "s"} awaiting your call.`;
    } else if (avgConfidence !== null && avgConfidence < I5_HIGH_GATE) {
      word = "Supervised";
      tone = "warn";
      detail = "Recent confidence sits below the autonomy gate — watch closely.";
    } else if (autonomyRate !== null && autonomyRate < 0.9) {
      word = "Supervised";
      tone = "warn";
      detail = "Escalation rate is elevated.";
    } else if (total === 0) {
      word = "Standby";
      tone = "neutral";
      detail = "No live decisions yet in this window.";
    }

    return { word, tone, detail, autonomyRate, avgConfidence, breakersOpen, total };
  }, [decisions, pending, posture.data, posture.isError]);

  const tone = TONE[verdict.tone];
  const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

  return (
    <section aria-label="System trust" className={cn("syn-card border-l-2 px-4 py-3", tone.rail)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className={cn(
              "h-2 w-2 rounded-full",
              tone.dot,
              verdict.tone === "risk" && "animate-pulse-confidence",
            )}
          />
          <span className="text-2xs uppercase tracking-[0.14em] text-ink-subtle">System trust</span>
          <span className={cn("font-display text-lg font-semibold", tone.text)}>
            {verdict.word}
          </span>
        </div>
        <dl className="flex items-baseline gap-4 font-mono text-2xs tabular-nums text-ink-muted">
          <div className="flex items-baseline gap-1">
            <dt className="text-ink-subtle">Autonomy</dt>
            <dd className="text-ink">{pct(verdict.autonomyRate)}</dd>
          </div>
          <div className="flex items-baseline gap-1">
            <dt className="text-ink-subtle">Avg conf</dt>
            <dd className="text-ink">
              {pct(verdict.avgConfidence)}
              <span className="text-ink-subtle"> / {I5_HIGH_GATE * 100}</span>
            </dd>
          </div>
          <div className="flex items-baseline gap-1">
            <dt className="text-ink-subtle">Breakers</dt>
            <dd className="text-ink">{verdict.breakersOpen}</dd>
          </div>
        </dl>
      </div>
      <p className="mt-1 text-xs text-ink-muted">{verdict.detail}</p>
    </section>
  );
}
