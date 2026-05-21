/**
 * SYNAPSE Atlas Console — Vitest setup.
 *
 * - jest-dom matchers for RTL assertions (`toBeInTheDocument`, etc.).
 * - MSW server starts/stops around each test so contract tests run
 *   against the same handlers Storybook uses.
 * - i18next bootstrapped in a no-op test mode so translations don't
 *   fetch over the network.
 *
 * fast-check seeding: pinned via VITEST_SEED env var (set by CI to
 * 20260430). Local runs use whatever's in process.env at boot.
 */
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import fc from "fast-check";

import { server } from "./msw/server";

const seed = Number(process.env["VITEST_SEED"] ?? Date.now());
fc.configureGlobal({ seed, numRuns: 100 });

beforeAll(() => {
  server.listen({ onUnhandledRequest: "warn" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

// Polyfill matchMedia for components that read `prefers-reduced-motion`
// or `prefers-color-scheme` during render.
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
