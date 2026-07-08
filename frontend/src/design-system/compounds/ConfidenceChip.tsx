import { confidenceColor, confidenceZone } from "@lib/chromatics";
import { cn } from "@lib/cn";
import { formatConfidence } from "@lib/confidence";
import { useThemeStore } from "@state/theme.store";

interface ConfidenceChipProps {
  readonly value: number;
  readonly threshold?: number;
  readonly band?: { readonly lower: number; readonly upper: number };
  readonly className?: string;
  readonly ariaLabel?: string;
}

/**
 * Numeric confidence chip on the CONTINUOUS gate-anchored scale (ADR-045):
 * the colour is `confidenceColor(value, {vsup: true})` — hue sweeps
 * red→amber→green→teal across the exact I-5 gates (0.70/0.80, INV-CLR-007)
 * and chroma drains as confidence falls (VSUP), so a shaky number LOOKS
 * shaky. The legacy 3-stop band classes were quantised at 0.9/0.7 — wrong
 * gates, wrong philosophy.
 *
 * The `confidence-{ok|warn|risk}` literal class is a stable test/automation
 * hook (zone-mapped: autonomous→ok, escalation→warn, low→risk); colour is
 * never the sole channel — the two-decimal numeric value (`formatConfidence`,
 * `^[01]\.\d{2}$`) is the signal (Req 4.1/4.2, INV-CLR-011).
 */
export function ConfidenceChip({
  value,
  threshold = 0.7,
  band,
  className,
  ariaLabel,
}: ConfidenceChipProps) {
  const theme = useThemeStore((s) => s.theme);
  const clamped = Math.max(0, Math.min(1, value));
  const zone = confidenceZone(clamped);
  const bandToken = zone === "autonomous" ? "ok" : zone === "escalation" ? "warn" : "risk";
  const below = clamped < threshold;
  const pct = Math.round(clamped * 100);
  // Two-decimal numeric-text channel (Req 4.1/4.2, INV-CLR-011): the value
  // ALWAYS renders as text matching `^[01]\.\d{2}$` so confidence is never
  // colour-only. Single source of truth: `formatConfidence` in @lib/confidence.
  const numeric = formatConfidence(clamped);
  const color = confidenceColor(clamped, { theme, vsup: true });

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-2xs font-semibold tabular-nums",
        `confidence-${bandToken}`,
        below && "ring-1 ring-confidence-risk/40",
        className,
      )}
      style={{ color, background: `color-mix(in oklab, ${color} 15%, transparent)` }}
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
      {numeric}
    </span>
  );
}
