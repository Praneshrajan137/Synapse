import { AGENT_COLOR_VAR } from "@lib/agent-identity";
import { cn } from "@lib/cn";
import {
  OBJECTIVE_AGENT,
  OBJECTIVE_LABEL,
  PARETO_OBJECTIVES,
  type ParetoFront,
  type ParetoObjective,
  axisExtents,
  kneePointIndex,
} from "@lib/pareto";
import { useMemo } from "react";

/**
 * ParetoParallel — the orchestrator's multi-objective consensus front as
 * parallel coordinates (SENSORIUM "The Tribunal"; the comprehension crown
 * jewel, SA-L2).
 *
 * The arbitration front is genuinely 8-dimensional (one objective per agent);
 * a 2-D scatter cannot show it. Each vertical axis is one objective, tinted
 * with its owning agent's FROZEN identity hue (INV-CLR-012), so the operator
 * reads "whose interest is this" pre-attentively. Every non-dominated
 * candidate is a faint polyline; the chosen **knee point** is bold. The
 * meta-RL objective weights ride atop each axis as bars — the exact lever the
 * Steering surface tunes ("The Will"), so the *cause* of the choice is visible.
 *
 * Honest: the knee is recomputed client-side from the front + weights
 * (lib/pareto.ts, faithful to pareto.py) rather than trusted from a field the
 * audit row may not carry. Colour never sole channel (INV-CLR-011): the knee
 * is also called out in the caption + the screen-reader table.
 */

const MARGIN = { top: 46, right: 28, bottom: 26, left: 28 };
const WEIGHT_BAR_MAX = 22;

export interface ParetoParallelProps {
  readonly front: ParetoFront;
  readonly weights?: Readonly<Record<string, number>> | undefined;
  readonly objectives?: readonly ParetoObjective[] | undefined;
  /** Override the computed knee (e.g. a persisted index). */
  readonly kneeIndex?: number | null | undefined;
  readonly width?: number | undefined;
  readonly height?: number | undefined;
  readonly className?: string | undefined;
}

interface AxisLayout {
  readonly obj: ParetoObjective;
  readonly label: string;
  readonly colorVar: string;
  readonly x: number;
  readonly min: number;
  readonly max: number;
  readonly weight: number;
}

export function ParetoParallel({
  front,
  weights = {},
  objectives = PARETO_OBJECTIVES,
  kneeIndex,
  width = 640,
  height = 300,
  className,
}: ParetoParallelProps) {
  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerH = Math.max(0, height - MARGIN.top - MARGIN.bottom);

  const knee = useMemo(() => {
    if (kneeIndex !== null && kneeIndex !== undefined) return kneeIndex;
    return kneePointIndex(front, weights, objectives);
  }, [front, weights, objectives, kneeIndex]);

  const axes = useMemo<AxisLayout[]>(() => {
    const ext = axisExtents(front, objectives);
    const n = objectives.length;
    const maxWeight = Math.max(1, ...objectives.map((o) => weights[o] ?? 0));
    return objectives.map((obj, j) => {
      const e = ext[obj] ?? { min: 0, max: 1 };
      return {
        obj,
        label: OBJECTIVE_LABEL[obj],
        colorVar: AGENT_COLOR_VAR[OBJECTIVE_AGENT[obj]],
        x: MARGIN.left + (n <= 1 ? innerW / 2 : (j * innerW) / (n - 1)),
        min: e.min,
        max: e.max,
        weight: (weights[obj] ?? 0) / maxWeight,
      };
    });
  }, [front, objectives, weights, innerW]);

  const yFor = (axis: AxisLayout, value: number): number => {
    const span = axis.max - axis.min;
    const norm = span <= 0 ? 0.5 : (value - axis.min) / span;
    return MARGIN.top + innerH * (1 - norm);
  };

  const valueAt = (row: Readonly<Record<string, number>>, axis: AxisLayout): number => {
    const v = row[axis.obj];
    return typeof v === "number" && Number.isFinite(v) ? v : axis.min;
  };

  const polyline = (row: Readonly<Record<string, number>>): string =>
    axes.map((a) => `${a.x},${yFor(a, valueAt(row, a))}`).join(" ");

  const kneeRow = knee !== null && knee >= 0 && knee < front.length ? front[knee] : undefined;

  if (front.length === 0) {
    return (
      <figure
        className={cn("syn-card flex items-center justify-center p-6", className)}
        aria-label="Pareto front not recorded for this decision"
      >
        <p className="text-xs text-ink-muted">
          No Pareto front recorded — this was a fast-path decision (Tier 1–2) or the front was not
          persisted.
        </p>
      </figure>
    );
  }

  return (
    <figure className={cn("space-y-2", className)}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={`Pareto front: ${front.length} candidate decisions across ${axes.length} objectives; the chosen knee-point solution is highlighted.`}
      >
        {/* Axes — one per objective, tinted by the owning agent's hue. */}
        {axes.map((a) => (
          <g key={a.obj}>
            <line
              x1={a.x}
              y1={MARGIN.top}
              x2={a.x}
              y2={MARGIN.top + innerH}
              stroke={a.colorVar}
              strokeOpacity={0.45}
              strokeWidth={1}
            />
            {/* Objective weight bar (the Steering lever, made visible). */}
            <rect
              x={a.x - 3}
              y={18}
              width={6}
              height={Math.max(0.5, a.weight * WEIGHT_BAR_MAX)}
              fill={a.colorVar}
              fillOpacity={0.6}
              rx={1}
            >
              <title>{`${a.label} objective weight`}</title>
            </rect>
            <text
              x={a.x}
              y={12}
              textAnchor="middle"
              className="fill-ink-muted text-[8px] uppercase tracking-wide"
            >
              {a.label}
            </text>
          </g>
        ))}

        {/* Non-knee candidates — faint background. */}
        {front.map((row, i) =>
          i === knee ? null : (
            <polyline
              key={`sol-${i}-${polyline(row)}`}
              points={polyline(row)}
              fill="none"
              className="stroke-ink-subtle"
              strokeOpacity={0.28}
              strokeWidth={1}
            />
          ),
        )}

        {/* The knee point — the chosen solution. Bold accent + value dots. */}
        {kneeRow && (
          <>
            <polyline
              points={polyline(kneeRow)}
              fill="none"
              className="stroke-accent"
              strokeWidth={2.5}
              strokeLinejoin="round"
            />
            {axes.map((a) => (
              <circle
                key={`knee-${a.obj}`}
                cx={a.x}
                cy={yFor(a, valueAt(kneeRow, a))}
                r={3}
                fill={a.colorVar}
                className="stroke-canvas"
                strokeWidth={1}
              />
            ))}
          </>
        )}
      </svg>

      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-2xs text-ink-muted">
        <span>
          {front.length} non-dominated candidate{front.length === 1 ? "" : "s"} · chosen solution
          (knee) in <span className="font-medium text-accent">bold</span>
        </span>
      </figcaption>

      {/* Screen-reader table — colour is never the sole channel (INV-CLR-011). */}
      {kneeRow && (
        <ul className="sr-only">
          {axes.map((a) => (
            <li key={`sr-${a.obj}`}>
              {`${a.label}: ${valueAt(kneeRow, a).toFixed(2)}, objective weight ${(weights[a.obj] ?? 0).toFixed(2)}`}
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
