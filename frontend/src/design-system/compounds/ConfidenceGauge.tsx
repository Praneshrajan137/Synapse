import { confidenceBand } from "@lib/confidence";

interface ConfidenceGaugeProps {
  readonly value: number;
  readonly size?: number;
  readonly thickness?: number;
  readonly label?: string;
}

// Chromatic-token migration (ADR-044 Phase 4): SVG presentation attributes
// accept CSS colour functions — rgb(var(--…)) reaches the channel tokens
// with no raw literal (INV-CLR-009) and flips with [data-theme].
const BAND_COLOR: Record<ReturnType<typeof confidenceBand>, string> = {
  ok: "rgb(var(--syn-confidence-ok))",
  warn: "rgb(var(--syn-confidence-warn))",
  risk: "rgb(var(--syn-confidence-risk))",
};

/**
 * Circular confidence gauge — TypeScript port of ConfidenceGauge.jsx with
 * a11y baked in. Falls back gracefully under prefers-reduced-motion (no
 * animated stroke).
 */
export function ConfidenceGauge({ value, size = 100, thickness = 6, label }: ConfidenceGaugeProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const pct = Math.round(clamped * 100);
  const ramp = confidenceBand(clamped);
  const color = BAND_COLOR[ramp];
  const r = size / 2 - thickness;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - clamped);
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`${label ?? "Confidence"} ${pct}%`}
    >
      <title>{`${label ?? "Confidence"} ${pct}%`}</title>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="rgb(var(--syn-border))"
        strokeWidth={thickness}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={thickness}
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
        fill={color}
        fontSize={size * 0.22}
        fontWeight={700}
        fontFamily="JetBrainsMono, ui-monospace, monospace"
      >
        {pct}%
      </text>
    </svg>
  );
}
