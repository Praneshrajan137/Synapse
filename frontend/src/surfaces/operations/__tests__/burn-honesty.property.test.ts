import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { burnSeverityWord, deriveBurnSeverity, type BurnSeverityInput } from "../logic";
import type { SloSeverity } from "@domain/operations";

// Feature: atlas-console-elevation
// Property 34: SLO burn is honest and never false-healthy
//
// `deriveBurnSeverity` + `burnSeverityWord` always render a severity word for a
// tier's burn gauge, and an unknown metrics source or a null window collapses
// to "unknown" / "burn unknown" — never "healthy" and never a fabricated 0.
//
// **Validates: Requirements 10.9**

const ALL_SEVERITIES: readonly SloSeverity[] = ["ok", "warning", "critical", "unknown"];
const arbSeverity = fc.constantFrom(...ALL_SEVERITIES);
const arbWindow = fc.option(fc.double({ min: 0, max: 100, noNaN: true }), { nil: null });

const arbInput: fc.Arbitrary<BurnSeverityInput> = fc.record({
  fast: arbWindow,
  slow: arbWindow,
  reported: arbSeverity,
  sourceUnknown: fc.boolean(),
});

describe("Property 34: SLO burn is honest and never false-healthy", () => {
  it("always renders a non-empty severity word for every possible severity", () => {
    fc.assert(
      fc.property(arbSeverity, (sev) => {
        const word = burnSeverityWord(sev);
        expect(typeof word).toBe("string");
        expect(word.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 },
    );
  });

  it("collapses an unknown source or any null window to 'unknown' / 'burn unknown'", () => {
    fc.assert(
      fc.property(arbInput, (i) => {
        if (i.sourceUnknown || i.fast === null || i.slow === null) {
          const sev = deriveBurnSeverity(i);
          expect(sev).toBe("unknown");
          const word = burnSeverityWord(sev);
          expect(word).toBe("burn unknown");
          // Never false-healthy, never a fabricated healthy word.
          expect(word).not.toBe("healthy");
        }
      }),
      { numRuns: 400 },
    );
  });

  it("only trusts the reported severity when the source is reachable and both windows carry evidence", () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0, max: 100, noNaN: true }),
        fc.double({ min: 0, max: 100, noNaN: true }),
        arbSeverity,
        (fast, slow, reported) => {
          const sev = deriveBurnSeverity({ fast, slow, reported, sourceUnknown: false });
          expect(sev).toBe(reported);
        },
      ),
      { numRuns: 300 },
    );
  });

  it("never reports 'healthy' unless the source is honestly reachable with both windows present", () => {
    fc.assert(
      fc.property(arbInput, (i) => {
        const word = burnSeverityWord(deriveBurnSeverity(i));
        if (word === "healthy") {
          // A healthy word is only permissible with a reachable source, both
          // windows present, and an affirmatively-ok reported severity.
          expect(i.sourceUnknown).toBe(false);
          expect(i.fast).not.toBeNull();
          expect(i.slow).not.toBeNull();
          expect(i.reported).toBe("ok");
        }
      }),
      { numRuns: 400 },
    );
  });
});
