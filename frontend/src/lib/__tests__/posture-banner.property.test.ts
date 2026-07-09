import type { SystemPosture } from "@transport/synapse-api";
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { derivePostureBanner } from "../posture-banner";

// Feature: atlas-console-elevation
// Property 32: Degraded posture is honest and never false-healthy
//
// `derivePostureBanner` names what is degraded whenever a brownout is shedding
// or a breaker is open, and a posture-fetch failure (or absent posture) derives
// "unknown" — never "healthy". The banner never fails silently green.
//
// **Validates: Requirements 10.5**

const arbBrownoutLevel = fc.constantFrom("NONE", "LOW", "MEDIUM", "HIGH");
const arbBreakerState = fc.constantFrom("closed", "open", "half_open");

const arbPosture: fc.Arbitrary<SystemPosture> = fc
  .record({
    brownout: fc.dictionary(fc.string({ minLength: 1, maxLength: 6 }), arbBrownoutLevel, {
      maxKeys: 6,
    }),
    breakers: fc.dictionary(fc.string({ minLength: 1, maxLength: 6 }), arbBreakerState, {
      maxKeys: 6,
    }),
    degraded: fc.boolean(),
  })
  .map((p) => p as SystemPosture);

describe("Property 32: degraded posture is honest and never false-healthy", () => {
  it("derives 'unknown' (never 'healthy') on a posture-fetch failure", () => {
    fc.assert(
      fc.property(fc.option(arbPosture, { nil: undefined }), (data) => {
        const banner = derivePostureBanner({ isError: true, data });
        expect(banner.kind).toBe("unknown");
        expect(banner.kind).not.toBe("healthy");
        expect(banner.brownout).toEqual([]);
        expect(banner.openBreakers).toEqual([]);
      }),
      { numRuns: 200 },
    );
  });

  it("derives 'unknown' (never 'healthy') when no posture is available", () => {
    const banner = derivePostureBanner({ isError: false, data: undefined });
    expect(banner.kind).toBe("unknown");
    expect(banner.kind).not.toBe("healthy");
  });

  it("names every shedding brownout and open breaker, and is 'degraded' when any exists", () => {
    fc.assert(
      fc.property(arbPosture, (data) => {
        const banner = derivePostureBanner({ isError: false, data });

        const expectedBrownout = Object.entries(data.brownout).filter(([, l]) => l !== "NONE");
        const expectedBreakers = Object.entries(data.breakers).filter(([, s]) => s !== "closed");

        // The banner names exactly the degraded elements.
        expect(new Set(banner.brownout.map(([c]) => c))).toEqual(
          new Set(expectedBrownout.map(([c]) => c)),
        );
        expect(new Set(banner.openBreakers.map(([n]) => n))).toEqual(
          new Set(expectedBreakers.map(([n]) => n)),
        );

        const hasNamedDegradation = expectedBrownout.length > 0 || expectedBreakers.length > 0;
        if (hasNamedDegradation || data.degraded) {
          // Any named degradation or the aggregate flag must drive "degraded".
          expect(banner.kind).toBe("degraded");
          expect(banner.kind).not.toBe("healthy");
        } else {
          // Only a fully-quiet, affirmative posture is healthy.
          expect(banner.kind).toBe("healthy");
        }
      }),
      { numRuns: 300 },
    );
  });

  it("is never 'healthy' while a named degradation is present", () => {
    fc.assert(
      fc.property(arbPosture, (data) => {
        const banner = derivePostureBanner({ isError: false, data });
        const hasNamedDegradation = banner.brownout.length > 0 || banner.openBreakers.length > 0;
        if (hasNamedDegradation) {
          expect(banner.kind).toBe("degraded");
        }
      }),
      { numRuns: 200 },
    );
  });
});
