import { cn } from "@lib/cn";
import { useMemo } from "react";

/**
 * OutcomeBand — a quantile dotplot for a distribution of outcomes (SENSORIUM
 * P5; the Projection's Monte-Carlo / forecast uncertainty).
 *
 * Point estimates lie about uncertainty. A quantile dotplot quantises the
 * predictive distribution into N equal-probability dots (Kay et al. — proven to
 * improve real decisions over density/interval encodings, because "14 of 20
 * scenarios land beyond the SLA" is something a non-statistician can act on).
 * Use it for conformal demand intervals and Tier-4 Monte-Carlo draws.
 *
 * Honest about sample size (P7): with too few samples it says so rather than
 * implying false precision. Colour never sole channel (INV-CLR-011): the
 * median + tail quantiles are labelled in text and the role=img summary.
 */

const MARGIN = { top: 8, right: 12, bottom: 22, left: 12 };

export interface OutcomeQuantiles {
  readonly p10: number;
  readonly p50: number;
  readonly p90: number;
}

/** The value at quantile q in [0,1] of a sample (linear interpolation). */
export function quantile(sorted: ReadonlyArray<number>, q: number): number {
  if (sorted.length === 0) return Number.NaN;
  if (sorted.length === 1) return sorted[0] as number;
  const pos = (sorted.length - 1) * Math.min(1, Math.max(0, q));
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  const a = sorted[lo] as number;
  const b = sorted[hi] as number;
  return a + (b - a) * (pos - lo);
}

/** N equal-probability dot values from a sample (the quantile dotplot). */
export function quantileDots(samples: ReadonlyArray<number>, dots: number): number[] {
  if (samples.length === 0 || dots <= 0) return [];
  const sorted = [...samples].sort((a, b) => a - b);
  const out: number[] = [];
  for (let i = 0; i < dots; i++) {
    out.push(quantile(sorted, (i + 0.5) / dots));
  }
  return out;
}

export interface OutcomeBandProps {
  readonly samples: ReadonlyArray<number>;
  /** Number of equal-probability dots (default 20 → each = 5%). */
  readonly dots?: number | undefined;
  /** Optional target/SLA line; dots beyond it are flagged in the summary. */
  readonly threshold?: number | undefined;
  /** True if exceeding the threshold is bad (default true). */
  readonly thresholdIsCeiling?: boolean | undefined;
  readonly unit?: string | undefined;
  readonly label?: string | undefined;
  readonly width?: number | undefined;
  readonly height?: number | undefined;
  readonly className?: string | undefined;
}

const MIN_SAMPLE = 5;

export function OutcomeBand({
  samples,
  dots = 20,
  threshold,
  thresholdIsCeiling = true,
  unit = "",
  label = "Outcome distribution",
  width = 360,
  height = 120,
  className,
}: OutcomeBandProps) {
  const model = useMemo(() => {
    const sorted = [...samples].sort((a, b) => a - b);
    const dotValues = quantileDots(sorted, dots);
    const q: OutcomeQuantiles = {
      p10: quantile(sorted, 0.1),
      p50: quantile(sorted, 0.5),
      p90: quantile(sorted, 0.9),
    };
    const min = sorted[0] ?? 0;
    const max = sorted[sorted.length - 1] ?? 1;
    const beyond =
      threshold === undefined
        ? 0
        : dotValues.filter((v) => (thresholdIsCeiling ? v > threshold : v < threshold)).length;
    return { dotValues, q, min, max, beyond };
  }, [samples, dots, threshold, thresholdIsCeiling]);

  if (samples.length < MIN_SAMPLE) {
    return (
      <figure
        className={cn("syn-card flex items-center justify-center p-4", className)}
        aria-label={`${label}: too few samples (${samples.length}) to show a distribution`}
      >
        <p className="text-xs text-ink-muted">
          Too few samples ({samples.length}) for an honest distribution.
        </p>
      </figure>
    );
  }

  const innerW = Math.max(1, width - MARGIN.left - MARGIN.right);
  const innerH = Math.max(1, height - MARGIN.top - MARGIN.bottom);
  const span = model.max - model.min || 1;
  const xFor = (v: number): number => MARGIN.left + ((v - model.min) / span) * innerW;

  // Stack dots into bins so equal/near-equal values pile vertically.
  const bins = 40;
  const binCount = new Array<number>(bins).fill(0);
  const dotR = 3;
  const baseY = MARGIN.top + innerH;

  const summary =
    threshold === undefined
      ? `${label}: median ${model.q.p50.toFixed(1)}${unit}, 10th–90th percentile ${model.q.p10.toFixed(1)}–${model.q.p90.toFixed(1)}${unit}, from ${samples.length} samples.`
      : `${label}: median ${model.q.p50.toFixed(1)}${unit}; ${model.beyond} of ${dots} scenarios ${thresholdIsCeiling ? "exceed" : "fall short of"} ${threshold}${unit}.`;

  return (
    <figure className={cn("space-y-1", className)}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={summary}
      >
        {threshold !== undefined && threshold >= model.min && threshold <= model.max && (
          <line
            x1={xFor(threshold)}
            y1={MARGIN.top}
            x2={xFor(threshold)}
            y2={baseY}
            className="stroke-signal-danger"
            strokeOpacity={0.6}
            strokeDasharray="3 3"
            strokeWidth={1}
          />
        )}
        {model.dotValues.map((v, i) => {
          const x = xFor(v);
          const bin = Math.min(bins - 1, Math.max(0, Math.floor(((v - model.min) / span) * bins)));
          const stack = binCount[bin] ?? 0;
          binCount[bin] = stack + 1;
          const cy = baseY - dotR - stack * (dotR * 2 + 0.5);
          const beyond =
            threshold !== undefined && (thresholdIsCeiling ? v > threshold : v < threshold);
          return (
            <circle
              key={`${i}-${x}`}
              cx={x}
              cy={cy}
              r={dotR}
              className={beyond ? "fill-signal-danger" : "fill-accent"}
              fillOpacity={0.85}
            />
          );
        })}
        {/* Median tick. */}
        <line
          x1={xFor(model.q.p50)}
          y1={MARGIN.top}
          x2={xFor(model.q.p50)}
          y2={baseY}
          className="stroke-ink"
          strokeOpacity={0.5}
          strokeWidth={1}
        />
        <text x={MARGIN.left} y={height - 6} className="fill-ink-subtle text-[8px] tabular-nums">
          {model.min.toFixed(1)}
          {unit}
        </text>
        <text
          x={width - MARGIN.right}
          y={height - 6}
          textAnchor="end"
          className="fill-ink-subtle text-[8px] tabular-nums"
        >
          {model.max.toFixed(1)}
          {unit}
        </text>
      </svg>
      <figcaption className="flex flex-wrap justify-between gap-2 text-2xs text-ink-muted">
        <span>
          median{" "}
          <span className="font-mono tabular-nums text-ink">
            {model.q.p50.toFixed(1)}
            {unit}
          </span>{" "}
          · P10–P90 {model.q.p10.toFixed(1)}–{model.q.p90.toFixed(1)}
          {unit}
        </span>
        {threshold !== undefined && (
          <span className={model.beyond > 0 ? "text-signal-warning" : "text-signal-success"}>
            {model.beyond}/{dots} {thresholdIsCeiling ? "over" : "under"} {threshold}
            {unit}
          </span>
        )}
      </figcaption>
    </figure>
  );
}
