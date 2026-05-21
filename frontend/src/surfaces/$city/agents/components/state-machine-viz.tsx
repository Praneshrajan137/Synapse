/**
 * SYNAPSE Atlas Console — agent state-machine visualisation.
 *
 * Visx-driven SVG: states placed on a circle, transitions drawn as
 * curved arrows. The current state is highlighted; unreachable states
 * fade out. Animation is gated by `prefers-reduced-motion` (handled
 * by tokens.css globally).
 */
import { memo } from "react";
import { Group } from "@visx/group";
import type { AgentSpec } from "virtual:atlas/agent-specs";

import { layoutStateGraph, reachableFrom } from "../model/state-machine";

const SIZE = 180;
const NODE_R = 16;

export interface StateMachineVizProps {
  readonly spec: AgentSpec;
  readonly currentState?: string;
  readonly width?: number;
  readonly height?: number;
}

export const StateMachineViz = memo(function StateMachineViz({
  spec,
  currentState,
  width = SIZE,
  height = SIZE,
}: StateMachineVizProps) {
  const cx = width / 2;
  const cy = height / 2;
  const r = Math.min(width, height) / 2 - NODE_R - 6;
  const graph = layoutStateGraph(spec, { cx, cy, r });
  const reachable = reachableFrom(spec, graph.initial);
  const active = currentState ?? graph.initial;

  return (
    <svg
      role="img"
      aria-label={`${spec.agent_name} state machine`}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
    >
      <defs>
        <marker
          id={`arrow-${spec.agent_name}`}
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="rgb(var(--color-muted-fg))" />
        </marker>
      </defs>

      <Group>
        {graph.transitions.map((t) => {
          const dx = t.to_pos.x - t.from_pos.x;
          const dy = t.to_pos.y - t.from_pos.y;
          const len = Math.sqrt(dx * dx + dy * dy) || 1;
          const ux = dx / len;
          const uy = dy / len;
          // Stop short of the node so the arrowhead lands on its edge.
          const x1 = t.from_pos.x + ux * NODE_R;
          const y1 = t.from_pos.y + uy * NODE_R;
          const x2 = t.to_pos.x - ux * NODE_R;
          const y2 = t.to_pos.y - uy * NODE_R;
          const isErrorEdge = t.to === "ERROR";
          return (
            <line
              key={t.id}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={isErrorEdge ? "rgb(var(--color-tier-4))" : "rgb(var(--color-muted-fg))"}
              strokeWidth={isErrorEdge ? 1.6 : 1}
              strokeOpacity={0.7}
              markerEnd={`url(#arrow-${spec.agent_name})`}
            />
          );
        })}
        {graph.states.map((s) => {
          const isActive = s.name === active;
          const isReachable = reachable.has(s.name);
          const isError = s.name === "ERROR";
          const fill = isError
            ? "rgb(var(--color-tier-4) / 0.18)"
            : isActive
              ? "rgb(var(--color-tier-3) / 0.25)"
              : "rgb(var(--color-card))";
          const stroke = isError
            ? "rgb(var(--color-tier-4))"
            : isActive
              ? "rgb(var(--color-tier-3))"
              : "rgb(var(--color-border))";
          return (
            <Group key={s.name} opacity={isReachable ? 1 : 0.45}>
              <circle cx={s.x} cy={s.y} r={NODE_R} fill={fill} stroke={stroke} strokeWidth={isActive ? 2 : 1} />
              <text
                x={s.x}
                y={s.y + 4}
                textAnchor="middle"
                fontSize={9}
                fill="rgb(var(--color-fg))"
                style={{ fontFamily: "JetBrains Mono, ui-monospace, monospace" }}
              >
                {s.name.slice(0, 4)}
              </text>
            </Group>
          );
        })}
      </Group>
    </svg>
  );
});
