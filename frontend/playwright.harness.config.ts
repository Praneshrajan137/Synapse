import { defineConfig, devices } from "@playwright/test";

import { HARNESS_SPEC_PATTERN } from "./playwright.config";

/**
 * Playwright config for the Effectiveness_Harness suite (task 11.1, AD-12).
 *
 * The six harness-dependent specs drive `window.__atlasHarness`, which exists
 * only in the `e2e`-mode build. That build writes to `dist-e2e/` and is served
 * by `pnpm preview:e2e`, so this config -- not `playwright.config.ts` -- is the
 * one that can honestly run them:
 *
 *     pnpm build:e2e && pnpm test:e2e:harness
 *
 * The run record lands at `artifacts/test-reports/playwright-harness.json`,
 * which is exactly the path `frontend/spec/check_fe_invariants.py` already reads
 * for the FE-INV attestation (and which `.github/workflows/frontend.yml`'s
 * `fe-invariants` job already downloads as `fe-invariant-playwright-*-report`).
 * A run that produces no record is `unavailable` to that gate, never a pass
 * (I-7).
 *
 * Chromium only, on purpose: the harness installs a service worker plus
 * `WebSocket`/`EventSource`/`fetch` doubles, and the measurement is a
 * Scripted_Proxy on one deterministic engine. Cross-engine rendering is the
 * default suite's job.
 */

const isCi = !!process.env.CI;
const baseUrlOverride = process.env.PLAYWRIGHT_BASE_URL;
const jsonReport =
  process.env.PLAYWRIGHT_JSON_OUTPUT_NAME ?? "artifacts/test-reports/playwright-harness.json";

export default defineConfig({
  testDir: "./tests/e2e",
  // Only the harness specs, and never the visual baselines.
  testMatch: HARNESS_SPEC_PATTERN,
  // The JTBD suite emits one scorecard per run and the resilience specs drive
  // shared in-page transport doubles, so the harness suite runs serially.
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCi,
  retries: 0,
  reporter: isCi
    ? [
        ["html", { open: "never" }],
        ["github"],
        ["json", { outputFile: jsonReport }],
      ]
    : [["list"], ["json", { outputFile: jsonReport }]],
  // The harness streams an adversarial burst and drives multi-step operator
  // paths, so a driven test needs more than the default 30s.
  timeout: 120_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: baseUrlOverride ?? "http://localhost:3001",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Serve the harness build (`dist-e2e/`), not the shipped bundle.
  ...(baseUrlOverride
    ? {}
    : {
        webServer: {
          command: "pnpm preview:e2e",
          url: "http://localhost:3001",
          reuseExistingServer: !isCi,
          timeout: 60_000,
        },
      }),
});
