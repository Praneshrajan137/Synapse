// Feature: atlas-console-elevation, Property 42: Every metric query key carries the active city
//
// Property 42 (Validates: Requirements 13.4) — for ANY metric query descriptor
// and ANY active city, the key built by `metricQueryKey`:
//   • embeds the active city as a dedicated discriminator at index 1, so
//   • two otherwise-identical descriptors under DIFFERENT cities always produce
//     structurally-different keys (switching cities invalidates stale data),
//   • preserves the scope at index 0, and
//   • normalizes params by dropping `undefined` entries.

import { ZCity } from "@domain/primitives";
import type { City } from "@domain/primitives";
import { metricQueryKey } from "@lib/query-keys";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const CITIES = ZCity.options as readonly City[];
const cityArb: fc.Arbitrary<City> = fc.constantFrom(...CITIES);
const scopeArb: fc.Arbitrary<string> = fc.string({ minLength: 1, maxLength: 24 });

// Params may include `undefined` values (an omitted optional) that must be
// dropped so they never fork the cache key.
const paramsArb: fc.Arbitrary<Record<string, unknown>> = fc.dictionary(
  fc.string({ minLength: 1, maxLength: 10 }),
  fc.oneof(fc.integer(), fc.string(), fc.boolean(), fc.constant(undefined)),
  { maxKeys: 6 },
);

describe("metricQueryKey — Property 42: every metric query key carries the active city", () => {
  it("embeds the active city as the index-1 discriminator, ahead of params", () => {
    fc.assert(
      fc.property(scopeArb, cityArb, paramsArb, (scope, city, params) => {
        const key = metricQueryKey(scope, city, params);
        expect(key[0]).toBe(scope);
        expect(key[1]).toBe(city);
        // The city sits at a fixed position; params are the third element.
        expect(key.length).toBe(3);
      }),
      { numRuns: 200 },
    );
  });

  it("produces structurally-distinct keys when the city differs (clean invalidation)", () => {
    const distinctCitiesArb = fc
      .tuple(cityArb, cityArb)
      .filter(([a, b]) => a !== b) as fc.Arbitrary<[City, City]>;

    fc.assert(
      fc.property(scopeArb, distinctCitiesArb, paramsArb, (scope, [cityA, cityB], params) => {
        const keyA = metricQueryKey(scope, cityA, params);
        const keyB = metricQueryKey(scope, cityB, params);
        // React Query compares keys structurally (JSON-equality); a differing
        // city MUST change the serialized key so stale city data is dropped.
        expect(JSON.stringify(keyA)).not.toBe(JSON.stringify(keyB));
        expect(keyA[1]).not.toBe(keyB[1]);
      }),
      { numRuns: 200 },
    );
  });

  it("drops `undefined` params without disturbing the city discriminator", () => {
    fc.assert(
      fc.property(scopeArb, cityArb, paramsArb, (scope, city, params) => {
        const [, keyCity, normalized] = metricQueryKey(scope, city, params);
        expect(keyCity).toBe(city);
        for (const value of Object.values(normalized)) {
          expect(value).not.toBeUndefined();
        }
        // Every defined input param survives normalization unchanged.
        for (const [k, v] of Object.entries(params)) {
          if (v !== undefined) expect(normalized[k]).toBe(v);
          else expect(Object.hasOwn(normalized, k)).toBe(false);
        }
      }),
      { numRuns: 200 },
    );
  });
});
