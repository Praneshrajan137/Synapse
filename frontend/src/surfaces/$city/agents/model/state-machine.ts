/**
 * SYNAPSE Atlas Console — agent state-machine helpers.
 *
 * Plan §5.5: every agent panel renders the canonical 6-state machine
 * (IDLE → PROPOSING → DEBATING → EXECUTING → LEARNING → ERROR) plus
 * the agent-specific transitions sourced from `spec.yaml`.
 *
 * The functions below take a typed `AgentSpec` and lay states out on
 * a circle so the graph renders without a layout pass per render.
 * Pure + deterministic so property tests can pin geometry.
 */
import type { AgentSpec, AgentStateTransition } from "virtual:atlas/agent-specs";

export interface PlacedState {
  readonly name: string;
  readonly x: number;
  readonly y: number;
}

export interface PlacedTransition extends AgentStateTransition {
  readonly id: string;
  readonly from_pos: PlacedState;
  readonly to_pos: PlacedState;
}

export interface StateGraph {
  readonly states: readonly PlacedState[];
  readonly transitions: readonly PlacedTransition[];
  readonly initial: string;
}

/**
 * Lay states evenly on a circle of radius `r` centred at (cx, cy).
 * Order is taken from spec.states so visual identity is stable.
 */
export function layoutStateGraph(
  spec: AgentSpec,
  options: { cx: number; cy: number; r: number },
): StateGraph {
  const { cx, cy, r } = options;
  const states = spec.state_machine.states;
  const placed: PlacedState[] = states.map((name, i) => {
    const theta = (-Math.PI / 2) + (2 * Math.PI * i) / states.length;
    return {
      name,
      x: cx + r * Math.cos(theta),
      y: cy + r * Math.sin(theta),
    };
  });
  const byName = new Map(placed.map((p) => [p.name, p]));

  const transitions: PlacedTransition[] = spec.state_machine.transitions
    .map((t, i) => {
      const from = byName.get(t.from);
      const to = byName.get(t.to);
      if (!from || !to) return null;
      return {
        ...t,
        id: `${spec.agent_name}-t-${i}`,
        from_pos: from,
        to_pos: to,
      };
    })
    .filter((t): t is PlacedTransition => t !== null);

  return { states: placed, transitions, initial: spec.state_machine.initial_state };
}

/**
 * Return the set of states reachable from `start` along the graph.
 * Used by the Agent Floor drawer to dim unreachable nodes.
 */
export function reachableFrom(
  spec: AgentSpec,
  start: string,
): ReadonlySet<string> {
  const adj = new Map<string, string[]>();
  for (const t of spec.state_machine.transitions) {
    if (!adj.has(t.from)) adj.set(t.from, []);
    adj.get(t.from)!.push(t.to);
  }
  const seen = new Set<string>([start]);
  const stack: string[] = [start];
  while (stack.length > 0) {
    const cur = stack.pop()!;
    for (const next of adj.get(cur) ?? []) {
      if (!seen.has(next)) {
        seen.add(next);
        stack.push(next);
      }
    }
  }
  return seen;
}
