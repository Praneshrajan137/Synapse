import { AGENT_STATE_FACTOR } from "@lib/chromatics";
import { z } from "zod";

// Canonical Agent-State Model (Atlas Console Elevation, Req 2).
//
// A CLOSED, enumerated union covering every observable agent lifecycle/process
// state the AUX layer can render. This supersedes the narrower
// `AgentProcessState` (in `@lib/chromatics`), which remains the chroma-rationing
// sub-grammar: process states reuse their factor verbatim here, and the new
// lifecycle states are assigned factors authored in the color token source
// (`design-system/color/tokens/semantic.tokens.json` → `factor.agentstate.*`),
// never invented in TS. Every factor is strictly > 0 so agent identity hue is
// never chroma-drained to neutral gray, in every state including interrupting
// and failing (Req 2.7, INV-CLR-017).

/**
 * The closed, canonical set of agent states (Req 2.1). Every state the AUX
 * layer renders SHALL be a member of this tuple.
 */
export const AGENT_STATES = [
  "idle",
  "thinking",
  "searching",
  "planning",
  "acting",
  "streaming",
  "waiting",
  "asking",
  "uncertain",
  "confident",
  "delegating",
  "escalating",
  "interrupting",
  "recovering",
  "failing",
  "succeeding",
  "handing-off",
  "completing",
] as const;

export type AgentState = (typeof AGENT_STATES)[number];

/** Closed enum: rejects any string that is not a canonical agent state. */
export const AgentStateSchema = z.enum(AGENT_STATES);

/**
 * A glyph token — an icon/shape identifier that carries meaning WITHOUT colour
 * (INV-CLR-011, Req 2.4). Glyphs are Unicode shape characters, consistent with
 * the rest of the design system (`@lib/agent-identity`, `ThemeToggle`,
 * `AttentionBeacon`). Never empty.
 */
export type GlyphId = string;

/**
 * Non-colour descriptor every rendered agent state must carry (Req 2.4): a
 * human-readable label, a shape glyph, a `data-agent-state:*` attribute, and a
 * chroma-rationing factor strictly greater than zero (Req 2.7).
 */
export interface AgentStateDescriptor {
  readonly state: AgentState;
  /** i18n label (resolved against the single `en` catalog). Never empty. */
  readonly label: string;
  /** Icon/shape token — a non-colour channel. Never empty. */
  readonly glyph: GlyphId;
  /** Chroma-rationing factor, strictly > 0 (Req 2.7). */
  readonly chromaFactor: number;
  /** Stable non-colour data attribute for styling/testing hooks. */
  readonly dataAttr: `agent-state:${AgentState}`;
}

/**
 * Availability wrapper — the AUX layer never fabricates activity (Req 2.2/2.3).
 * A state with a backing backend event renders `live`; a state with no backing
 * event renders `unavailable`; a stale stream (no backing event within the
 * staleness window, default 5s) renders `not-live` (Req 2.6).
 */
export type RenderableAgentState =
  | { kind: "live"; descriptor: AgentStateDescriptor; hue: string /* frozen identity var */ }
  | { kind: "unavailable"; reason: "no-backend-event" }
  | { kind: "not-live"; sinceMs: number };

/**
 * Per-state chroma-rationing factor mapping (Req 2.7, INV-CLR-017).
 *
 * Values mirror `factor.agentstate.*` in the color token source (pinned against
 * `design-system/color/dist/tokens.json` by the drift test). Process states
 * that already exist in the `AgentProcessState` grammar REUSE their factor
 * verbatim from `AGENT_STATE_FACTOR`; the new lifecycle states take the factors
 * authored alongside them in the token source. Every factor is strictly > 0
 * (interrupting floor = 0.25).
 */
export const AGENT_STATE_CHROMA_FACTOR: Record<AgentState, number> = {
  idle: 0.3,
  thinking: AGENT_STATE_FACTOR.thinking, // 0.55
  searching: 0.6,
  planning: 0.65,
  acting: AGENT_STATE_FACTOR.acting, // 1
  streaming: 0.85,
  waiting: AGENT_STATE_FACTOR.waiting, // 0.35
  asking: 0.4,
  uncertain: 0.45,
  confident: 0.9,
  delegating: 0.7,
  escalating: 1,
  interrupting: 0.25, // floor (Req 2.7)
  recovering: 0.5,
  failing: 1, // identity stays fully identifiable even when failing (Req 2.7)
  succeeding: 1,
  "handing-off": 0.72,
  completing: 1,
};

/**
 * Shape glyphs per state — a non-colour signal (Req 2.4). Each is a distinct
 * Unicode shape so states are legible without colour and without motion.
 */
const AGENT_STATE_GLYPH: Record<AgentState, GlyphId> = {
  idle: "○",
  thinking: "◐",
  searching: "⌕",
  planning: "▤",
  acting: "▶",
  streaming: "≋",
  waiting: "⋯",
  asking: "?",
  uncertain: "~",
  confident: "✓",
  delegating: "⇄",
  escalating: "▲",
  interrupting: "⏸",
  recovering: "↻",
  failing: "✕",
  succeeding: "★",
  "handing-off": "⇥",
  completing: "⬤",
};

/**
 * Human-readable labels per state (resolved English catalog values, Req 2.4).
 * Never empty.
 */
const AGENT_STATE_LABEL: Record<AgentState, string> = {
  idle: "Idle",
  thinking: "Thinking",
  searching: "Searching",
  planning: "Planning",
  acting: "Acting",
  streaming: "Streaming",
  waiting: "Waiting",
  asking: "Asking",
  uncertain: "Uncertain",
  confident: "Confident",
  delegating: "Delegating",
  escalating: "Escalating",
  interrupting: "Interrupting",
  recovering: "Recovering",
  failing: "Failing",
  succeeding: "Succeeding",
  "handing-off": "Handing off",
  completing: "Completing",
};

/** Build the non-colour descriptor for a single state. */
function buildDescriptor(state: AgentState): AgentStateDescriptor {
  return {
    state,
    label: AGENT_STATE_LABEL[state],
    glyph: AGENT_STATE_GLYPH[state],
    chromaFactor: AGENT_STATE_CHROMA_FACTOR[state],
    dataAttr: `agent-state:${state}`,
  };
}

/**
 * The frozen descriptor table — the single source every renderer consumes so
 * each state always carries its non-colour channels and a non-zero chroma
 * factor (Req 2.4, 2.7).
 */
export const AGENT_STATE_DESCRIPTORS: Record<AgentState, AgentStateDescriptor> = Object.fromEntries(
  AGENT_STATES.map((state) => [state, buildDescriptor(state)]),
) as Record<AgentState, AgentStateDescriptor>;

/** Descriptor lookup for a canonical agent state. */
export function agentStateDescriptor(state: AgentState): AgentStateDescriptor {
  return AGENT_STATE_DESCRIPTORS[state];
}
