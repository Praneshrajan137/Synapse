/**
 * SYNAPSE Atlas Console — 5-phase LangGraph timeline.
 *
 * Visx-driven horizontal timeline. The five phases of the consensus
 * pipeline (ingest → propose → debate → select → commit) appear as
 * dots along an axis; clicking a dot scrolls the underlying context
 * messages into view in the drawer.
 *
 * Tokens drive every colour so the timeline renders correctly in dark
 * + light + AAA contrast modes.
 */
import { memo, useMemo } from "react";
import { Group } from "@visx/group";
import { scaleLinear } from "@visx/scale";

import type { ContextMessage } from "../model/decision";

const PHASE_LABELS: readonly string[] = [
  "Ingest",
  "Propose",
  "Debate",
  "Select",
  "Commit",
];

export interface PhaseTimelineProps {
  /** Phase actually reached (1-5) — unreached nodes render dim. */
  readonly phaseReached: number;
  readonly contextMessages: readonly ContextMessage[];
  readonly onPhaseSelect?: (phase: 1 | 2 | 3 | 4 | 5) => void;
  readonly width?: number;
  readonly height?: number;
}

export const PhaseTimeline = memo(function PhaseTimeline({
  phaseReached,
  contextMessages,
  onPhaseSelect,
  width = 600,
  height = 80,
}: PhaseTimelineProps) {
  const xScale = useMemo(
    () => scaleLinear<number>({ domain: [1, 5], range: [40, width - 40] }),
    [width],
  );

  const phaseCounts = useMemo(() => {
    const counts: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    for (const m of contextMessages) {
      if (typeof m.phase === "number" && m.phase >= 1 && m.phase <= 5) {
        counts[m.phase] = (counts[m.phase] ?? 0) + 1;
      }
    }
    return counts;
  }, [contextMessages]);

  const cy = height / 2;

  return (
    <svg
      role="img"
      aria-label="5-phase consensus timeline"
      width={width}
      height={height}
      className="w-full"
    >
      <Group>
        <line
          x1={xScale(1)}
          x2={xScale(5)}
          y1={cy}
          y2={cy}
          stroke="rgb(var(--color-border))"
          strokeWidth={2}
        />
        {[1, 2, 3, 4, 5].map((phase) => {
          const reached = phase <= phaseReached;
          const count = phaseCounts[phase] ?? 0;
          const fillVar = reached
            ? phase === phaseReached
              ? "rgb(var(--color-tier-3))"
              : "rgb(var(--color-tier-2))"
            : "rgb(var(--color-muted))";
          return (
            <Group key={phase}>
              <circle
                cx={xScale(phase)}
                cy={cy}
                r={reached ? 10 : 7}
                fill={fillVar}
                stroke="rgb(var(--color-card))"
                strokeWidth={2}
                style={{ cursor: onPhaseSelect ? "pointer" : "default" }}
                onClick={() =>
                  onPhaseSelect?.(phase as 1 | 2 | 3 | 4 | 5)
                }
              />
              <text
                x={xScale(phase)}
                y={cy - 18}
                textAnchor="middle"
                fontSize={11}
                fill="rgb(var(--color-fg))"
              >
                {PHASE_LABELS[phase - 1]}
              </text>
              <text
                x={xScale(phase)}
                y={cy + 22}
                textAnchor="middle"
                fontSize={10}
                fill="rgb(var(--color-muted-fg))"
              >
                {count > 0 ? `${count} msg` : ""}
              </text>
            </Group>
          );
        })}
      </Group>
    </svg>
  );
});
