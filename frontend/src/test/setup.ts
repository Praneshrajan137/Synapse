import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, expect } from "vitest";
// Registers the `toHaveNoViolations` axe matcher (+ its `declare module "vitest"`
// types) for the a11y test layer (SENSORIUM accessibility rigor — WCAG 2.1 AA /
// INV-CLR-011). The bare extend-expect import is a no-op under Vitest globals,
// so we extend the imported `expect` explicitly.
import { axeMatchers } from "vitest-axe";
import { server } from "./msw-server";

expect.extend(axeMatchers);

// Start MSW for every test; reset handlers between tests.
beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
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
