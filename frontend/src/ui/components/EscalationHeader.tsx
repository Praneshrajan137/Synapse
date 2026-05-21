import type { Escalation } from "@/domain/decision";
import { TierBadge } from "@/ui/components/TierBadge";
import { cn } from "@/ui/lib/cn";
import { countdown, shortId } from "@/ui/lib/format";
import { Badge } from "@/ui/primitives";
import { AlertTriangle } from "lucide-react";

/**
 * EscalationHeader — the Council's top strip and 300s clock.
 *
 * The countdown is a breathing ring (tenet T-4) plus a numeric readout;
 * under 60s it turns red and quickens. Violations are named explicitly.
 */

export interface EscalationHeaderProps {
  escalation: Escalation;
  now: number;
}

export function EscalationHeader({ escalation, now }: EscalationHeaderProps) {
  const remaining = escalation.deadlineAt - now;
  const fraction = Math.max(0, Math.min(1, remaining / 300_000));
  const urgent = remaining < 60_000;
  const expired = remaining <= 0;
  const ringColor = expired
    ? "var(--color-ink-disabled)"
    : urgent
      ? "var(--color-sig-stop)"
      : "var(--color-sig-warn)";

  return (
    <header className="flex items-center gap-4 border-b border-line-faint bg-paper px-4 py-3">
      <div className="relative flex size-12 items-center justify-center">
        <svg width={48} height={48} viewBox="0 0 48 48" aria-hidden="true">
          <circle
            cx={24}
            cy={24}
            r={20}
            fill="none"
            stroke="var(--color-line-strong)"
            strokeWidth={3}
          />
          <circle
            cx={24}
            cy={24}
            r={20}
            fill="none"
            stroke={ringColor}
            strokeWidth={3}
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray="1 1"
            strokeDashoffset={1 - fraction}
            transform="rotate(-90 24 24)"
            className={urgent && !expired ? "animate-breathe" : undefined}
          />
        </svg>
        <span
          className="tnum absolute font-mono text-2xs font-semibold"
          style={{ color: ringColor }}
        >
          {countdown(remaining)}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="font-display text-sm font-semibold text-ink-primary">Council</h1>
          <span className="font-mono text-2xs text-ink-hint">
            {shortId(escalation.decision.id)}
          </span>
          <TierBadge tier={escalation.decision.tier} showLatency />
          <Badge tone="warn" dot>
            Escalated
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {escalation.violations.map((violation) => (
            <span
              key={violation.code}
              className="flex items-center gap-1 text-2xs text-sig-stop"
            >
              <AlertTriangle size={11} aria-hidden="true" />
              {violation.detail}
            </span>
          ))}
        </div>
      </div>

      <span
        className={cn(
          "ml-auto font-mono text-2xs",
          expired ? "text-sig-stop" : "text-ink-hint",
        )}
      >
        {expired ? "deadline passed — fallback policy active" : "awaiting operator"}
      </span>
    </header>
  );
}
