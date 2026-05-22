import { cn } from "@lib/cn";
import { confidenceBand } from "@lib/confidence";

interface ConfidenceChipProps {
  readonly value: number;
  readonly threshold?: number;
  readonly band?: { readonly lower: number; readonly upper: number };
  readonly className?: string;
  readonly ariaLabel?: string;
}

const BAND_CLASS = {
  ok: "bg-confidence-ok/15 text-confidence-ok",
  warn: "bg-confidence-warn/15 text-confidence-warn",
  risk: "bg-confidence-risk/15 text-confidence-risk",
} as const;

/**
 * Numeric confidence chip with a ramped color and an optional MAPIE band.
 * Generalization of ConfidenceGauge.jsx — used inline in decision rows,
 * agent cards, and the escalation header.
 */
export function ConfidenceChip({
  value,
  threshold = 0.7,
  band,
  className,
  ariaLabel,
}: ConfidenceChipProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const ramp = confidenceBand(clamped);
  const below = clamped < threshold;
  const pct = Math.round(clamped * 100);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-2xs font-semibold tabular-nums",
        BAND_CLASS[ramp],
        below && "ring-1 ring-confidence-risk/40",
        className,
      )}
      role="img"
      aria-label={ariaLabel ?? `Confidence ${pct} percent${below ? ", below threshold" : ""}`}
      title={
        band
          ? `Confidence ${pct}% (90% interval ${Math.round(band.lower * 100)}–${Math.round(band.upper * 100)}%)`
          : `Confidence ${pct}% (threshold ${Math.round(threshold * 100)}%)`
      }
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: "currentColor" }}
        aria-hidden
      />
      {pct}%
    </span>
  );
}
