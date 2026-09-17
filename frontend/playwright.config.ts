import { defineConfig, devices } from "@playwright/test";

/**
 * The six harness-dependent specs (task 11.1). They drive
 * `window.__atlasHarness`, which exists ONLY in the `e2e`-mode build
 * (`pnpm build:e2e` -> `dist-e2e/`, AD-12), so they are excluded from the
 * default projects and selected by `playwright.harness.config.ts` instead.
 *
 * This is not a way of hiding them: they no longer skip when the harness is
 * missing (a missing harness is now a failure, I-7), so running them against a
 * production preview that cannot contain the harness would report a failure
 * about the wrong thing. They run in the build that has the harness, and their
 * run record (`artifacts/test-reports/playwright-harness.json`) is what
 * `frontend/spec/check_fe_invariants.py` reads for FE-INV-056.
 */
export const HARNESS_SPEC_PATTERN =
  /(task-completion\.jtbd|fault-transition\.resilience|firehose-stress\.resilience|scale-virtualization\.resilience|spatial-visualization|assistive-tech-flow)\.spec\.ts$/;

const isCi = !!process.env.CI;
const baseUrlOverride = process.env.PLAYWRIGHT_BASE_URL;
// Where the JSON run record lands. `PLAYWRIGHT_JSON_OUTPUT_NAME` is Playwright's
// own override and takes precedence when a job needs a distinct file per run
// (e.g. the nightly real-stack run).
const jsonReport =
  process.env.PLAYWRIGHT_JSON_OUTPUT_NAME ?? "artifacts/test-reports/playwright.json";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: isCi,
  retries: isCi ? 1 : 0,
  // `workers` is omitted off-CI so Playwright picks its default — passing an
  // explicit `undefined` is rejected under `exactOptionalPropertyTypes`.
  ...(isCi ? { workers: 2 } : {}),
  // The `json` reporter is always on: `frontend/spec/check_fe_invariants.py`
  // gates the FE-INV registry on EXECUTED, non-skipped assertions read from this
  // file (R8.7), so a run that emits no record is `unavailable` to that gate, not
  // a pass. `PLAYWRIGHT_JSON_OUTPUT_NAME` still wins when set — the nightly
  // real-stack job (`integration.yml::real-stack-run`) already relies on it. The
  // default path is outside `outputDir` (which Playwright wipes per run) and
  // under the gitignored `artifacts/` tree.
  reporter: isCi
    ? [
        ["html", { open: "never" }],
        ["github"],
        ["json", { outputFile: jsonReport }],
      ]
    : [["list"], ["json", { outputFile: jsonReport }]],
  timeout: 30_000,
  expect: {
    timeout: 5_000,
    // Deterministic Visual_Regression_Gate threshold (Req 14.2, 14.3). The
    // gate fails when a captured screenshot diverges from its committed
    // baseline beyond this defined tolerance; the small pixel-ratio allowance
    // absorbs benign anti-aliasing noise without hiding real token/layout
    // regressions. `animations: "disabled"` and `scale: "css"` keep captures
    // stable across runs; `caret: "hide"` removes the blinking text caret.
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      threshold: 0.2,
      animations: "disabled",
      scale: "css",
      caret: "hide",
    },
  },
  use: {
    baseURL: baseUrlOverride ?? "http://localhost:3001",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  // The Visual_Regression_Gate lives under `tests/e2e/visual/` and runs in its
  // own `visual` project (below). Every other project ignores that directory so
  // the functional E2E job never trips over screenshot baselines (Req 14.2).
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: [/visual\//, HARNESS_SPEC_PATTERN],
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
      testIgnore: [/visual\//, HARNESS_SPEC_PATTERN],
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
      testIgnore: [/visual\//, HARNESS_SPEC_PATTERN],
    },
    {
      name: "mobile-cockpit",
      use: { ...devices["iPhone 14"] },
      testMatch: /cockpit\.spec\.ts/,
    },
    // Visual_Regression_Gate (Req 14): deterministic screenshot diffing on a
    // fixed Chromium profile. Kept in a dedicated project so the deterministic
    // PR gate stays isolated and non-flaky.
    {
      name: "visual",
      use: { ...devices["Desktop Chrome"] },
      testMatch: /visual\/.*\.spec\.ts/,
    },
  ],
  // When PLAYWRIGHT_BASE_URL is set the suite runs against an already-running
  // server, so `webServer` is omitted entirely rather than set to `undefined`.
  ...(baseUrlOverride
    ? {}
    : {
        webServer: {
          command: "pnpm preview --port 3001",
          url: "http://localhost:3001",
          reuseExistingServer: !isCi,
          timeout: 60_000,
        },
      }),
});
