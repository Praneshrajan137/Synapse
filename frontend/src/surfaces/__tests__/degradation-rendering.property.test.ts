/**
 * Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded
 * data is shown
 *
 * Validates: Requirements 3.5, 4.3, 13.6
 *
 * Property-based verification that the console cannot display a value derived from a degraded,
 * synthetic-sourced, or non-existent pipeline read without saying so on the surface that
 * displays it (design "Property 31: Degradation is rendered wherever degraded data is shown";
 * Requirements 3.5, 4.3, 13.6).
 *
 * What is universally quantified
 * ------------------------------
 * Two spaces, crossed:
 *
 *   1. THE WHOLE DECLARED REGISTRY - every id in `SURFACE_DATA_PATH_IDS`, not a hand-picked
 *      handful. Driving the suite off the exported id list is what makes the claim total: a
 *      panel registered tomorrow is covered by every facet below on the next run, and a panel
 *      whose notice copy is missing fails rather than passing unnoticed.
 *   2. THE WHOLE TRI-STATE SIGNAL SPACE - `degraded` and `synthetic` each range over
 *      `true | false | null`. `null` is the shape a payload carrying no provenance block
 *      produces, and under I-7 it is a different claim from `false`; quantifying over it is how
 *      "absence of proof is never rendered as health" becomes mechanical rather than
 *      conventional.
 *
 * Every facet renders the REAL `DataPathNotice` into jsdom and reads the state back OFF THE DOM
 * (`data-data-path`, `data-synthetic-sourced`) instead of trusting the resolver's return value,
 * because R3.5 / R4.3 / R13.6 are obligations about what an operator SEES. Rendered copy is
 * compared against `t(state.labelKey)` / `t(state.detailKey)`, and each key is asserted to
 * resolve to something other than itself - so a registered panel whose copy is absent from the
 * catalog renders a raw key and goes RED rather than quietly rendering a meaningless string.
 *
 * Why these facets suffice
 * ------------------------
 *  - Completeness (facet 2): one resolved state per registered path, exactly one rendered
 *    `[data-data-path]` per notice - the "one per row" contract `data-paths.ts` documents - and
 *    the resolved state's fields are mutually exclusive, so "exactly one state" is not a
 *    superposition of two.
 *  - R3.5 (facets 3, 4): degraded in => degraded rendered, stated in BOTH directions. Facet 4 is
 *    the total form: over the entire registry and the entire signal space, a rendered "live"
 *    implies the read affirmatively reported `degraded === false`. There is therefore no signal
 *    combination that yields a degraded pipeline response and a `live` rendering.
 *  - R4.3 (facets 5, 6, 7, 8): an aggregate derived from an `is_synthetic` state is labelled;
 *    `"never"` is the ONLY `SyntheticSource` that renders `false` for a synthetic state; the
 *    label survives a degraded read on the SAME element (no precedence ordering swallows it);
 *    and an unaffirmed flag is never upgraded into a synthetic claim, with its absence
 *    disclosed instead of collapsed into `false`.
 *  - R13.6 (facets 9, 10): also both directions. Every `ABSENT_DATA_PATH_IDS` entry renders its
 *    declared empty state AND the statement that no data path exists; and a panel that HAS an
 *    endpoint never renders as absent for any signals - without which the facet would pass on a
 *    resolver that returned "absent" for everything.
 *  - I-7 (facet 11): `unknown` is rendered, and rendered DISTINCTLY from `live`. An unreadable
 *    or missing signal is never rendered as health.
 *  - Non-vacuity (facet 1): the generated domain provably reaches all four `DataPathKind`s and
 *    both `syntheticSourced` values, and the four kind labels resolve to four DISTINCT strings -
 *    so "rendered distinctly" is a checked fact rather than an assumption, and no facet below
 *    can pass because its interesting branch was never generated.
 *
 * DOM hygiene: `renderNotice` asserts the document holds no `[data-data-path]` node BEFORE it
 * renders and unmounts in a `finally`, and the suite re-asserts emptiness after every test. An
 * exactly-one-element count is worthless if a previous iteration's node is still mounted, and
 * the global setup's `cleanup()` runs only between `it`s - not between the hundred renders
 * inside one.
 *
 * Why this file sits under `src/` and not `spec/effectiveness/__tests__/`
 * -----------------------------------------------------------------------
 * Both directories are in `vitest.config.ts`'s `include` and both run under the global `jsdom`
 * environment, so either would EXECUTE. Only this one is inside `tsconfig.json`'s `include`
 * (`["src", ...]`) and inside `biome check ./src`, so only this one is covered by CI's
 * `pnpm typecheck` and `pnpm lint` steps (frontend.yml, job `quality`). A property test whose
 * types nothing checks until the runner reaches it is weaker evidence than one the compiler
 * gates - and this is also where the code under test lives (`../data-paths`). Precedent:
 * `src/app/__tests__/primary-surfaces.property.test.ts` (atlas-console-elevation Property 28).
 */

