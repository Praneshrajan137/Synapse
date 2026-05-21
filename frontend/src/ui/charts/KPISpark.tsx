import { signal } from "@/ui/tokens";
import { useId } from "react";

/**
 * KPISpark — a compact sparkline with an optional conformal band.
 *
 * Tenet T-4 / T-8: KPIs are shown with their uncertainty (the band) and,
 * where relevant, their model's track record. Rendered as raw SVG — a
 * sparkline does not justify a charting-library dependency.
 */

export interface KPISparkProps {
  /** The metric series, oldest first. */
  data: readonly number[];
  /** Optional conformal prediction band, aligned index-for-index with data. */
  band?: { lower: readonly number[]; upper: readonly number[] };
  width?: number;
  height?: number;
  color?: string;
  /** Accessible description, e.g. "Fill rate, last 24 hours". */
  label?: string;
  className?: string;
}

interface Scaled {
  min: number;
  max: number;
}

function extent(values: readonly number[]): Scaled {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const v of values) {
    if (v < min) min = v;
    if (v > max) max = v;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
  if (min === max) return { min: min - 0.5, max: max + 0.5 };
  return { min, max };
}

export function KPISpark({
  data,
  band,
  width = 96,
  height = 28,
  color = signal.live,
  label,
  className,
}: KPISparkProps) {
  const gradientId = useId();
  const pad = 2;

  if (data.length === 0) {
    return (
      <svg width={width} height={height} className={className} aria-hidden="true">
        <line
          x1={pad}
          y1={height / 2}
          x2={width - pad}
          y2={height / 2}
          stroke="var(--color-line-strong)"
          strokeDasharray="2 3"
        />
      </svg>
    );
  }

  const all = band ? [...data, ...band.lower, ...band.upper] : data;
  const { min, max } = extent(all);
  const span = max - min;

  const x = (i: number): number =>
    data.length === 1 ? width / 2 : pad + (i / (data.length - 1)) * (width - pad * 2);
  const y = (v: number): number => height - pad - ((v - min) / span) * (height - pad * 2);

  const line = data.map((v, i) => `${x(i)},${y(v)}`).join(" ");

  let bandPath: string | null = null;
  if (band && band.lower.length === data.length && band.upper.length === data.length) {
    const top = band.upper.map((v, i) => `${x(i)},${y(v)}`);
    const bottom = band.lower.map((v, i) => `${x(i)},${y(v)}`).reverse();
    bandPath = `M${top.join("L")}L${bottom.join("L")}Z`;
  }

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      role="img"
      aria-label={label ?? "Trend sparkline"}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.28} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      {bandPath && <path d={bandPath} fill={color} fillOpacity={0.12} stroke="none" />}
      <polyline
        points={`${pad},${height} ${line} ${width - pad},${height}`}
        fill={`url(#${gradientId})`}
        stroke="none"
      />
      <polyline
        points={line}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
