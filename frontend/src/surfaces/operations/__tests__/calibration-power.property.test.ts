import { describe, expect, it } from "vitest";
import fc from "fast-check";
import {
  formatMetric,
  hasScoredEvidence,
  isProvisional,
  NO_VALUE_MARKER,
  PROVISIONAL_THRESHOLD,
} from "../logic";

// Feature: atlas-console-elevation
// Property 15: Calibration discloses statistical power and never renders null as zero
//
// `isProvisional(n)` is true iff the scored-outcome count is below the
// statistical-power floor (30). `formatMetric` renders a null/absent metric as
// the explicit no-value marker "—" (never "0"), while a real numeric value —
// INCLUDING 0 — is formatted to fixed decimals ("0.000" / "0").
//
// **Validates: Requirements 4.4, 4.6**

const NUMERIC_3DP = /^-?\d+\.\d{3}$/;

describe("Property 15: statistical power disclosure and null-vs-zero honesty", () => {
  it("flags provisional iff scored outcomes are below the power floor (30)", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 500 }), (n) => {
        expect(isProvisional(n)).toBe(n < PROVISIONAL_THRESHOLD);
      }),
      { numRuns: 200 },
    );
  });

  it("treats a null / undefined / non-finite count as provisional (never a strong sample)", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<number | null | undefined>(
          null,
          undefined,
          Number.NaN,
          Number.POSITIVE_INFINITY,
          Number.NEGATIVE_INFINITY,
        ),
        (bad) => {
          expect(isProvisional(bad)).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("renders a null / undefined / non-finite metric as the no-value marker, never a number", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<number | null | undefined>(
          null,
          undefined,
          Number.NaN,
          Number.POSITIVE_INFINITY,
          Number.NEGATIVE_INFINITY,
        ),
        fc.integer({ min: 0, max: 6 }),
        (bad, digits) => {
          expect(formatMetric(bad, digits)).toBe(NO_VALUE_MARKER);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("renders a real numeric value (including 0) as a fixed-decimal number, never the marker", () => {
    fc.assert(
      fc.property(fc.double({ min: -1000, max: 1000, noNaN: true }), (value) => {
        const out = formatMetric(value);
        expect(out).not.toBe(NO_VALUE_MARKER);
        expect(out).toMatch(NUMERIC_3DP);
        expect(out).toBe(value.toFixed(3));
      }),
      { numRuns: 300 },
    );
  });

  it("renders measured zero honestly as '0.000' (default) / '0' (0 digits), never '—'", () => {
    expect(formatMetric(0)).toBe("0.000");
    expect(formatMetric(0, 0)).toBe("0");
    expect(formatMetric(0)).not.toBe(NO_VALUE_MARKER);
  });

  it("reports scored evidence iff a positive finite count backs the metric", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 500 }), (n) => {
        expect(hasScoredEvidence(n)).toBe(n > 0);
      }),
      { numRuns: 200 },
    );
  });

  it("treats a null / undefined / non-finite count as having no scored evidence", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<number | null | undefined>(
          null,
          undefined,
          Number.NaN,
          Number.POSITIVE_INFINITY,
          Number.NEGATIVE_INFINITY,
        ),
        (bad) => {
          expect(hasScoredEvidence(bad)).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });
});
