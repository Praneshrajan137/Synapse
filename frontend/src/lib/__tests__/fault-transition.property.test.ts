import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { resolveFault, type FaultEvent } from "../fault-transition";
import { type UniversalState } from "../universal-state";

// Feature: atlas-console-effectiveness
// Property 11: Fault/connectivity transition resolution is total and distinct —
// every transition maps to the correct distinct Universal_State and never
// latches on a prior state or renders false-healthy.
//
// `resolveFault(prev, e)` is TOTAL (every FaultEvent applied to any prior state
// yields exactly one of the six canonical Universal_States), derives its result
// solely from the event so it NEVER latches on `prev`, and a fault event never
// resolves to `populated` (no false-healthy render). Only genuine recovery
// events (return to online, a live WebSocket, or a successful HTTP response)
// restore the healthy `populated` state.
//
// **Validates: Requirements 8.1, 8.6**

const ALL_STATES: ReadonlySet<UniversalState> = new Set([
  "loading",
  "empty",
  "error",
  "degraded",
  "offline",
  "populated",
]);

const arbPrev: fc.Arbitrary<UniversalState> = fc.constantFrom(
  "loading",
  "empty",
  "error",
  "degraded",
  "offline",
  "populated",
);

// HTTP statuses spanning success/redirect (<400), the 503 brownout, other
// client/server errors, and the boundary at 400.
const arbHttp: fc.Arbitrary<FaultEvent> = fc
  .integer({ min: 100, max: 599 })
  .map((status) => ({ kind: "http" as const, status }));

const arbAuth401: fc.Arbitrary<FaultEvent> = fc
  .integer({ min: 1, max: 10 })
  .map((consecutive) => ({ kind: "auth-401" as const, consecutive }));

const arbWsFlap: fc.Arbitrary<FaultEvent> = fc
  .boolean()
  .map((live) => ({ kind: "ws-flap" as const, live }));

const arbEvent: fc.Arbitrary<FaultEvent> = fc.oneof(
  arbHttp,
  fc.constant<FaultEvent>({ kind: "schema-violation" }),
  arbAuth401,
  arbWsFlap,
  fc.constant<FaultEvent>({ kind: "offline" }),
  fc.constant<FaultEvent>({ kind: "online" }),
);

// A recovery event is one that legitimately restores health: return to online,
// a live socket, or a successful (<400) HTTP response. Every other event is a
// fault and must never resolve to `populated`.
function isRecovery(e: FaultEvent): boolean {
  switch (e.kind) {
    case "online":
      return true;
    case "ws-flap":
      return e.live;
    case "http":
      return e.status < 400;
    default:
      return false;
  }
}

// Independent reference mapping of each event to its expected distinct state.
function expectedState(e: FaultEvent): UniversalState {
  switch (e.kind) {
    case "offline":
      return "offline";
    case "online":
      return "populated";
    case "schema-violation":
      return "error";
    case "auth-401":
      return e.consecutive < 2 ? "loading" : "error";
    case "ws-flap":
      return e.live ? "populated" : "degraded";
    case "http":
      if (e.status === 503) return "degraded";
      if (e.status >= 400) return "error";
      return "populated";
  }
}

describe("Property 11: fault-transition resolution is total, distinct, and non-latching", () => {
  it("is total: every FaultEvent + any prior state maps to exactly one of the six states", () => {
    fc.assert(
      fc.property(arbPrev, arbEvent, (prev, e) => {
        const state = resolveFault(prev, e);
        expect(ALL_STATES.has(state)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it("maps each transition to its correct distinct Universal_State", () => {
    fc.assert(
      fc.property(arbPrev, arbEvent, (prev, e) => {
        expect(resolveFault(prev, e)).toBe(expectedState(e));
      }),
      { numRuns: 100 },
    );
  });

  it("never renders a false-healthy `populated` state for a fault event", () => {
    fc.assert(
      fc.property(arbPrev, arbEvent, (prev, e) => {
        if (!isRecovery(e)) {
          expect(resolveFault(prev, e)).not.toBe("populated");
        }
      }),
      { numRuns: 100 },
    );
  });

  it("never latches: the result is independent of the prior state", () => {
    fc.assert(
      fc.property(arbPrev, arbPrev, arbEvent, (prevA, prevB, e) => {
        // The same event applied from two arbitrary prior states must resolve
        // identically — the transition derives solely from the event.
        expect(resolveFault(prevA, e)).toBe(resolveFault(prevB, e));
      }),
      { numRuns: 100 },
    );
  });
});
