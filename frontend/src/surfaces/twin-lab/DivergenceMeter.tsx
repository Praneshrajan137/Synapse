import { cn } from "@lib/cn";

interface DivergenceMeterProps {
  readonly value: number;
  readonly className?: string;
}

/**
 * KL divergence indicator (I-12). 0.05 OK · 0.05–0.1 WARN · >0.1 RISK.
 */
export function DivergenceMeter({ value, className }: DivergenceMeterProps) {
  const clamped = Math.max(0, Math.min(0.2, value));
  const pct = (clamped / 0.2) * 100;
  const tone = clamped <= 0.05 ? "ok" : clamped <= 0.1 ? "warn" : "risk";
  const toneClass = {
    ok: "bg-confidence-ok",
    warn: "bg-confidence-warn",
    risk: "bg-confidence-risk",
  }[tone];
  return (
    <div className={cn("space-y-1", className)} aria-label={`KL divergence ${value.toFixed(3)}`}>
      <div className="flex items-center justify-between text-2xs text-ink-muted">
        <span>KL divergence</span>
        <span className="font-mono text-ink">{value.toFixed(3)}</span>
      </div>
      <div className="relative h-2 w-full overflow-hidden rounded bg-surface-raised">
        <div
          className={cn("h-full rounded transition-all duration-medium ease-standard", toneClass)}
          style={{ width: `${pct}%` }}
        />
        <span className="absolute left-[25%] top-0 h-full w-px bg-confidence-warn/60" aria-hidden />
        <span className="absolute left-[50%] top-0 h-full w-px bg-confidence-risk/60" aria-hidden />
      </div>
      <div className="flex justify-between text-2xs text-ink-subtle">
        <span>0.00</span>
        <span>0.05</span>
        <span>0.10</span>
        <span>0.20</span>
      </div>
    </div>
  );
}
