// Feature: atlas-console-elevation, Property 8: State transitions preserve frozen identity hue
//
// Property 8 (Validates: Requirements 2.5) — for any agent and any PAIR of
// process states, the rendered identity colours share the same frozen hue
// coordinate (|Δhue| < 2°) and differ only in chroma. An agent's state never
// masquerades as a different agent.
//
// WHY THIS IS A MODEL-LEVEL PROPERTY
// ----------------------------------
// The presenter paints identity as a CSS `color-mix(in oklab, <hue> <pct>%,
// var(--syn-neutral-mix))` string. jsdom cannot resolve a `var(--syn-agent-*)`
// token to an OKLCH triple, so we cannot compute a numeric hue in degrees.
// Instead we assert the STRUCTURAL invariant that guarantees hue-freezing:
//   • the hue term of the mix is ALWAYS the agent's frozen identity token
//     `agentColorVar(agent)` — byte-identical across every state, so the hue
//     coordinate is provably invariant (Δhue = 0° < 2°); and
//   • the ONLY thing that changes between two states is the chroma-mix
//     percentage, which tracks the state descriptor's `chromaFactor`.
// If the hue term were ever a different agent's token (or the mix base changed
// the hue), the identity would masquerade — this property rules that out.
//
// The assertion is made against the ACTUAL rendered `AgentStatePresenter`
// output (its live-state dot's inline background), so it verifies the shipped
// component, not a re-implementation.

import {
  AGENT_STATES,
  AGENT_STATE_DESCRIPTORS,
  type AgentState,
} from "@domain/agent-state";
import type { RenderableAgentState } from "@domain/agent-state";
import { AGENT_NAMES, agentColorVar, type AgentName } from "@lib/agent-identity";
import { AgentStatePresenter } from "@ds/compounds/AgentStatePresenter";
import { cleanup, render } from "@testing-library/react";
import fc from "fast-check";
import { afterEach, describe, expect, it } from "vitest";

afterEach(() => cleanup());

const agentArb: fc.Arbitrary<AgentName> = fc.constantFrom(...AGENT_NAMES);
const stateArb: fc.Arbitrary<AgentState> = fc.constantFrom(...AGENT_STATES);

/** Build a `live` renderable state painted in the agent's frozen identity hue. */
function liveState(agent: AgentName, state: AgentState): RenderableAgentState {
  return {
    kind: "live",
    descriptor: AGENT_STATE_DESCRIPTORS[state],
    hue: agentColorVar(agent),
  };
}

interface ParsedMix {
  readonly hueTerm: string;
  readonly pct: number;
  /** The color-mix string with its percentage blanked — the shape/hue template. */
  readonly template: string;
}

// color-mix(in oklab, <hue term> <pct>%, var(--syn-neutral-mix))
const MIX_RE = /^color-mix\(in oklab, (.+) (\d+)%, var\(--syn-neutral-mix\)\)$/;

/** Render the presenter and parse its live identity-dot background color-mix. */
function renderIdentityMix(agent: AgentName, state: AgentState): ParsedMix {
  const { container } = render(
    <AgentStatePresenter state={liveState(agent, state)} agent={agent} />,
  );
  // The identity dot is the only element carrying an inline background.
  const dot = container.querySelector<HTMLElement>("span[style]");
  expect(dot).not.toBeNull();
  const background = dot!.style.background;
  const match = MIX_RE.exec(background);
  expect(match, `background did not match color-mix shape: ${background}`).not.toBeNull();
  const [, hueTerm, pctStr] = match!;
  return {
    hueTerm: hueTerm!,
    pct: Number(pctStr),
    template: background.replace(`${pctStr}%`, "<pct>%"),
  };
}

describe("AgentStatePresenter — Property 8: state transitions preserve frozen identity hue", () => {
  it("uses the agent's frozen identity token as the hue term in every state", () => {
    fc.assert(
      fc.property(agentArb, stateArb, (agent, state) => {
        const mix = renderIdentityMix(agent, state);
        // The hue term IS the frozen identity token — hue cannot drift.
        expect(mix.hueTerm).toBe(agentColorVar(agent));
        cleanup();
      }),
      { numRuns: 200 },
    );
  });

  it("across ANY pair of states, hue is byte-identical and only chroma % changes", () => {
    fc.assert(
      fc.property(agentArb, stateArb, stateArb, (agent, s1, s2) => {
        const a = renderIdentityMix(agent, s1);
        cleanup();
        const b = renderIdentityMix(agent, s2);
        cleanup();

        // 1) Frozen hue: the hue term is the SAME frozen identity token, so the
        //    hue coordinate is invariant across the transition (|Δhue| = 0 < 2°).
        expect(a.hueTerm).toBe(b.hueTerm);
        expect(a.hueTerm).toBe(agentColorVar(agent));

        // 2) Differ ONLY in chroma: with the percentage blanked, the two mixes
        //    are structurally identical — nothing but chroma moves.
        expect(a.template).toBe(b.template);

        // 3) The chroma percentage tracks each state's descriptor factor, and
        //    equal factors yield equal chroma (no hidden per-state hue shift).
        const f1 = AGENT_STATE_DESCRIPTORS[s1].chromaFactor;
        const f2 = AGENT_STATE_DESCRIPTORS[s2].chromaFactor;
        expect(a.pct).toBe(Math.round(f1 * 100));
        expect(b.pct).toBe(Math.round(f2 * 100));
        if (f1 === f2) expect(a.pct).toBe(b.pct);
      }),
      { numRuns: 200 },
    );
  });

  it("distinct agents never share a hue term (identity cannot masquerade)", () => {
    fc.assert(
      fc.property(agentArb, agentArb, stateArb, (agentA, agentB, state) => {
        fc.pre(agentA !== agentB);
        const a = renderIdentityMix(agentA, state);
        cleanup();
        const b = renderIdentityMix(agentB, state);
        cleanup();
        // Different agents → different frozen hue tokens, same state chroma %.
        expect(a.hueTerm).not.toBe(b.hueTerm);
        expect(a.pct).toBe(b.pct);
      }),
      { numRuns: 200 },
    );
  });
});
