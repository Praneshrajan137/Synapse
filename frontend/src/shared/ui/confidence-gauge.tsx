/**
 * SYNAPSE Atlas Console — ConfidenceGauge (TS port of legacy JSX).
 *
 * Plan §5.2: gauge thresholds are stable colour signals across the app.
 * Token-driven so dark + light themes inherit, and AAA on the safety
 * surfaces without per-component tweaks.
 */
import { memo } from "react";

import { cn } from "./cn";

export interface ConfidenceGaugeProps {
  /** 0–1; values outside the range are clamped. */
  readonly value: number;
  /** Pixel size; the SVG is square. */
  readonly size?: number;
  readonly className?: string;
  /** Optional label override for screen readers. Defaults to "Confidence: <pct>%". */
  readonly ariaLabel?: string;
}

/** Tri-state colour bin. Property tests in confidence-gauge.test.ts pin the boundaries. */
function bin(value: number): "high" | "mid" | "low" {
  if (value >= 0.8) return "high";
  if (value >= 0.7) return "mid";
  return "low";
}

const STROKE_BY_BIN = {
  high: "stroke-confidence-high",
  mid: "stroke-confidence-mid",
  low: "stroke-confidence-low",
} as const;

const FILL_BY_BIN = {
  high: "fill-confidence-high",
  mid: "fill-confidence-mid",
  low: "fill-confidence-low",
} as const;

export const ConfidenceGauge = memo(function ConfidenceGauge({
  value,
  size = 100,
  className,
  ariaLabel,
}: ConfidenceGaugeProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const pct = Math.round(clamped * 100);
  const tier = bin(clamped);
  const r = size / 2 - 8;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - clamped);

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={cn("overflow-visible", className)}
      role="img"
      aria-label={ariaLabel ?? `Confidence: ${pct}%`}
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        className="fill-none stroke-muted"
        strokeWidth={6}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        className={cn("fill-none transition-[stroke-dashoffset]", STROKE_BY_BIN[tier])}
        strokeWidth={6}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x="50%"
        y="50%"
        dominantBaseline="central"
        textAnchor="middle"
        className={cn("font-bold", FILL_BY_BIN[tier])}
        fontSize={size * 0.22}
      >
        {pct}%
      </text>
    </svg>
  );
});
