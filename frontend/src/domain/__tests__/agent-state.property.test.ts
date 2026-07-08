// Feature: atlas-console-elevation, Property 5: Agent-state enumeration is closed
// Feature: atlas-console-elevation, Property 7: Every rendered agent state carries a non-color channel and non-zero identity chroma
//
// Property 5 (Validates: Requirements 2.1) — `AgentStateSchema` parses a string
// if and only if the string is a member of `AGENT_STATES`, and every state the
// AUX layer can produce (every descriptor's `state`) is a member of that set.
//
// Property 7 (Validates: Requirements 2.4, 2.7) — for any `AgentState`, its
// descriptor exposes at least one non-color channel (a non-empty text label,
// plus a glyph and a `data-agent-state:*` attribute) and a chroma factor
// strictly greater than zero (identity hue is never chroma-drained to gray).

import {
  AGENT_STATES,
  AGENT_STATE_DESCRIPTORS,
  AgentStateSchema,
  agentStateDescriptor,
  type AgentState,
} from "@domain/agent-state";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const MEMBER_SET: ReadonlySet<string> = new Set(AGENT_STATES);

const agentStateArb: fc.Arbitrary<AgentState> = fc.constantFrom(...AGENT_STATES);

// Arbitrary string that is guaranteed NOT to be a canonical agent state.
const nonMemberStringArb: fc.Arbitrary<string> = fc
  .string({ maxLength: 30 })
  .filter((s) => !MEMBER_SET.has(s));

describe("AgentStateSchema — Property 5: Agent-state enumeration is closed", () => {
  it("parses successfully for every canonical member", () => {
    fc.assert(
      fc.property(agentStateArb, (state) => {
        const result = AgentStateSchema.safeParse(state);
        expect(result.success).toBe(true);
      }),
      { numRuns: 200 },
    );
  });

  it("rejects any string that is not a member of AGENT_STATES", () => {
    fc.assert(
      fc.property(nonMemberStringArb, (notAState) => {
        const result = AgentStateSchema.safeParse(notAState);
        // parses iff member; a non-member must fail.
        expect(result.success).toBe(false);
      }),
      { numRuns: 200 },
    );
  });

  it("parses iff member — the biconditional holds for arbitrary strings", () => {
    fc.assert(
      fc.property(
        fc.oneof(agentStateArb as fc.Arbitrary<string>, fc.string({ maxLength: 30 })),
        (candidate) => {
          const parses = AgentStateSchema.safeParse(candidate).success;
          expect(parses).toBe(MEMBER_SET.has(candidate));
        },
      ),
      { numRuns: 200 },
    );
  });

  it("every AUX-produced state (descriptor.state) is a member of AGENT_STATES", () => {
    fc.assert(
      fc.property(agentStateArb, (state) => {
        const descriptor = AGENT_STATE_DESCRIPTORS[state];
        expect(MEMBER_SET.has(descriptor.state)).toBe(true);
        // and it round-trips through the closed schema.
        expect(AgentStateSchema.safeParse(descriptor.state).success).toBe(true);
      }),
      { numRuns: 200 },
    );
  });
});

describe("agentStateDescriptor — Property 7: non-color channel + non-zero identity chroma", () => {
  it("exposes a non-empty label, glyph, matching data-agent-state attr, and chromaFactor > 0", () => {
    fc.assert(
      fc.property(agentStateArb, (state) => {
        const descriptor = agentStateDescriptor(state);

        // Non-color channel: text label present and non-empty.
        expect(descriptor.label.length).toBeGreaterThan(0);
        expect(descriptor.label.trim()).not.toBe("");

        // Non-color channel: a shape glyph present and non-empty.
        expect(descriptor.glyph.length).toBeGreaterThan(0);
        expect(descriptor.glyph.trim()).not.toBe("");

        // Non-color channel: stable data attribute keyed to the state.
        expect(descriptor.dataAttr).toBe(`agent-state:${state}`);

        // Identity chroma is never drained to neutral gray (Req 2.7).
        expect(descriptor.chromaFactor).toBeGreaterThan(0);
        expect(Number.isFinite(descriptor.chromaFactor)).toBe(true);
      }),
      { numRuns: 200 },
    );
  });
});
