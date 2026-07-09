// Feature: atlas-console-elevation, Property 6: Agent-state derivation is honest
//
// Property 6 (Validates: Requirements 2.2, 2.3, 2.6) — for any cognition event
// stream and evaluation time, `deriveAgentState`:
//   • returns `live` ONLY when a backing event for that agent exists in the
//     stream within the staleness window (never fabricates activity),
//   • returns `not-live` when the newest backing event is older than the
//     staleness window, and
//   • never returns a fabricated active state for an agent with no backing
//     per-agent cognition (arbitrating / learning phases → unavailable).
//
// NOTE ON `sinceMs`: the implementation reports `not-live.sinceMs` as the
// epoch-millisecond TIMESTAMP of the latest event (`Date.parse(latest.ts)`),
// NOT an age/elapsed duration. This test is written to match that actual
// behavior (verified against `frontend/src/lib/agent-state.ts`).

import { AGENT_STATES } from "@domain/agent-state";
import type { CognitionEvent, CognitionPhase } from "@domain/cognition-event";
import { AGENT_NAMES, type AgentName } from "@lib/agent-identity";
import { deriveAgentState } from "@lib/agent-state";
import { deriveLiveCognition } from "@lib/cognition";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const STALE_MS = 5000;
// A fixed epoch base so generated ISO timestamps round-trip losslessly.
const BASE_NOW = 1_700_000_000_000;

const CANONICAL_STATES: ReadonlySet<string> = new Set(AGENT_STATES);

const PHASES: readonly CognitionPhase[] = [
  "collecting",
  "debating",
  "arbitrating",
  "executing",
  "learning",
];

const agentArb: fc.Arbitrary<AgentName> = fc.constantFrom(...AGENT_NAMES);
const phaseArb: fc.Arbitrary<CognitionPhase> = fc.constantFrom(...PHASES);

interface Scenario {
  readonly nowMs: number;
  readonly decisionId: string;
  readonly agent: AgentName;
  readonly phase: CognitionPhase;
  /** Per-event age in ms relative to nowMs; last element is the latest event. */
  readonly ages: readonly number[];
  readonly proposed: readonly AgentName[];
}

const scenarioArb: fc.Arbitrary<Scenario> = fc.record({
  nowMs: fc.integer({ min: BASE_NOW, max: BASE_NOW + 1_000_000 }),
  decisionId: fc.uuid(),
  agent: agentArb,
  phase: phaseArb,
  // ages span both sides of the staleness window (0..20s).
  ages: fc.array(fc.integer({ min: 0, max: 20_000 }), { minLength: 1, maxLength: 6 }),
  proposed: fc.uniqueArray(agentArb, { maxLength: AGENT_NAMES.length }),
});

/** Build a concrete, well-formed event stream from a scenario. */
function buildEvents(s: Scenario): CognitionEvent[] {
  return s.ages.map((age, i): CognitionEvent => {
    const ts = new Date(s.nowMs - age).toISOString();
    const base: CognitionEvent = {
      decision_id: s.decisionId,
      phase: s.phase,
      ts,
    };
    // Give collecting events a per-agent "proposed" signal for realism.
    if (s.phase === "collecting" && i < s.proposed.length) {
      return { ...base, event: "proposed", agent_name: s.proposed[i] };
    }
    return base;
  });
}

describe("deriveAgentState — Property 6: derivation is honest", () => {
  it("returns `unavailable` for an empty event stream (never fabricates)", () => {
    fc.assert(
      fc.property(
        agentArb,
        fc.integer({ min: BASE_NOW, max: BASE_NOW + 1_000_000 }),
        (agent, nowMs) => {
          const result = deriveAgentState([], agent, nowMs, STALE_MS);
          expect(result.kind).toBe("unavailable");
        },
      ),
      { numRuns: 200 },
    );
  });

  it("returns one of the three renderable kinds, and never fabricates a live state", () => {
    fc.assert(
      fc.property(scenarioArb, (s) => {
        const events = buildEvents(s);
        const result = deriveAgentState(events, s.agent, s.nowMs, STALE_MS);

        expect(["live", "unavailable", "not-live"]).toContain(result.kind);

        const latest = events.at(-1);
        // Stream is always non-empty here.
        expect(latest).toBeDefined();
        const latestTsMs = Date.parse(latest!.ts as string);
        const latestAge = s.nowMs - latestTsMs;

        if (result.kind === "live") {
          // A live state MUST be backed by an in-window latest event ...
          expect(latestAge).toBeLessThanOrEqual(STALE_MS);
          // ... and by real per-agent cognition (not invented).
          const cognition = deriveLiveCognition(events, s.nowMs, STALE_MS);
          expect(cognition).not.toBeNull();
          expect(cognition?.agentStates[s.agent]).toBeDefined();
          // The rendered state is a canonical, closed-enum member.
          expect(CANONICAL_STATES.has(result.descriptor.state)).toBe(true);
        }
      }),
      { numRuns: 200 },
    );
  });

  it("returns `not-live` with sinceMs = latest event timestamp when the stream is stale (Req 2.6)", () => {
    // Force the latest event to be strictly older than the staleness window.
    const staleScenarioArb = scenarioArb.chain((s) =>
      fc.integer({ min: STALE_MS + 1, max: 60_000 }).map((latestAge) => ({
        ...s,
        // Append a definitively-stale latest event on top of the base stream.
        ages: [...s.ages, latestAge],
      })),
    );

    fc.assert(
      fc.property(staleScenarioArb, (s) => {
        const events = buildEvents(s);
        const result = deriveAgentState(events, s.agent, s.nowMs, STALE_MS);

        expect(result.kind).toBe("not-live");
        if (result.kind === "not-live") {
          const latestTsMs = Date.parse(events.at(-1)!.ts as string);
          // sinceMs is the epoch-ms TIMESTAMP of the latest event, not an age.
          expect(result.sinceMs).toBe(latestTsMs);
          expect(s.nowMs - result.sinceMs).toBeGreaterThan(STALE_MS);
        }
      }),
      { numRuns: 200 },
    );
  });

  it("never fabricates activity for phases with no per-agent cognition (arbitrating/learning)", () => {
    // Fresh (in-window) latest event in a phase that carries no per-agent state.
    const noCognitionArb = fc
      .record({
        nowMs: fc.integer({ min: BASE_NOW, max: BASE_NOW + 1_000_000 }),
        decisionId: fc.uuid(),
        agent: agentArb,
        phase: fc.constantFrom<CognitionPhase>("arbitrating", "learning"),
        freshAge: fc.integer({ min: 0, max: STALE_MS }),
      })
      .map(({ nowMs, decisionId, agent, phase, freshAge }) => {
        const events: CognitionEvent[] = [
          { decision_id: decisionId, phase, ts: new Date(nowMs - freshAge).toISOString() },
        ];
        return { events, agent, nowMs };
      });

    fc.assert(
      fc.property(noCognitionArb, ({ events, agent, nowMs }) => {
        const result = deriveAgentState(events, agent, nowMs, STALE_MS);
        // In-window but no backing per-agent event → unavailable, never live.
        expect(result.kind).toBe("unavailable");
      }),
      { numRuns: 200 },
    );
  });
});
