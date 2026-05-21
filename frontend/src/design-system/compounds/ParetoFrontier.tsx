import { useMemo } from "react";
import { Group } from "@visx/group";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { scaleLinear } from "@visx/scale";
import { Circle } from "@visx/shape";
import { cn } from "@lib/cn";

export interface ParetoPoint {
  readonly id: string;
  readonly x: number;
  readonly y: number;
  readonly label?: string;
}

interface ParetoFrontierProps {
  readonly points: ReadonlyArray<ParetoPoint>;
  readonly selectedId?: string;
  readonly xLabel?: string;
  readonly yLabel?: string;
  readonly width?: number;
  readonly height?: number;
  readonly onSelect?: (id: string) => void;
  readonly weights?: Readonly<Record<string, number>>;
  readonly className?: string;
}

const MARGIN = { top: 16, right: 16, bottom: 32, left: 40 };

/**
 * 2D Pareto frontier scatter (visx). The selected point pulses; non-dominated
 * points are bright; dominated points dim. Weight vector is shown as a
 * legend chip below.
 *
 * "Dominated" here means: there exists another point with x' >= x and
 * y' >= y and strictly better in at least one dimension (FE-P9).
 */
export function ParetoFrontier({
  points,
  selectedId,
  xLabel = "objective A",
  yLabel = "objective B",
  width = 360,
  height = 220,
  onSelect,
  weights,
  className,
}: ParetoFrontierProps) {
  const dominated = useMemo(() => computeDominated(points), [points]);

  const innerWidth = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerHeight = Math.max(0, height - MARGIN.top - MARGIN.bottom);

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xScale = scaleLinear<number>({
    domain: [Math.min(...xs, 0), Math.max(...xs, 1)],
    range: [0, innerWidth],
    nice: true,
  });
  const yScale = scaleLinear<number>({
    domain: [Math.min(...ys, 0), Math.max(...ys, 1)],
    range: [innerHeight, 0],
    nice: true,
  });

  return (
    <figure className={cn("space-y-2", className)} aria-label="Pareto frontier scatter">
      <svg width={width} height={height} role="img" aria-labelledby="pareto-title">
        <title id="pareto-title">
          Pareto frontier: {points.length} proposals; selected highlighted
        </title>
        <Group left={MARGIN.left} top={MARGIN.top}>
          <AxisBottom
            top={innerHeight}
            scale={xScale}
            stroke="rgb(100 116 139)"
            tickStroke="rgb(100 116 139)"
            tickLabelProps={{ fill: "rgb(148 163 184)", fontSize: 10 }}
            label={xLabel}
            labelProps={{ fill: "rgb(148 163 184)", fontSize: 10 }}
          />
          <AxisLeft
            scale={yScale}
            stroke="rgb(100 116 139)"
            tickStroke="rgb(100 116 139)"
            tickLabelProps={{ fill: "rgb(148 163 184)", fontSize: 10 }}
            label={yLabel}
            labelProps={{ fill: "rgb(148 163 184)", fontSize: 10 }}
          />
          {points.map((p) => {
            const isSelected = p.id === selectedId;
            const isDominated = dominated.has(p.id);
            return (
              <g key={p.id}>
                <Circle
                  cx={xScale(p.x)}
                  cy={yScale(p.y)}
                  r={isSelected ? 7 : 4}
                  fill={
                    isSelected
                      ? "rgb(56 189 248)"
                      : isDominated
                        ? "rgb(100 116 139)"
                        : "rgb(129 140 248)"
                  }
                  stroke={isSelected ? "rgb(248 250 252)" : "transparent"}
                  strokeWidth={isSelected ? 2 : 0}
                  onClick={onSelect ? () => onSelect(p.id) : undefined}
                  style={onSelect ? { cursor: "pointer" } : undefined}
                  aria-label={`${p.label ?? p.id} (x=${p.x.toFixed(2)}, y=${p.y.toFixed(2)})${isSelected ? " — selected" : ""}${isDominated ? " — dominated" : ""}`}
                />
              </g>
            );
          })}
        </Group>
      </svg>
      {weights && (
        <dl className="flex flex-wrap gap-2 text-2xs text-ink-muted">
          {Object.entries(weights).map(([k, v]) => (
            <div
              key={k}
              className="rounded bg-surface-raised px-1.5 py-0.5"
              title={`Pareto weight for ${k}`}
            >
              <dt className="inline">{k}</dt>
              <dd className="ml-1 inline font-mono text-ink">{v.toFixed(2)}</dd>
            </div>
          ))}
        </dl>
      )}
    </figure>
  );
}

/** Compute the set of dominated point IDs (for visual dimming). */
function computeDominated(points: ReadonlyArray<ParetoPoint>): Set<string> {
  const out = new Set<string>();
  for (const a of points) {
    for (const b of points) {
      if (a.id === b.id) continue;
      if (b.x >= a.x && b.y >= a.y && (b.x > a.x || b.y > a.y)) {
        out.add(a.id);
        break;
      }
    }
  }
  return out;
}
