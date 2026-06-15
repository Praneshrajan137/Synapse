import type { CalibrationBin } from "@domain/operations";
import { cn } from "@lib/cn";
import { useMemo } from "react";

const M = { top: 12, right: 14, bottom: 26, left: 32 };

interface ReliabilityCurveProps {
  readonly bins: ReadonlyArray<CalibrationBin>;
  readonly width?: number;
  readonly height?: number;
  readonly className?: string;
}

/**
 * Reliability diagram (pure SVG — no viz lib, stays out of the entry bundle).
 * Plots observed-correct fraction (y) against predicted confidence (x) for each
 * bin that has scored decisions; the diagonal is perfect calibration. Points
 * above the line = under-confident, below = over-confident.
 *
 * Honest about evidence (FE-INV-043): bins with n=0 are not plotted, dot area
 * scales with n, and an all-empty curve says so rather than drawing a flat
 * confident-looking line. The I-5 gate (0.70) is marked.
 */
export function ReliabilityCurve({
  bins,
  width = 320,
  height = 220,
  className,
}: ReliabilityCurveProps) {
  const points = useMemo(
    () =>
      bins
        .filter((b) => b.n > 0 && b.mean_confidence !== null && b.observed_rate !== null)
        .map((b) => ({
          x: b.mean_confidence as number,
          y: b.observed_rate as number,
          n: b.n,
        }))
        .sort((a, b) => a.x - b.x),
    [bins],
  );

  const innerW = Math.max(1, width - M.left - M.right);
  const innerH = Math.max(1, height - M.top - M.bottom);
  const px = (v: number) => M.left + Math.min(1, Math.max(0, v)) * innerW;
  const py = (v: number) => M.top + (1 - Math.min(1, Math.max(0, v))) * innerH;
  const maxN = points.reduce((m, p) => Math.max(m, p.n), 1);
  const rFor = (n: number) => 2.5 + 4 * Math.sqrt(n / maxN);

  if (points.length === 0) {
    return (
      <figure
        className={cn("syn-card flex items-center justify-center p-6", className)}
        aria-label="Reliability diagram: no scored outcomes yet"
      >
        <p className="text-xs text-ink-muted">
          Awaiting scored outcomes — the curve appears once decisions settle.
        </p>
      </figure>
    );
  }

  const totalN = points.reduce((s, p) => s + p.n, 0);
  const summary = `Reliability diagram from ${totalN} scored decisions across ${points.length} confidence bins; the diagonal is perfect calibration.`;
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${px(p.x)},${py(p.y)}`).join(" ");

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
        {/* frame */}
        <line x1={M.left} y1={M.top} x2={M.left} y2={M.top + innerH} className="stroke-border" />
        <line
          x1={M.left}
          y1={M.top + innerH}
          x2={M.left + innerW}
          y2={M.top + innerH}
          className="stroke-border"
        />
        {/* perfect-calibration diagonal */}
        <line
          x1={px(0)}
          y1={py(0)}
          x2={px(1)}
          y2={py(1)}
          className="stroke-ink-subtle"
          strokeDasharray="4 4"
          strokeOpacity={0.7}
        />
        {/* I-5 gate */}
        <line
          x1={px(0.7)}
          y1={M.top}
          x2={px(0.7)}
          y2={M.top + innerH}
          className="stroke-signal-warning"
          strokeOpacity={0.4}
          strokeDasharray="2 3"
        />
        {/* observed curve */}
        <path d={linePath} fill="none" className="stroke-accent" strokeWidth={1.5} />
        {points.map((p) => (
          <circle
            key={`${p.x}-${p.y}`}
            cx={px(p.x)}
            cy={py(p.y)}
            r={rFor(p.n)}
            className="fill-accent"
            fillOpacity={0.85}
          >
            <title>{`conf ${p.x.toFixed(2)} → observed ${(p.y * 100).toFixed(0)}% (n=${p.n})`}</title>
          </circle>
        ))}
        {/* axis labels */}
        {[0, 0.5, 1].map((t) => (
          <text
            key={`x${t}`}
            x={px(t)}
            y={height - 8}
            textAnchor="middle"
            className="fill-ink-subtle text-[8px] tabular-nums"
          >
            {t}
          </text>
        ))}
        {[0, 0.5, 1].map((t) => (
          <text
            key={`y${t}`}
            x={M.left - 6}
            y={py(t) + 3}
            textAnchor="end"
            className="fill-ink-subtle text-[8px] tabular-nums"
          >
            {t}
          </text>
        ))}
      </svg>
      <figcaption className="flex justify-between text-2xs text-ink-muted">
        <span>predicted confidence →</span>
        <span>↑ observed correct</span>
      </figcaption>
    </figure>
  );
}