import {
  type DataPathClass,
  type DataPathKind,
  DataPathNotice,
  type DataPathNoticeState,
  type DataPathSignals,
  type DataPathSpec,
  type SyntheticSource,
  resolveDataPath,
} from "@ds/compounds/DataPathNotice";
// Bootstraps i18next (registers the "common" namespace) AND exposes the non-React `t` used to
// resolve the copy each notice is asserted to actually render. Without the bootstrap every
// assertion below would compare raw translation keys against raw translation keys and prove
// nothing.
import { t } from "@i18n/index";
import { cleanup, render } from "@testing-library/react";
import fc from "fast-check";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";
import {
  ABSENT_DATA_PATH_IDS,
  SURFACE_DATA_PATHS,
  SURFACE_DATA_PATH_IDS,
  type SurfaceDataPathId,
  surfaceDataPath,
} from "../data-paths";

// ─────────────────────────────────────────────────────────────────────────────
// Domains
// ─────────────────────────────────────────────────────────────────────────────

/** The closed `DataPathKind` union, enumerated so coverage over it is checkable. */
const ALL_KINDS: ReadonlyArray<DataPathKind> = ["absent", "degraded", "unknown", "live"];

/** The closed `SyntheticSource` union. */
const ALL_SYNTHETIC_SOURCES: ReadonlyArray<SyntheticSource> = ["world", "decision", "never"];

/** The closed `DataPathClass` union. */
const ALL_DATA_CLASSES: ReadonlyArray<DataPathClass> = ["pipeline", "client-window"];

/**
 * The tri-state a provenance signal can arrive in. `null` is not a third flavour of `false`:
 * it means the payload does not carry the fact at all (I-7).
 */
const TRI_STATES: ReadonlyArray<boolean | null> = [true, false, null];

/** Registered ids that DO have an endpoint - the R3.5 / R4.3 population. */
const PRESENT_DATA_PATH_IDS: ReadonlyArray<SurfaceDataPathId> = SURFACE_DATA_PATH_IDS.filter(
  (id) => SURFACE_DATA_PATHS[id].endpoint !== null,
);

// ─────────────────────────────────────────────────────────────────────────────
// Non-vacuity oracle
//
// Deterministically enumerate the EXACT domain the arbitraries draw from
// (`SURFACE_DATA_PATH_IDS` x TRI_STATES x TRI_STATES) and record which kinds and which
// synthetic verdicts it reaches. Enumeration rather than `fc.sample` on purpose: a sampled
// coverage guard is only probably non-vacuous, and a probabilistic guard against vacuity is
// itself a way to pass vacuously.
// ─────────────────────────────────────────────────────────────────────────────

const LABEL_KEY_BY_KIND = new Map<DataPathKind, string>();
const REACHED_SYNTHETIC_SOURCED = new Set<boolean>();
const REACHED_SYNTHETIC_UNKNOWN = new Set<boolean>();

