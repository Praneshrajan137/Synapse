import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, expect, vi } from "vitest";
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

// Inert global WebSocket for jsdom (CI crash-class guard).
//
// Any component that mounts `useFirehose` opens `new WebSocket(...)`. Without a
// stub, MSW intercepts a real socket and the half-open stream is destroyed on
// teardown — aborting the vitest worker with a native libuv assertion
// (uv__stream_destroy) on CI. This inert socket never opens, sends nothing, and
// closes cleanly, so no native stream ever exists. Installed per-test so the
// transport firehose test (which stubs its own MockWebSocket + unstubs after
// each) stays compatible. Tests that need socket behaviour stub their own.
class InertWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  readyState = InertWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(readonly url: string) {}
  send(_data: string): void {}
  close(): void {
    this.readyState = InertWebSocket.CLOSED;
    this.onclose?.();
  }
  addEventListener(): void {}
  removeEventListener(): void {}
}

// Start MSW for every test; reset handlers between tests.
beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
beforeEach(() => {
  // After MSW's beforeAll listen() patches the global, override with the inert
  // socket so live WS connections are never opened in jsdom.
  vi.stubGlobal("WebSocket", InertWebSocket);
});
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

// jsdom does not implement ResizeObserver (Radix Slider thumb sizing, Sigma).
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver;
}
