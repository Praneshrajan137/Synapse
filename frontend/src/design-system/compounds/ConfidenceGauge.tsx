import { confidenceBand } from "@lib/confidence";

interface ConfidenceGaugeProps {
  readonly value: number;
  readonly size?: number;
  readonly thickness?: number;
  readonly label?: string;
}

const BAND_HEX: Record<ReturnType<typeof confidenceBand>, string> = {
  ok: "rgb(34 197 94)",
  warn: "rgb(234 179 8)",
  risk: "rgb(239 68 68)",
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
  const color = BAND_HEX[ramp];
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
        stroke="rgb(51 65 85)"
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
