import { cn } from "@lib/cn";
import { useMemo } from "react";

/**
 * DivergenceTrace — the digital twin's fidelity over time (SENSORIUM "The
 * Projection"; I-12).
 *
 * A single KL-divergence gauge answers "is the twin faithful right now?" but
 * the operator's real question is "is it drifting?". This renders the KL series
 * as a sparkline with the re-sync threshold (0.1) marked; samples above the
 * line are flagged. Disagreement between model and reality is itself a signal
 * worth attention (the agent-observability "drift" idiom).
 *
 * Colour never sole channel (INV-CLR-011): breaches are larger dots AND the
 * caption + role=img label state the breach count in words.
 */

const MARGIN = { top: 10, right: 8, bottom: 8, left: 8 };
export const DIVERGENCE_RESYNC_THRESHOLD = 0.1;

export interface DivergenceSummary {
  readonly latest: number | null;
  readonly max: number;
  readonly breaches: number;
  readonly trend: "rising" | "falling" | "flat" | "n/a";
}

export function divergenceSummary(
  series: ReadonlyArray<number>,
  threshold = DIVERGENCE_RESYNC_THRESHOLD,
): DivergenceSummary {
  if (series.length === 0) {
    return { latest: null, max: 0, breaches: 0, trend: "n/a" };
  }
  const latest = series[series.length - 1] ?? null;
  const prev = series.length >= 2 ? series[series.length - 2] : undefined;
  const max = series.reduce((m, v) => (v > m ? v : m), 0);
  const breaches = series.filter((v) => v > threshold).length;
  let trend: DivergenceSummary["trend"] = "flat";
  if (latest !== null && prev !== undefined) {
    const delta = latest - prev;
    trend = Math.abs(delta) < 1e-6 ? "flat" : delta > 0 ? "rising" : "falling";
  } else {
    trend = "n/a";
  }
  return { latest, max, breaches, trend };
}

const TREND_GLYPH: Record<DivergenceSummary["trend"], string> = {
  rising: "↑",
  falling: "↓",
  flat: "=",
  "n/a": "",
};

export interface DivergenceTraceProps {
  /** KL-divergence samples, oldest → newest. */
  readonly series: ReadonlyArray<number>;
  readonly threshold?: number | undefined;
  readonly width?: number | undefined;
  readonly height?: number | undefined;
  readonly className?: string | undefined;
}

export function DivergenceTrace({
  series,
  threshold = DIVERGENCE_RESYNC_THRESHOLD,
  width = 480,
  height = 96,
  className,
}: DivergenceTraceProps) {
  const summary = useMemo(() => divergenceSummary(series, threshold), [series, threshold]);

  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerH = Math.max(0, height - MARGIN.top - MARGIN.bottom);
  // Headroom so the threshold line is always visible even on a calm twin.
  const maxY = Math.max(threshold * 2, summary.max, 0.01);

  const pts = useMemo(() => {
    const n = series.length;
    return series.map((kl, i) => ({
      kl,
      x: MARGIN.left + (n <= 1 ? innerW / 2 : (i * innerW) / (n - 1)),
      y: MARGIN.top + innerH * (1 - Math.min(1, Math.max(0, kl / maxY))),
      breach: kl > threshold,
    }));
  }, [series, innerW, innerH, maxY, threshold]);

  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
  const thresholdY = MARGIN.top + innerH * (1 - Math.min(1, threshold / maxY));

  const latestText = summary.latest === null ? "—" : summary.latest.toFixed(3);
  const ariaLabel =
    summary.latest === null
      ? "Twin divergence trace: no samples yet."
      : `Twin divergence trace: latest KL ${latestText}, ${summary.trend}; re-sync threshold ${threshold}; ${summary.breaches} of ${series.length} samples above threshold.`;

  if (series.length === 0) {
    return (
      <figure
        className={cn("syn-card flex items-center justify-center p-4", className)}
        aria-label={ariaLabel}
      >
        <p className="text-xs text-ink-muted">No twin divergence samples yet.</p>
      </figure>
    );
  }

  return (
    <figure className={cn("space-y-1", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-2xs uppercase tracking-wide text-ink-muted">
          Twin divergence (KL)
        </span>
        <span className="font-mono text-xs tabular-nums text-ink">
          {latestText} <span className="text-ink-subtle">{TREND_GLYPH[summary.trend]}</span>
        </span>
      </div>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={ariaLabel}
      >
        {/* Re-sync threshold (I-12: re-sync fires above 0.1). */}
        <line
          x1={MARGIN.left}
          y1={thresholdY}
          x2={width - MARGIN.right}
          y2={thresholdY}
          className="stroke-signal-danger"
          strokeOpacity={0.6}
          strokeDasharray="3 3"
          strokeWidth={1}
        />
        <path
          d={path}
          fill="none"
          className="stroke-accent"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        {pts.map((p) => (
          <circle
            key={`${p.x}-${p.y}`}
            cx={p.x}
            cy={p.y}
            r={p.breach ? 2.6 : 1.4}
            className={p.breach ? "fill-signal-danger" : "fill-accent"}
          />
        ))}
      </svg>
      <figcaption className="flex justify-between text-2xs text-ink-subtle">
        <span>
          re-sync &gt; {threshold} ·{" "}
          {summary.breaches > 0 ? (
            <span className="text-signal-danger">
              {summary.breaches} breach{summary.breaches === 1 ? "" : "es"}
            </span>
          ) : (
            <span className="text-signal-success">no breaches</span>
          )}
        </span>
        <span>{series.length} samples</span>
      </figcaption>
    </figure>
  );
}
