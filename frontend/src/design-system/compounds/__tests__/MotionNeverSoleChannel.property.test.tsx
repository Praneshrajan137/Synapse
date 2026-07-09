// Feature: atlas-console-elevation, Property 27: Motion is never the sole information channel
//
// Property 27 (Validates: Requirements 6.2, 6.3) — every animated state the
// Console can render (acting pulse, synthetic pulse, escalation beacon,
// decision arrival) retains a STATIC, non-motion representation that still
// conveys the full state when `prefers-reduced-motion` zeroes the motion
// tokens. Under reduced motion the animation freezes, so the surviving text /
// data-attribute / shape channel MUST carry the state on its own.
//
// The four animated states map to their static fallbacks as follows:
//   - acting pulse       → CouncilStrip: status word + `data-process-state` attr
//   - synthetic pulse    → SyntheticBadge: dashed ring + text label
//   - escalation beacon  → EscalationQueue: pending sort order + queue count
//   - decision arrival   → DecisionFirehoseTail: persistent row (id/tier/conf)
//
// The property samples over the set of animated states (with varied backing
// data) and asserts, for each, that BOTH a token-governed motion channel and a
// non-motion static channel are present — so removing the motion loses nothing.

import { DecisionEnvelopeSchema, type LiveDecision } from "@domain/decision-envelope";
import type { EscalationMessage } from "@domain/escalation";
import { CouncilStrip } from "@ds/compounds/CouncilStrip";
import { SyntheticBadge } from "@ds/compounds/SyntheticBadge";
import { AGENT_LABEL, AGENT_NAMES, type AgentName } from "@lib/agent-identity";
import type { EscalationEntry } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import { cleanup, render, screen, within } from "@testing-library/react";
import fc from "fast-check";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { DecisionFirehoseTail } from "../../../surfaces/mission-control/DecisionFirehoseTail";
import { EscalationQueue } from "../../../surfaces/override-cockpit/EscalationQueue";
// i18next global bootstrap (registers the "common" namespace used by badges).
import "@i18n/index";

// The four animated states named by Req 6.3. Each declares the token-governed
// animation utility that carries its MOTION channel and the number of runs so
// fast-check exercises the static fallback across varied backing data.
type AnimatedState = "acting-pulse" | "synthetic-pulse" | "escalation-beacon" | "decision-arrival";

const ANIMATION_CLASS: Record<AnimatedState, string> = {
  "acting-pulse": "animate-pulse-confidence",
  "synthetic-pulse": "animate-demo-pulse",
  "escalation-beacon": "animate-urgent-pulse",
  "decision-arrival": "animate-arrive",
};

const DECISION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

function makeEscalationMessage(confidence: number): EscalationMessage {
  return {
    type: "escalation",
    decision_id: DECISION_ID,
    tier: "tier_3",
    confidence,
    proposals: [],
    recommended_action: {},
    violations: [],
    reason: "escalated",
  };
}

function makeLiveDecision(confidence: number): LiveDecision {
  const parsed = DecisionEnvelopeSchema.parse({
    decision_id: DECISION_ID,
    tier: "tier_2",
    confidence,
  });
  return { ...parsed, timestamp: new Date(0).toISOString() };
}

// Force the reduced-motion posture jsdom cannot express with CSS: the point of
// the property is that the STATIC channel below survives with motion removed.
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
});

afterEach(() => {
  cleanup();
  useFirehoseStore.getState().flushAll();
});

// Render an animated state with arbitrary backing data and return the element
// that carries the motion class plus an assertion that a static channel holds.
function renderAnimatedState(state: AnimatedState, agent: AgentName, confidence: number): void {
  switch (state) {
    case "acting-pulse": {
      // An agent contributing to a live decision pulses; the status word and
      // `data-process-state` attribute carry "acting" without the animation.
      render(<CouncilStrip states={{ [agent]: { status: "healthy", active: true } }} />);
      const cell = screen.getByLabelText(new RegExp(AGENT_LABEL[agent], "i"));
      // Motion channel present (token-governed animation utility)…
      const dot = cell.querySelector(`.${ANIMATION_CLASS[state]}`);
      expect(dot).not.toBeNull();
      // …and a non-motion static channel conveying the same state.
      expect(cell.getAttribute("data-process-state")).toBe("acting");
      expect(cell.getAttribute("aria-label")).toMatch(/active in a live decision/i);
      expect(cell).toHaveTextContent(/live/i);
      return;
    }
    case "synthetic-pulse": {
      render(<SyntheticBadge />);
      const badge = screen.getByRole("img");
      expect(badge.className).toContain(ANIMATION_CLASS[state]);
      // Static channels: the dashed ring + the text label carry "synthetic".
      expect(badge.className).toMatch(/border-dashed/);
      expect(badge.textContent?.trim().length ?? 0).toBeGreaterThan(0);
      return;
    }
    case "escalation-beacon": {
      const entry: EscalationEntry = {
        id: DECISION_ID,
        received_at: 0,
        message: makeEscalationMessage(confidence),
        status: "pending",
      };
      render(<EscalationQueue entries={[entry]} activeId={null} onSelect={() => {}} />);
      const queue = screen.getByLabelText("Escalation queue");
      // Motion channel: the pending beacon beats at the urgent cadence…
      expect(queue.querySelector(`.${ANIMATION_CLASS[state]}`)).not.toBeNull();
      // …the beacon itself is aria-hidden, so state must survive via the
      // header count + pending sort order (both static, non-motion channels).
      const header = within(queue).getByText(/pending/i);
      expect(header).toHaveTextContent(/1 pending/i);
      return;
    }
    case "decision-arrival": {
      // Seed the firehose ring buffer so the tail renders one arriving row.
      useFirehoseStore.setState({
        decisions: { cap: 200, items: [makeLiveDecision(confidence)] },
      });
      render(
        <MemoryRouter>
          <DecisionFirehoseTail />
        </MemoryRouter>,
      );
      const row = screen.getByRole("listitem");
      // Motion channel: the entrance animation utility on the row…
      expect(row.className).toContain(ANIMATION_CLASS[state]);
      // …the row is a persistent element whose id/tier/confidence text remains
      // once the one-shot entrance settles (arrival is not the only signal).
      const link = within(row).getByRole("link");
      expect(link.getAttribute("aria-label")).toMatch(/decision/i);
      expect(link.textContent?.trim().length ?? 0).toBeGreaterThan(0);
      return;
    }
  }
}

describe("Motion System — Property 27: motion is never the sole information channel", () => {
  const stateArb: fc.Arbitrary<AnimatedState> = fc.constantFrom(
    "acting-pulse",
    "synthetic-pulse",
    "escalation-beacon",
    "decision-arrival",
  );
  const agentArb: fc.Arbitrary<AgentName> = fc.constantFrom(...AGENT_NAMES);
  const confidenceArb: fc.Arbitrary<number> = fc.integer({ min: 0, max: 100 }).map((n) => n / 100);

  it("every animated state retains a static representation under reduced motion", () => {
    fc.assert(
      fc.property(stateArb, agentArb, confidenceArb, (state, agent, confidence) => {
        renderAnimatedState(state, agent, confidence);
        cleanup();
        useFirehoseStore.getState().flushAll();
      }),
      { numRuns: 200 },
    );
  });
});
