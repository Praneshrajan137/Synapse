import { type Worker as PageWorker, expect, test } from "@playwright/test";

/**
 * The basemap's tile worker boots from the asset the production build emitted.
 *
 * maplibre-gl v6 is ESM-only and cannot find its own worker inside a bundler's
 * module graph, so `src/visualization/maplibre/basemap.ts` hands it the URL that
 * Vite's `?worker&url` pipeline emits. If that wiring breaks, nothing fails
 * loudly: the map container, its controls and the deck.gl overlay all mount,
 * but the worker that decodes every vector tile never starts, so the basemap
 * stays empty. No other check in CI can see that; this spec can.
 *
 * Deterministic under `pnpm preview` with no backend and no tiles: the API
 * calls, the firehose socket and the PMTiles fetch all fail here, and nothing
 * below depends on them. Only the worker is asserted on.
 *
 * Kept free of the app's `@`-alias module graph, like the other e2e specs.
 */

/** Vite's worker pipeline emits the worker entry as `assets/[name]-[hash].js`. */
const WORKER_ASSET = /\/assets\/maplibre-gl-worker-[\w-]+\.m?js$/;

/**
 * Text that means the worker did not start, matched case-insensitively against
 * page console text and source, and against page-error messages and stacks.
 */
const WORKER_FAILURE_SIGNATURES: readonly string[] = [
  // Any error whose text, source or stack names the worker script.
  "maplibre-gl-worker",
  // The browser refused to construct the Worker (bad URL, CSP).
  "failed to construct 'worker'",
  // The module worker's script was not JavaScript (e.g. an HTML fallback page).
  "failed to load module script",
  // maplibre: a cross-origin worker script could not be fetched.
  "failed to fetch worker script",
  // maplibre: the module worker was rejected and it fell back to a classic one.
  "module worker not supported",
];

function namesWorkerFailure(text: string): boolean {
  const lower = text.toLowerCase();
  return WORKER_FAILURE_SIGNATURES.some((signature) => lower.includes(signature));
}

test("the basemap's tile worker boots from the bundled worker asset", async ({ page }) => {
  const workers: PageWorker[] = [];
  const failures: string[] = [];
  page.on("console", (message) => {
    // Playwright 1.60 also delivers a web worker's own console messages here (their
    // `page()` is non-null). Those are judged once, by the worker's listener below.
    if (message.worker() !== null) return;
    const kind = message.type();
    const text = `${message.text()} (${message.location().url})`;
    if ((kind === "error" || kind === "warning") && namesWorkerFailure(text)) {
      failures.push(`console.${kind}: ${text}`);
    }
  });
  page.on("worker", (worker) => {
    workers.push(worker);
    // Anything a worker itself reports as an error is a worker failure.
    worker.on("console", (message) => {
      if (message.type() === "error") {
        failures.push(`worker console.error (${worker.url()}): ${message.text()}`);
      }
    });
  });
  page.on("pageerror", (error) => {
    if (namesWorkerFailure(`${error.message}\n${error.stack ?? ""}`)) {
      failures.push(`pageerror: ${error.message}`);
    }
  });

  // Seed an authenticated session so RouteGuard passes (mirrors mobile-reality.spec.ts).
  await page.addInitScript(() => {
    sessionStorage.setItem(
      "synapse.session",
      JSON.stringify({
        state: { role: "admin", operatorTokenRef: "e2e-operator" },
        version: 0,
      }),
    );
  });

  await page.goto("/");
  // The map container mounts only once the lazily loaded canvas chunk has arrived. The
  // three step bounds (15 + 8 + 5 s) sum inside the 30 s test timeout, so a slow step
  // fails with its own message rather than a generic timeout.
  await expect(
    page.getByRole("img", { name: /live map$/ }),
    "the living map never mounted (canvas chunk failed, or no WebGL2 for maplibre-gl v6)",
  ).toBeVisible({ timeout: 15_000 });

  // 1. A dedicated Worker was started from the hashed worker asset ...
  await expect
    .poll(() => workers.map((worker) => worker.url()), {
      message: "no dedicated Worker was started from the bundled maplibre-gl worker asset",
      timeout: 8_000,
    })
    .toContainEqual(expect.stringMatching(WORKER_ASSET));
  const tileWorker = workers.find((worker) => WORKER_ASSET.test(worker.url()));
  if (tileWorker === undefined) {
    throw new Error("the worker the poll above matched is no longer in the list");
  }

  // 2. ... the asset is served, as JavaScript ...
  const script = await page.request.get(tileWorker.url());
  expect(script.ok(), `GET ${tileWorker.url()} answered ${script.status()}`).toBe(true);
  // `pnpm preview` answers an unknown path with index.html and a 200 (SPA
  // fallback), so the status alone cannot tell a real asset from a missing one.
  expect(script.headers()["content-type"] ?? "").toMatch(/javascript/);

  // 3. ... and maplibre's worker runtime booted inside it: the worker entry's
  // last statement assigns that runtime to `self.worker`.
  await expect
    .poll(() => tileWorker.evaluate(() => ("worker" in self ? typeof self.worker : "undefined")), {
      message: "the worker script loaded but maplibre's worker runtime never started",
      timeout: 5_000,
    })
    .toBe("object");

  // 4. ... with no worker failure reported anywhere on the page.
  expect(failures).toEqual([]);
});
