import type { CognitionEvent, CognitionPhase } from "@domain/cognition-event";
import { AGENT_NAMES, type AgentName } from "@lib/agent-identity";
import type { AgentProcessState } from "@lib/chromatics";

// ADR-048: derive the council's LIVE cognition from the recent phase-event
// buffer, so the CouncilStrip can show the agents thinking/debating in real
// time — backed by REAL orchestrator FSM events, never fabricated (I-7).

export interface LiveCognition {
  readonly decisionId: string;
  readonly phase: CognitionPhase;
  /** Per-agent process state derived from recorded events (never invented). */
  readonly agentStates: Partial<Record<AgentName, AgentProcessState>>;
}

/**
 * Honest by construction:
 *   • Returns null when the stream is STALE (latest event older than windowMs) —
 *     a council that is not deliberating is never painted "live".
 *   • Per-agent states come ONLY from recorded events: during `collecting` an
 *     agent is `thinking` until its `proposed` event lands (then `acting`);
 *     during `debating` the council is `debating`; during `executing` it is
 *     `acting`. `arbitrating`/`learning` are orchestrator-level — no per-agent
 *     cognition is invented, so those cells fall back to health-derived state.
 *
 * Pure: no Date.now / Math.random / I/O — `nowMs` is injected so it is
 * deterministically testable.
 */
export function deriveLiveCognition(
  events: readonly CognitionEvent[],
  nowMs: number,
  windowMs = 8000,
): LiveCognition | null {
  const latest = events.at(-1);
  if (!latest) return null;
  const tsMs = latest.ts ? Date.parse(latest.ts) : Number.NaN;
  if (Number.isFinite(tsMs) && nowMs - tsMs > windowMs) return null;

  const decisionId = latest.decision_id;
  const phase = latest.phase;
  const forDecision = events.filter((e) => e.decision_id === decisionId);

  const agentStates: Partial<Record<AgentName, AgentProcessState>> = {};
  if (phase === "collecting") {
    const proposed = new Set<string>();
    for (const e of forDecision) {
      if (e.phase === "collecting" && e.event === "proposed" && e.agent_name) {
        proposed.add(e.agent_name);
      }
    }
    for (const name of AGENT_NAMES) {
      agentStates[name] = proposed.has(name) ? "acting" : "thinking";
    }
  } else if (phase === "debating") {
    for (const name of AGENT_NAMES) agentStates[name] = "debating";
  } else if (phase === "executing") {
    for (const name of AGENT_NAMES) agentStates[name] = "acting";
  }

  return { decisionId, phase, agentStates };
}

/** Human label for the council's current phase (for the live banner). */
export function phaseLabel(phase: CognitionPhase): string {
  switch (phase) {
    case "collecting":
      return "collecting proposals";
    case "debating":
      return "debating";
    case "arbitrating":
      return "arbitrating";
    case "executing":
      return "executing";
    default:
      return "learning";
  }
}
