import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, expect } from "vitest";
import { server } from "./msw-server";

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
