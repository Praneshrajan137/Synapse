import type { ParetoPoint } from "@/domain/decision";
import { cn } from "@/ui/lib/cn";
import { signal } from "@/ui/tokens";

/**
 * ParetoCell — the NSGA-II Pareto front of a decision.
 *
 * A cost/time tradeoff scatter; point opacity tracks sustainability and
 * the arbitration-selected knee point glows. This is where the operator
 * sees that a decision is a *value choice*, not a single right answer.
 */

export interface ParetoCellProps {
  front: readonly ParetoPoint[];
  className?: string;
}

const PAD = 12;
const SPAN = 100 - PAD * 2;

export function ParetoCell({ front, className }: ParetoCellProps) {
  if (front.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border border-line-faint bg-paper",
          className,
        )}
      >
        <p className="text-2xs text-ink-hint">Tier 1 — no Pareto arbitration</p>
      </div>
    );
  }

  const x = (cost: number) => PAD + cost * SPAN;
  const y = (time: number) => PAD + (1 - time) * SPAN;

  return (
    <figure
      className={cn(
        "flex flex-col rounded-lg border border-line-faint bg-paper p-3",
        className,
      )}
    >
      <figcaption className="mb-1 font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
        Pareto Front
      </figcaption>
      <svg
        viewBox="0 0 100 100"
        className="w-full flex-1"
        role="img"
        aria-label={`Pareto front with ${front.length} solutions; knee solution selected`}
      >
        <title>Cost vs. time Pareto front</title>
        {/* Axes */}
        <line
          x1={PAD}
          y1={100 - PAD}
          x2={100 - PAD}
          y2={100 - PAD}
          stroke="var(--color-line-strong)"
          strokeWidth={0.5}
        />
        <line
          x1={PAD}
          y1={PAD}
          x2={PAD}
          y2={100 - PAD}
          stroke="var(--color-line-strong)"
          strokeWidth={0.5}
        />

        {/* Front polyline */}
        <polyline
          points={front.map((p) => `${x(p.cost)},${y(p.time)}`).join(" ")}
          fill="none"
          stroke={signal.trace}
          strokeOpacity={0.4}
          strokeWidth={0.6}
        />

        {/* Solutions */}
        {front.map((p, i) => (
          <g key={`${p.cost}-${p.time}-${i}`}>
            {p.knee && (
              <circle
                cx={x(p.cost)}
                cy={y(p.time)}
                r={4.5}
                fill="none"
                stroke={signal.live}
                strokeWidth={0.7}
                className="animate-breathe"
              />
            )}
            <circle
              cx={x(p.cost)}
              cy={y(p.time)}
              r={p.knee ? 2.4 : 1.7}
              fill={p.knee ? signal.live : signal.trace}
              fillOpacity={p.knee ? 1 : 0.35 + p.sustainability * 0.5}
            >
              <title>
                {p.knee ? "Knee — selected · " : ""}
                cost {p.cost.toFixed(2)} · time {p.time.toFixed(2)} · fairness{" "}
                {p.fairness.toFixed(2)}
              </title>
            </circle>
          </g>
        ))}
      </svg>
      <div className="mt-1 flex justify-between text-2xs text-ink-hint">
        <span>← cost</span>
        <span className="text-sig-live">◆ knee solution</span>
        <span>time ↑</span>
      </div>
    </figure>
  );
}
