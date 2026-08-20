import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import fc from "fast-check";
import { afterAll, afterEach, beforeAll, beforeEach, expect, vi } from "vitest";
import {
  activeBudget,
  budgetAttestation,
  FAST_CHECK_IMPLICIT_NUM_RUNS,
  FC_BUDGET_META_KEY,
} from "./fc-budget";
import { server } from "./msw-server";

// ---------------------------------------------------------------------------
// fast-check example budget: inherited from a profile, never stated in place
// ---------------------------------------------------------------------------
//
// R3.1/R3.2/R3.5 (AD-13's inheritance rule). This is the fast-check analogue of the root
// `conftest.py` Hypothesis profiles, resolved from the same `HYPOTHESIS_PROFILE`
// variable. See ./fc-budget.ts for the table, the deliberate unset->`dev` asymmetry with
// the Python side, and why the resolver lives in its own module.
//
// A per-call `{ numRuns }` overrides this global, so this configuration changes nothing
// in a file that still states one — which is why removing them (task 1.3) and inverting
// the inventory gate's clause (task 1.4) are the same logical move as this one.
const fcBudget = activeBudget();
fc.configureGlobal({ numRuns: fcBudget.numRuns });

// R3.9, first half: a silently failed global must be distinguishable from one that
// applied. Read the configuration back rather than trusting the call. fast-check's own
// implicit default is 100 (confirmed against the installed 3.23.2 — see ./fc-budget.ts),
// which would look CI-legal while costing a laptop ten times the intended `dev` budget:
// the one failure mode that must not pass silently (I-7). Throwing here aborts the run
// loudly, and a setup-file throw lands in the JSON reporter's per-file `message` field, so
// the failure is in the run record too rather than only on a console nobody parses.
const fcApplied: number | undefined = fc.readConfigureGlobal().numRuns;
if (fcApplied !== fcBudget.numRuns) {
  throw new Error(
    `fast-check global numRuns did not apply: resolved ${fcBudget.numRuns} from profile ` +
      `'${fcBudget.profile}' (requested ${JSON.stringify(fcBudget.requested)}, ` +
      `recognised=${String(fcBudget.recognised)}) but readConfigureGlobal reports ` +
      `${String(fcApplied)}. An unconfigured run falls back to fast-check's implicit ` +
      `${FAST_CHECK_IMPLICIT_NUM_RUNS}, which is not the declared budget.`,
  );
}

// R3.9, second half: report the EFFECTIVE count into the run record, on a passing run.
//
// The throw above only covers the failing case. A green run must also state the budget it
// ran at, or "the global applied" is an unfalsifiable claim about every other console
// property. `vitest.config.ts:34-35` writes `artifacts/test-reports/vitest.json`, and
// vitest 2.1.9's JSON reporter emits, per assertion result, exactly:
// `{ancestorTitles, fullName, status, title, duration, failureMessages, location, meta}`.
// Of those, `meta` is the only field a setup file can write on a PASSING test —
// `failureMessages` is populated from errors and a static test title carries no number. So
// `task.meta` is the channel, and it is the whole reason this is a hook rather than a
// `console.log`: stdout does not appear in that record at all.
//
// Stamped once per test file rather than once per test: the module-level flag resets with
// each isolated test-file module, so the record carries one attestation per file and not
// one per assertion. Under `isolate: false` the flag would survive and the record would
// carry fewer — at least one, which still satisfies R3.9, and vitest's default isolation
// is on.
//
// `Object.assign` rather than a cast or a `declare module` augmentation: `TaskMeta` is an
// empty interface re-exported from `@vitest/runner`, so an augmentation on the `"vitest"`
// module declares a second interface instead of merging with the first, and
// `@vitest/runner` is not a direct dependency here to augment by name.
let fcBudgetReported = false;
beforeEach((context) => {
  if (fcBudgetReported) {
    return;
  }
  fcBudgetReported = true;
  Object.assign(context.task.meta, {
    [FC_BUDGET_META_KEY]: budgetAttestation(fcBudget, fcApplied),
  });
});

// a11y matcher for the axe test layer (SENSORIUM accessibility rigor —
// WCAG 2.1 AA / INV-CLR-011). vitest-axe ships the `axe` runner as a proper
// value export, but types its `toHaveNoViolations` matcher as type-only, which
// trips `verbatimModuleSyntax`. So we implement the (tiny) matcher here against
// axe's result shape; types are augmented in ./vitest-axe.d.ts.
interface AxeNode {
  readonly html?: string;
}
interface AxeViolation {
  readonly id: string;
  readonly help: string;
  readonly nodes: ReadonlyArray<AxeNode>;
}
interface AxeResultsLike {
  readonly violations?: ReadonlyArray<AxeViolation>;
}

expect.extend({
  toHaveNoViolations(received: AxeResultsLike) {
    const violations = received?.violations ?? [];
    const pass = violations.length === 0;
    return {
      pass,
      message: () =>
        pass
          ? "expected accessibility violations, but found none"
          : `expected no accessibility violations, but found ${violations.length}:\n${violations
              .map((v) => `  [${v.id}] ${v.help} — ${v.nodes.length} node(s)`)
              .join("\n")}`,
    };
  },
});

// Inert global WebSocket for jsdom (CI crash-class guard).
//
// Any component that mounts `useFirehose` opens `new WebSocket(...)`. Without a
// stub, MSW intercepts a real socket and the half-open stream is destroyed on
// teardown — aborting the vitest worker with a native libuv assertion
// (uv__stream_destroy) on CI. This inert socket never opens, sends nothing, and
// closes cleanly, so no native stream ever exists. Installed per-test so the
// transport firehose test (which stubs its own MockWebSocket + unstubs after
// each) stays compatible. Tests that need socket behaviour stub their own.
class InertWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  readyState = InertWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(readonly url: string) {}
  send(_data: string): void {}
  close(): void {
    this.readyState = InertWebSocket.CLOSED;
    this.onclose?.();
  }
  addEventListener(): void {}
  removeEventListener(): void {}
}

// Start MSW for every test; reset handlers between tests.
beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
beforeEach(() => {
  // After MSW's beforeAll listen() patches the global, override with the inert
  // socket so live WS connections are never opened in jsdom.
  vi.stubGlobal("WebSocket", InertWebSocket);
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

// jsdom does not implement matchMedia.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// jsdom does not implement ResizeObserver (Radix Slider thumb sizing, Sigma).
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver;
}
