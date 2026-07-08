/**
 * Feature: atlas-console-effectiveness, Property 4: A Backend_Contract request
 * with no registered fixture fails the test and names the unhandled path, never
 * returning an empty/default response
 *
 * Validates: Requirements 1.6
 *
 * Property-based verification of the Effectiveness_Harness unhandled-path guard
 * (design "B. Harness — MSW browser worker + stream driver"; Requirement 1.6).
 * The browser worker's `onUnhandledRequest` guard classifies every intercepted
 * path with {@link isBackendContractPath} and, for a Backend_Contract path with
 * no registered fixture, throws an {@link UnhandledFixtureError} that NAMES the
 * offending path — so the request rejects rather than the Console silently
 * receiving an empty or default body.
 *
 * Rather than booting a service worker (unavailable under jsdom), this test
 * exercises the two pure pieces the guard is built from — the contract-path
 * classifier and the error constructor — over the real `EFFECTIVENESS_HANDLER_SPECS`
 * so the property holds against the shipped handler set. Facets, each `numRuns: 100`:
 *
 *   1. Any Backend_Contract path NOT covered by a registered handler is
 *      classified as needing a fixture (`isBackendContractPath === true`) AND
 *      constructing an `UnhandledFixtureError` for it names that exact path
 *      (`error.path === path`, `error.message` contains the path) — never a
 *      silent empty/default response (Req 1.6).
 *   2. A same-origin static asset path is NOT classified as a contract path
 *      (`isBackendContractPath === false`), so the guard lets it pass through
 *      to the preview server rather than demanding a fixture (Req 1.5/1.6).
 *   3. The scripted-stream endpoints (demo SSE, WebSocket firehose) owned by the
 *      stream driver are likewise NOT classified as HTTP contract paths, so the
 *      HTTP guard never falsely flags them as unhandled fixtures.
 */

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { UnhandledFixtureError } from "../browser-worker";
import { EFFECTIVENESS_HANDLER_SPECS, isBackendContractPath } from "../handlers";

// ─────────────────────────────────────────────────────────────────────────
// Coverage oracle — a path is "covered" iff a registered fixture serves it.
// Registered fixtures = the effectiveness handler specs plus the base
// `src/test/msw-handlers.ts` handlers reused by the worker (/health, /ready,
// /api/v1/agents, /api/v1/decisions/recent).
// ─────────────────────────────────────────────────────────────────────────

function isCoveredByHandler(path: string): boolean {
  if (/\/health$/.test(path)) return true;
  if (/\/ready$/.test(path)) return true;
  if (/\/api\/v1\/agents$/.test(path)) return true;
  if (/\/api\/v1\/decisions\/recent/.test(path)) return true;
  return EFFECTIVENESS_HANDLER_SPECS.some((spec) => spec.pattern.test(path));
}

// ─────────────────────────────────────────────────────────────────────────
// Generators
// ─────────────────────────────────────────────────────────────────────────

/** A non-empty lowercase-alphanumeric path segment (URL-safe, no separators). */
const tokenArb = fc
  .array(fc.constantFrom(..."abcdefghijklmnopqrstuvwxyz0123456789".split("")), {
    minLength: 1,
    maxLength: 10,
  })
  .map((chars) => chars.join(""));

/**
 * A Backend_Contract HTTP path (`/api/...`) that is NOT covered by any
 * registered fixture — the exact input space Req 1.6 governs.
 */
const unhandledContractPathArb = fc
  .array(tokenArb, { minLength: 1, maxLength: 4 })
  .map((segments) => `/api/${segments.join("/")}`)
  .filter((path) => isBackendContractPath(path) && !isCoveredByHandler(path));

/** HTTP methods the Console may issue. */
const methodArb = fc.constantFrom("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD");

/** A same-origin static asset path the worker must pass through, never flag. */
const staticAssetArb = fc.oneof(
  fc.constantFrom(
    "/index.html",
    "/favicon.ico",
    "/mockServiceWorker.js",
    "/manifest.webmanifest",
    "/robots.txt",
    "/logo.png",
  ),
  tokenArb.map((t) => `/assets/${t}.js`),
  tokenArb.map((t) => `/assets/${t}.css`),
  tokenArb.map((t) => `/fonts/${t}.woff2`),
  tokenArb.map((t) => `/${t}.svg`),
);

/** Scripted-stream endpoints owned by the stream driver (not HTTP fixtures). */
const streamEndpointArb = fc.oneof(
  tokenArb.map((t) => `/api/v1/demo/${t}/stream`),
  tokenArb.map((t) => `/ws/${t}`),
);

// ─────────────────────────────────────────────────────────────────────────
// Property 4
// ─────────────────────────────────────────────────────────────────────────

describe("Property 4: unhandled-path failure names the path, never a default response", () => {
  it("guards the generated contract paths are genuinely uncovered (non-empty input space)", () => {
    const sample = fc.sample(unhandledContractPathArb, 20);
    expect(sample.length).toBeGreaterThan(0);
    for (const path of sample) {
      expect(isBackendContractPath(path)).toBe(true);
      expect(isCoveredByHandler(path)).toBe(false);
    }
  });

  // Req 1.6: an uncovered Backend_Contract request is classified as needing a
  // fixture AND the raised error names the exact unhandled path.
  it("classifies an uncovered contract path as needing a fixture and names it in the error", () => {
    fc.assert(
      fc.property(unhandledContractPathArb, methodArb, (path, method) => {
        // The guard's classifier flags it as a Backend_Contract path (Req 1.6).
        expect(isBackendContractPath(path)).toBe(true);

        // The guard raises an UnhandledFixtureError that names the path/method
        // rather than resolving to an empty/default body (Req 1.6).
        const error = new UnhandledFixtureError(path, method);
        expect(error).toBeInstanceOf(UnhandledFixtureError);
        expect(error).toBeInstanceOf(Error);
        expect(error.name).toBe("UnhandledFixtureError");
        expect(error.path).toBe(path);
        expect(error.method).toBe(method);
        // The path (and method) are surfaced in the message so the failure is
        // actionable — the harness never silently swallows the gap.
        expect(error.message).toContain(path);
        expect(error.message).toContain(method);
        // It is an explicit failure signal, not an empty/default response.
        expect(error.message.length).toBeGreaterThan(path.length);
      }),
      { numRuns: 100 },
    );
  });

  // Req 1.5/1.6: a same-origin static asset is NOT a contract path, so the
  // guard passes it through instead of demanding a fixture.
  it("never classifies a same-origin static asset as a Backend_Contract path", () => {
    fc.assert(
      fc.property(staticAssetArb, (assetPath) => {
        expect(isBackendContractPath(assetPath)).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  // Req 1.6: the stream-driver endpoints (demo SSE, WebSocket firehose) are not
  // HTTP fixtures, so the HTTP guard must not flag them as unhandled paths.
  it("never classifies a scripted-stream endpoint as an HTTP Backend_Contract path", () => {
    fc.assert(
      fc.property(streamEndpointArb, (streamPath) => {
        expect(isBackendContractPath(streamPath)).toBe(false);
      }),
      { numRuns: 100 },
    );
  });
});
