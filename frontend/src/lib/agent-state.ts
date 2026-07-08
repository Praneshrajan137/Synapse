import {
  type AgentState,
  type RenderableAgentState,
  agentStateDescriptor,
} from "@domain/agent-state";
import type { CognitionEvent } from "@domain/cognition-event";
import { type AgentName, agentColorVar } from "@lib/agent-identity";
import type { AgentProcessState } from "@lib/chromatics";
import { deriveLiveCognition } from "@lib/cognition";

// Honest per-agent state derivation (Atlas Console Elevation, Req 2.2/2.3/2.6).
//
// `deriveAgentState` extends `deriveLiveCognition`: it maps the council's
// RECORDED cognition (per-agent process states derived from real orchestrator
// FSM events) to a member of the canonical closed `AGENT_STATES` union, and
// NEVER fabricates activity:
//
//   • no backing event at all            → `unavailable` (no-backend-event)
//   • newest backing event is stale (> staleMs)
//                                         → `not-live` (Req 2.6)
//   • a live stream with no per-agent
//     event for THIS agent (arbitrating /
//     learning carry no per-agent cognition)
//                                         → `unavailable`
//   • otherwise                          → `live` with the state descriptor and
//                                           the agent's FROZEN identity hue var
//                                           (INV-CLR-012 — hue never changes;
//                                           only chroma may, via the descriptor
//                                           chroma factor).
//
// Pure: no `Date.now` / `Math.random` / I/O — `nowMs` is injected so the
// derivation is deterministically testable (Property 6, Req 2.2/2.3/2.6).

/**
 * Map the recorded chroma-rationing process-state grammar
 * (`AgentProcessState`, the sub-grammar `deriveLiveCognition` produces) onto
 * the canonical lifecycle `AgentState` union. Total over the grammar so no
 * recorded process state is ever dropped.
 */
const PROCESS_STATE_TO_AGENT_STATE: Record<AgentProcessState, AgentState> = {
  interrupted: "interrupting",
  waiting: "waiting",
  thinking: "thinking",
  debating: "thinking",
  acting: "acting",
  escalated: "escalating",
};

/**
 * Derive the renderable state of a single agent from the recorded cognition
 * event buffer. Pure — `nowMs` and `staleMs` are injected. Never invents an
 * active state that has no backing event (Req 2.2/2.3); renders `not-live` when
 * the newest backing event is older than `staleMs` (Req 2.6).
 */
export function deriveAgentState(
  events: readonly CognitionEvent[],
  agent: AgentName,
  nowMs: number,
  staleMs = 5000,
): RenderableAgentState {
  const latest = events.at(-1);

  // No backing event at all — never fabricate activity (Req 2.2/2.3).
  if (!latest) {
    return { kind: "unavailable", reason: "no-backend-event" };
  }

  // The stream is stale: the newest backing event is older than the staleness
  // window, so the council is not-live rather than frozen-as-active (Req 2.6).
  const tsMs = latest.ts ? Date.parse(latest.ts) : Number.NaN;
  if (Number.isFinite(tsMs) && nowMs - tsMs > staleMs) {
    return { kind: "not-live", sinceMs: tsMs };
  }

  // Honest per-agent state — recorded events only, via `deriveLiveCognition`
  // (same latest-event / staleness gate, so it agrees with the check above).
  const cognition = deriveLiveCognition(events, nowMs, staleMs);
  const processState = cognition?.agentStates[agent];

  // A live stream with no backing event for THIS agent (e.g. the arbitrating /
  // learning phases carry no per-agent cognition) → unavailable, never invented.
  if (!processState) {
    return { kind: "unavailable", reason: "no-backend-event" };
  }

  const state = PROCESS_STATE_TO_AGENT_STATE[processState];
  return {
    kind: "live",
    descriptor: agentStateDescriptor(state),
    // Frozen identity hue var — hue never changes across transitions
    // (INV-CLR-012, Req 2.5); chroma is rationed via the descriptor factor.
    hue: agentColorVar(agent),
  };
}
