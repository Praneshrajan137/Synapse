import { useEscalations } from "@/application/decisions";
import type { Escalation } from "@/domain/decision";
import { TierBadge } from "@/ui/components/TierBadge";
import { useNow } from "@/ui/hooks/useNow";
import { AgentSigil } from "@/ui/icons";
import { cn } from "@/ui/lib/cn";
import { countdown, shortId } from "@/ui/lib/format";
import { ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

/**
 * EscalationQueue — pending HITL escalations. Calm by default (tenet
 * T-7): when nothing is escalated this collapses to a single "all
 * clear" line. Each item carries a live countdown to its 300s deadline.
 */

function CountdownRing({ remainingMs }: { remainingMs: number }) {
  const total = 300_000;
  const fraction = Math.max(0, Math.min(1, remainingMs / total));
  const urgent = remainingMs < 60_000;
  const color = urgent ? "var(--color-sig-stop)" : "var(--color-sig-warn)";
  return (
    <svg width={34} height={34} viewBox="0 0 34 34" aria-hidden="true">
      <circle
        cx={17}
        cy={17}
        r={14}
        fill="none"
        stroke="var(--color-line-strong)"
        strokeWidth={3}
      />
      <circle
        cx={17}
        cy={17}
        r={14}
        fill="none"
        stroke={color}
        strokeWidth={3}
        strokeLinecap="round"
        pathLength={1}
        strokeDasharray="1 1"
        strokeDashoffset={1 - fraction}
        transform="rotate(-90 17 17)"
        className={urgent ? "animate-breathe" : undefined}
      />
    </svg>
  );
}

function EscalationItem({ escalation, now }: { escalation: Escalation; now: number }) {
  const navigate = useNavigate();
  const remaining = escalation.deadlineAt - now;
  return (
    <button
      type="button"
      onClick={() => navigate("/council")}
      className={cn(
        "flex w-full items-center gap-3 border-b border-line-faint/60 px-3 py-2.5 text-left",
        "transition-colors hover:bg-elevated/60",
        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sig-live",
      )}
    >
      <CountdownRing remainingMs={remaining} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-xs text-ink-primary">
          {escalation.decision.summary}
        </span>
        <span className="flex items-center gap-2 text-2xs text-ink-hint">
          <AgentSigil agent={escalation.recommendedAgent} size={13} />
          <span className="font-mono">{shortId(escalation.decision.id)}</span>
          <span className="tnum text-sig-warn">{countdown(remaining)}</span>
        </span>
      </div>
      <TierBadge tier={escalation.decision.tier} />
    </button>
  );
}

export function EscalationQueue({ className }: { className?: string }) {
  const { data } = useEscalations();
  const now = useNow(1000);
  const escalations = data ?? [];

  return (
    <section aria-label="Escalation queue" className={cn("bg-paper", className)}>
      <header className="flex h-9 items-center justify-between border-y border-line-faint px-3">
        <h2 className="font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
          Escalation Queue
        </h2>
        {escalations.length > 0 && (
          <span className="rounded-sm bg-sig-warn/15 px-1.5 text-2xs font-semibold text-sig-warn">
            {escalations.length}
          </span>
        )}
      </header>
      {escalations.length === 0 ? (
        <p className="flex items-center gap-2 px-3 py-2.5 text-2xs text-ink-hint">
          <ShieldCheck size={13} className="text-sig-ok" aria-hidden="true" />
          All clear — no decisions awaiting human action.
        </p>
      ) : (
        <ul>
          {escalations.map((escalation) => (
            <li key={escalation.decision.id}>
              <EscalationItem escalation={escalation} now={now} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
