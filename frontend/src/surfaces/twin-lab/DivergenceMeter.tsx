import { cn } from "@lib/cn";
import { NO_VALUE_MARKER } from "@surfaces/operations/logic";

interface DivergenceMeterProps {
  /**
   * KL divergence against the live distribution, or `null` when it has not been
   * measured. `null` is NOT zero: on this meter zero is the strongest possible
   * fidelity claim, so substituting it for an absent measurement inverts the
   * reading (I-7, R3.5). The twin's own uplift artifact records
   * `kl_divergence: null` for exactly this reason - the measurement has not been
   * taken - and the console must say the same thing.
   */
  readonly value: number | null;
  readonly className?: string;
}

/**
 * KL divergence indicator (I-12). 0.05 OK · 0.05–0.1 WARN · >0.1 RISK, and an
 * unmeasured divergence renders a drained track with the explicit no-value
 * marker rather than a full-width green bar at 0.000.
 */
export function DivergenceMeter({ value, className }: DivergenceMeterProps) {
  const measured = value !== null && Number.isFinite(value);
  const clamped = measured ? Math.max(0, Math.min(0.2, value)) : 0;
  const pct = measured ? (clamped / 0.2) * 100 : 0;
  const tone = !measured ? "unknown" : clamped <= 0.05 ? "ok" : clamped <= 0.1 ? "warn" : "risk";
  const toneClass = {
    ok: "bg-confidence-ok",
    warn: "bg-confidence-warn",
    risk: "bg-confidence-risk",
    // A drained track: nothing is painted, because nothing was measured.
    unknown: "bg-border",
  }[tone];
  const reading = measured ? value.toFixed(3) : NO_VALUE_MARKER;
  return (
    <div
      className={cn("space-y-1", className)}
      data-kl-measured={measured ? "true" : "false"}
      aria-label={
        measured ? `KL divergence ${reading}` : "KL divergence not measured — no scenario has run"
      }
    >
      <div className="flex items-center justify-between text-2xs text-ink-muted">
        <span>KL divergence</span>
        <span className={cn("font-mono", measured ? "text-ink" : "text-state-degraded")}>
          {reading}
        </span>
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
      {!measured && (
        <p className="text-2xs text-state-degraded">
          <span aria-hidden>▲ </span>
          Not measured — run a scenario. This is not a fidelity reading of zero.
        </p>
      )}
    </div>
  );
}
