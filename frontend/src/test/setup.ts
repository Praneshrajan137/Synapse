/**
 * Vitest global setup.
 *
 * Extends `expect` with jest-dom and jest-axe matchers, runs the MSW
 * mock server for the whole suite, polyfills the browser APIs jsdom
 * omits, and tears down the DOM between tests.
 */

import "@testing-library/jest-dom/vitest";
import { server } from "@/mocks/server";
import { cleanup } from "@testing-library/react";
import { toHaveNoViolations } from "jest-axe";
import { afterAll, afterEach, beforeAll, expect } from "vitest";

expect.extend(toHaveNoViolations);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

// jsdom does not implement matchMedia — the motion tokens and several
// components query it for prefers-reduced-motion.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// jsdom lacks ResizeObserver — needed by charts and virtualized lists.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom does not implement scrollIntoView — used by the append-only tapes.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
