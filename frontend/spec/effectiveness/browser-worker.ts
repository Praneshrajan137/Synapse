/**
 * Effectiveness_Harness — MSW browser worker (Req 1.1, 1.4, 1.5, 1.6).
 *
 * This is the keystone of the Effectiveness_Harness: Mock Service Worker running
 * as a *browser* service worker inside the Playwright-controlled browser. It
 * intercepts every Backend_Contract HTTP request the Atlas_Console issues and
 * answers it from a seeded, schema-bound fixture, so end-to-end tests prove the
 * Console behaves correctly *against data* rather than only that routes render
 * (design "B. Harness — MSW browser worker + stream driver").
 *
 * Composition rules (from the design):
 *   • **Reuse and extend, never duplicate.** The worker is built from the
 *     existing `src/test/msw-handlers.ts` `handlers` array plus the full
 *     schema-bound effectiveness handler set (`./handlers.ts`). The
 *     effectiveness handlers are registered FIRST so their populated fixtures
 *     supersede the base empty/minimal ones (MSW first-match-wins), while the
 *     base `/health`, `/ready`, and `/api/v1/agents` handlers are reused as-is.
 *   • **Never patch app code.** The worker intercepts `fetch` at the network
 *     boundary exactly where `transport/http-client` issues requests; the app
 *     runs unmodified.
 *   • **Zero live calls (Req 1.5).** Every Backend_Contract HTTP path is
 *     intercepted; same-origin static assets (the app's own bundle) pass
 *     through to the preview server, which is not a live/third-party endpoint.
 *   • **No silent gaps (Req 1.6).** A Backend_Contract request with no
 *     registered fixture fails the test naming the unhandled path via
 *     {@link UnhandledFixtureError}, rather than returning an empty/default body.
 *
 * The scripted WebSocket/SSE streams for real-time channels are the stream
 * driver's responsibility (`./stream-driver.ts`, task 2.2); this module owns the
 * HTTP surface only.
 */

import { setupWorker, type SetupWorker } from "msw/browser";

import { handlers as baseHandlers } from "@test/msw-handlers";

import {
  ALL_SURFACES,
  buildEffectivenessHandlers,
  isBackendContractPath,
  uncoveredSurfaces,
} from "./handlers";
import type { HarnessOptions } from "./scenarios/types";

export type { HarnessOptions };

// ─────────────────────────────────────────────────────────────────────────
// UnhandledFixtureError (Req 1.6)
// ─────────────────────────────────────────────────────────────────────────

/**
 * Thrown/recorded when a harness-mode request hits a Backend_Contract path for
 * which no MSW_Fixture is registered. Names the offending path and method so
 * the failure is actionable, rather than the Console silently receiving an
 * empty or default response (Req 1.6).
 */
export class UnhandledFixtureError extends Error {
  constructor(
    readonly path: string,
    readonly method: string,
  ) {
    super(
      `Effectiveness_Harness: no MSW_Fixture registered for Backend_Contract request ${method} ${path}. ` +
        `Register a handler in spec/effectiveness/handlers.ts (or drive it via the stream driver) — ` +
        `the harness never returns an empty/default response for an unhandled contract path (Req 1.6).`,
    );
    this.name = "UnhandledFixtureError";
  }
}

// ─────────────────────────────────────────────────────────────────────────
// HarnessHandle (design "B")
// ─────────────────────────────────────────────────────────────────────────

/** A running harness instance; returned by {@link startHarness}. */
export interface HarnessHandle {
  /** The seed this harness was started with (Req 1.3). */
  readonly seed: number;
  /** Stop the worker and release the service-worker registration. */
  stop(): Promise<void>;
  /** Names of every intercepted path served so far, for the coverage report (Req 1.4). */
  servedPaths(): readonly string[];
  /**
   * Backend_Contract paths that were requested with no registered fixture
   * (Req 1.6). Non-empty ⇒ the harness detected a contract gap; a
   * Task_Completion_Test asserts this stays empty.
   */
  unhandledPaths(): readonly string[];
}

// ─────────────────────────────────────────────────────────────────────────
// startHarness (Req 1.1)
// ─────────────────────────────────────────────────────────────────────────

/**
 * Start the MSW browser worker for a seeded scenario. Resolves once the service
 * worker is active and intercepting. The returned {@link HarnessHandle} exposes
 * the served/unhandled paths for the coverage report and stops the worker on
 * teardown.
 *
 * A malformed surface map (a Surface with no seeded capability) fails fast here
 * rather than surfacing as an opaque e2e failure (Req 1.4).
 */
export async function startHarness(opts: HarnessOptions): Promise<HarnessHandle> {
  assertFullSurfaceCoverage();

  const served = new Set<string>();
  const unhandled = new Set<string>();

  const worker: SetupWorker = setupWorker(
    ...buildEffectivenessHandlers(opts.seed),
    ...baseHandlers,
  );

  // Record every matched request path for the Req 1.4 coverage report.
  worker.events.on("request:match", ({ request }) => {
    served.add(pathnameOf(request.url));
  });

  await worker.start({
    // Bind the worker script emitted by `msw init public` (public/mockServiceWorker.js).
    serviceWorker: { url: "/mockServiceWorker.js" },
    // Keep the console quiet for handled requests; unhandled ones are surfaced
    // by the guard below.
    quiet: true,
    onUnhandledRequest: (request, print) => {
      const path = pathnameOf(request.url);
      if (!isBackendContractPath(path)) {
        // Same-origin static asset or a stream endpoint owned by the stream
        // driver — allow it through (Req 1.5: not a live/third-party endpoint).
        return;
      }
      // A Backend_Contract path with no fixture: fail loudly naming the path
      // (Req 1.6). Record it for `unhandledPaths()` and raise so the request
      // rejects rather than silently resolving to a default body.
      unhandled.add(path);
      print.error();
      throw new UnhandledFixtureError(path, request.method);
    },
  });

  return {
    seed: opts.seed,
    servedPaths: () => Array.from(served).sort(),
    unhandledPaths: () => Array.from(unhandled).sort(),
    stop: async () => {
      worker.stop();
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────

/** Extract the pathname from a request URL, tolerating a relative or absolute URL. */
function pathnameOf(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    // Already a bare path (defensive — MSW gives absolute URLs).
    const q = url.indexOf("?");
    return q === -1 ? url : url.slice(0, q);
  }
}

/**
 * Assert every Surface in the Req 1.4 surface list has at least one seeded
 * capability. Throws (fail-fast) naming any uncovered Surface.
 */
function assertFullSurfaceCoverage(): void {
  const uncovered = uncoveredSurfaces();
  if (uncovered.length > 0) {
    throw new Error(
      `Effectiveness_Harness surface coverage gap (Req 1.4): no seeded fixture reaches the ` +
        `populated Universal_State for surface(s): ${uncovered.join(", ")}. ` +
        `Every Surface in [${ALL_SURFACES.join(", ")}] must be covered.`,
    );
  }
}