for (const id of SURFACE_DATA_PATH_IDS) {
  for (const degraded of TRI_STATES) {
    for (const synthetic of TRI_STATES) {
      const state = surfaceDataPath(id, { degraded, synthetic });
      LABEL_KEY_BY_KIND.set(state.kind, state.labelKey);
      REACHED_SYNTHETIC_SOURCED.add(state.syntheticSourced);
      REACHED_SYNTHETIC_UNKNOWN.add(state.syntheticUnknown);
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Generators
//
// `fc.constantFrom(...)` over an EMPTY list throws at module load, which is the loud failure we
// want if the registry (or its absent subset) is ever emptied: facet 1 asserts both are
// non-empty, and a registry that cannot even build its generators must not report green.
// ─────────────────────────────────────────────────────────────────────────────

const idArb = fc.constantFrom<SurfaceDataPathId>(...SURFACE_DATA_PATH_IDS);
const presentIdArb = fc.constantFrom<SurfaceDataPathId>(...PRESENT_DATA_PATH_IDS);
const absentIdArb = fc.constantFrom<SurfaceDataPathId>(...ABSENT_DATA_PATH_IDS);

const triStateArb = fc.constantFrom<boolean | null>(...TRI_STATES);
const syntheticSourceArb = fc.constantFrom<SyntheticSource>(...ALL_SYNTHETIC_SOURCES);
const dataClassArb = fc.constantFrom<DataPathClass>(...ALL_DATA_CLASSES);

/**
 * The two signal values that are NOT an affirmative synthetic claim. `false` says "measured,
 * not synthetic"; `null` says "the payload does not carry the fact". Neither may render as
 * synthetic-sourced, and only `null` may render as disclosed-unknown.
 */
const unaffirmedArb = fc.constantFrom<boolean | null>(false, null);

/** Any provenance pair a read can hand a panel, including "carries neither fact". */
const signalsArb: fc.Arbitrary<DataPathSignals> = fc.record({
  degraded: triStateArb,
  synthetic: triStateArb,
});

// ─────────────────────────────────────────────────────────────────────────────
// Render harness
// ─────────────────────────────────────────────────────────────────────────────

/** What the operator can actually see, snapshotted before the node is unmounted. */
interface RenderedNotice {
  /** How many `[data-data-path]` elements the whole document holds. Must be exactly 1. */
  readonly count: number;
  readonly kind: string | null;
  readonly syntheticSourced: string | null;
  readonly text: string;
}

const NOTICE_SELECTOR = "[data-data-path]";

/**
 * Render one resolved state, snapshot the rendered facts, and unmount.
 *
 * The pre-render emptiness assertion is load-bearing: `count` below is measured over
 * `document.body`, so a node leaked by the previous property iteration would silently turn the
 * "exactly one notice per row" claim into "at least one somewhere". `cleanup()` runs in a
 * `finally` so a failing assertion still leaves the document clean for the shrinker's next
 * attempt.
 */
function renderNotice(state: DataPathNoticeState): RenderedNotice {
  cleanup();
  expect(document.body.querySelectorAll(NOTICE_SELECTOR)).toHaveLength(0);
  try {
    render(createElement(DataPathNotice, { state }));
    const nodes = document.body.querySelectorAll(NOTICE_SELECTOR);
    const notice = nodes.item(0);
    return {
      count: nodes.length,
      kind: notice === null ? null : notice.getAttribute("data-data-path"),
      syntheticSourced: notice === null ? null : notice.getAttribute("data-synthetic-sourced"),
      text: notice === null ? "" : (notice.textContent ?? ""),
    };
  } finally {
    cleanup();
  }
}

/**
 * Resolve a copy key and assert it is really copy. `t` echoes an unregistered key back, so this
 * is how "the surface states X" stays a claim about prose rather than about a key string.
 */
function copy(key: string): string {
  const resolved = t(key);
  expect(resolved).not.toBe(key);
  expect(resolved.length).toBeGreaterThan(0);
  return resolved;
}

afterEach(() => {
  cleanup();
  // Nothing may survive a test. The per-iteration count assertions are only meaningful against
  // an empty document, so a leak is a defect in this suite, not a detail.
  expect(document.body.querySelectorAll(NOTICE_SELECTOR)).toHaveLength(0);
});

describe("Property 31: Degradation is rendered wherever degraded data is shown", () => {
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("guards the registry, the absent subset, and the kind coverage of the generated space", () => {
    // The registry is the quantification domain; an empty one would make every facet vacuous.
    expect(SURFACE_DATA_PATH_IDS.length).toBeGreaterThan(0);
    expect(PRESENT_DATA_PATH_IDS.length).toBeGreaterThan(0);
    expect(ABSENT_DATA_PATH_IDS.length).toBeGreaterThan(0);

    // R13.6's subset is a real subset of the registry, and is exactly the endpoint-less set -
    // so "iterate ABSENT_DATA_PATH_IDS" and "iterate the panels with no endpoint" name the
    // same population.
    const registry = new Set<SurfaceDataPathId>(SURFACE_DATA_PATH_IDS);
    for (const id of ABSENT_DATA_PATH_IDS) {
      expect(registry.has(id)).toBe(true);
      expect(SURFACE_DATA_PATHS[id].endpoint).toBeNull();
    }
    expect(ABSENT_DATA_PATH_IDS.length + PRESENT_DATA_PATH_IDS.length).toBe(
      SURFACE_DATA_PATH_IDS.length,
    );

    // The generated domain reaches every DataPathKind, so no facet below passes because its
    // interesting branch was never generated.
    expect([...LABEL_KEY_BY_KIND.keys()].sort()).toEqual([...ALL_KINDS].sort());

    // ... and reaches both synthetic verdicts in both directions (R4.3 is not one-sided).
    expect([...REACHED_SYNTHETIC_SOURCED].sort()).toEqual([false, true]);
    expect([...REACHED_SYNTHETIC_UNKNOWN].sort()).toEqual([false, true]);

    // Every kind's label resolves to real copy, and the four resolve to four DISTINCT strings -
    // which is what makes "unknown is rendered distinctly from live" (facet 11) checkable.
    const labels = new Set<string>();
    for (const kind of ALL_KINDS) {
      const labelKey = LABEL_KEY_BY_KIND.get(kind);
      expect(labelKey).toBeDefined();
      labels.add(copy(labelKey ?? ""));
    }
    expect(labels.size).toBe(ALL_KINDS.length);
  });

  // Completeness over the registry: one resolved state, one rendered notice, per declared row.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("every registered data path resolves to one state and renders exactly one notice", () => {
    fc.assert(
      fc.property(idArb, signalsArb, (id, signals) => {
        const state = surfaceDataPath(id, signals);

        // Exactly one kind, drawn from the closed union.
        expect(ALL_KINDS).toContain(state.kind);

        // "Exactly one state" is not a superposition: the absent facts and the present facts
        // are mutually exclusive, and the two synthetic verdicts cannot both hold.
        expect(state.statesNoDataPath).toBe(state.kind === "absent");
        expect(state.endpoint === null).toBe(state.kind === "absent");
        expect(state.scopeKey === null).toBe(state.kind === "absent");
        expect(state.syntheticSourced && state.syntheticUnknown).toBe(false);

        // The "one rendered [data-data-path] per row" contract `data-paths.ts` documents.
        const rendered = renderNotice(state);
        expect(rendered.count).toBe(1);
        expect(rendered.kind).toBe(state.kind);

        // The notice is never wordless: both its label and its detail are real copy, and both
        // reach the operator.
        expect(rendered.text).toContain(copy(state.labelKey));
        expect(rendered.text).toContain(copy(state.detailKey));
      }),
    );
  });

  // R3.5, forward direction: a degraded pipeline response is rendered as degraded.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("a degraded pipeline response renders the declared degraded state on every panel", () => {
    fc.assert(
      fc.property(presentIdArb, triStateArb, (id, synthetic) => {
        const state = surfaceDataPath(id, { degraded: true, synthetic });
        expect(state.kind).toBe("degraded");

        const rendered = renderNotice(state);
        expect(rendered.count).toBe(1);
        expect(rendered.kind).toBe("degraded");

        // The declared degraded copy is on the surface, and the healthy copy is not.
        expect(rendered.text).toContain(copy("datapath.degraded"));
        expect(rendered.text).toContain(copy("datapath.degraded_detail"));
        expect(rendered.text).not.toContain(copy("datapath.live"));
      }),
    );
  });

  // R3.5 + I-7, the TOTAL form: over the whole registry and the whole signal space there is no
  // combination that yields a degraded pipeline but a `live` rendering.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("no signal combination renders a degraded or unproven read as live", () => {
    fc.assert(
      fc.property(idArb, signalsArb, (id, signals) => {
        const rendered = renderNotice(surfaceDataPath(id, signals));
        expect(rendered.count).toBe(1);

        // A live rendering is reachable ONLY from an affirmative "this read was not degraded".
        if (rendered.kind === "live") {
          expect(signals.degraded).toBe(false);
        }

        // Contrapositive, asserted directly so a resolver regression cannot satisfy the
        // implication above by never rendering "live" at all.
        if (signals.degraded === true) {
          expect(rendered.kind).not.toBe("live");
        }
      }),
    );
  });

  // R4.3, over the real registry: an aggregate derived from an `is_synthetic` state is labelled
  // synthetic-sourced on the surface that displays it.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("an is_synthetic-derived aggregate renders data-synthetic-sourced=true", () => {
    fc.assert(
      fc.property(presentIdArb, triStateArb, (id, degraded) => {
        const spec = SURFACE_DATA_PATHS[id];
        // `presentIdArb` draws only registered ids with an endpoint; the narrow keeps
        // `syntheticSource` reachable without a cast or a non-null assertion.
        expect(spec.endpoint).not.toBeNull();
        if (spec.endpoint === null) return;

        const claims = spec.syntheticSource !== "never";
        const state = surfaceDataPath(id, { degraded, synthetic: true });
        const rendered = renderNotice(state);

        expect(rendered.count).toBe(1);
        expect(rendered.syntheticSourced).toBe(claims ? "true" : "false");
        expect(state.syntheticSourced).toBe(claims);

        // The label is prose on the surface, not just an attribute a test can read.
        if (claims) {
          expect(rendered.text).toContain(copy("synthetic.aggregate_label"));
        }
      }),
    );
  });

  // R4.3, quantified over the closed `SyntheticSource` union: "never" is the ONLY value that
  // renders a synthetic state as not-synthetic-sourced.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("never is the only SyntheticSource that renders a synthetic state as false", () => {
    fc.assert(
      fc.property(
        syntheticSourceArb,
        dataClassArb,
        triStateArb,
        (syntheticSource, dataClass, degraded) => {
          const spec: DataPathSpec = { endpoint: "GET /api/v1/probe", dataClass, syntheticSource };
          const rendered = renderNotice(resolveDataPath(spec, { degraded, synthetic: true }));

          expect(rendered.count).toBe(1);
          // Biconditional over the whole union: false <=> "never".
          expect(rendered.syntheticSourced === "false").toBe(syntheticSource === "never");
        },
      ),
    );
  });

  // R3.5 and R4.3 are independent obligations: a degraded synthetic aggregate must render BOTH,
  // on the one element, with no precedence ordering swallowing either.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("a degraded synthetic aggregate renders both states on the single notice element", () => {
    fc.assert(
      fc.property(syntheticSourceArb, dataClassArb, (syntheticSource, dataClass) => {
        const spec: DataPathSpec = { endpoint: "GET /api/v1/probe", dataClass, syntheticSource };
        const rendered = renderNotice(resolveDataPath(spec, { degraded: true, synthetic: true }));

        expect(rendered.count).toBe(1);
        expect(rendered.kind).toBe("degraded");
        expect(rendered.syntheticSourced).toBe(syntheticSource === "never" ? "false" : "true");
        expect(rendered.text).toContain(copy("datapath.degraded"));
      }),
    );
  });

  // R4.3 + I-7, the non-fabrication direction: an unaffirmed `is_synthetic` is never upgraded
  // into a synthetic claim, and when the payload carries no flag at all that absence is
  // DISCLOSED rather than collapsed into `false`.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("an unaffirmed synthetic flag never renders as synthetic-sourced, and null is disclosed", () => {
    fc.assert(
      fc.property(presentIdArb, triStateArb, unaffirmedArb, (id, degraded, synthetic) => {
        const spec = SURFACE_DATA_PATHS[id];
        expect(spec.endpoint).not.toBeNull();
        if (spec.endpoint === null) return;

        const state = surfaceDataPath(id, { degraded, synthetic });
        const rendered = renderNotice(state);

        expect(rendered.count).toBe(1);
        expect(rendered.syntheticSourced).toBe("false");
        expect(state.syntheticSourced).toBe(false);

        // A path that COULD carry the flag but did not must say so - "false" on the attribute
        // must not read as a positive "not synthetic" finding.
        const claims = spec.syntheticSource !== "never";
        expect(state.syntheticUnknown).toBe(claims && synthetic === null);
        if (state.syntheticUnknown) {
          expect(rendered.text).toContain(copy("datapath.synthetic_unknown"));
        }
      }),
    );
  });

  // R13.6: every panel with no data endpoint renders its declared empty state and states that
  // no data path exists - for ANY signals, since there is no read to be degraded about.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("a panel with no data endpoint renders the declared empty state stating no data path", () => {
    fc.assert(
      fc.property(absentIdArb, signalsArb, (id, signals) => {
        const state = surfaceDataPath(id, signals);

        expect(state.kind).toBe("absent");
        expect(state.statesNoDataPath).toBe(true);
        expect(state.endpoint).toBeNull();

        const rendered = renderNotice(state);
        expect(rendered.count).toBe(1);
        expect(rendered.kind).toBe("absent");

        // "The surface states that no data path exists" - the standing label - plus the panel's
        // OWN declared reason, which `DataPathSpec` makes a compile-time obligation.
        expect(rendered.text).toContain(copy("datapath.absent"));
        expect(rendered.text).toContain(copy(state.detailKey));

        // An absent panel makes no health claim and no synthetic claim in either direction.
        expect(rendered.text).not.toContain(copy("datapath.live"));
        expect(rendered.syntheticSourced).toBe("false");
      }),
    );
  });

  // R13.6, the other direction. Without this the facet above would pass on a resolver that
  // rendered everything as absent.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("a panel that has an endpoint never renders as absent, for any signals", () => {
    fc.assert(
      fc.property(presentIdArb, signalsArb, (id, signals) => {
        const state = surfaceDataPath(id, signals);

        expect(state.kind).not.toBe("absent");
        expect(state.statesNoDataPath).toBe(false);
        expect(state.endpoint).not.toBeNull();

        const rendered = renderNotice(state);
        expect(rendered.count).toBe(1);
        expect(rendered.kind).not.toBe("absent");
        expect(rendered.text).not.toContain(copy("datapath.absent"));
      }),
    );
  });

  // I-7: a read that carries no degradation flag, or could not be read at all, resolves to
  // `unknown` and is rendered distinctly. Absence of proof is never rendered as health.
  // Feature: purpose-achievement-audit, Property 31: Degradation is rendered wherever degraded data is shown
  it("a missing degradation signal renders unknown, distinctly from live", () => {
    fc.assert(
      fc.property(presentIdArb, triStateArb, (id, synthetic) => {
        const state = surfaceDataPath(id, { degraded: null, synthetic });
        expect(state.kind).toBe("unknown");

        const rendered = renderNotice(state);
        expect(rendered.count).toBe(1);
        expect(rendered.kind).toBe("unknown");
        expect(rendered.kind).not.toBe("live");

        // Distinct copy, not merely a distinct attribute: the unknown wording is on the
        // surface and the healthy wording is absent.
        expect(rendered.text).toContain(copy("datapath.unknown"));
        expect(rendered.text).toContain(copy("datapath.unknown_detail"));
        expect(rendered.text).not.toContain(copy("datapath.live"));
        expect(rendered.text).not.toContain(copy("datapath.live_detail"));
      }),
    );
  });
});
