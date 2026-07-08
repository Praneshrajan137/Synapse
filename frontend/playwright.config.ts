import { defineConfig, devices } from "@playwright/test";

const isCi = !!process.env.CI;
const baseUrlOverride = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: isCi,
  retries: isCi ? 1 : 0,
  // `workers` is omitted off-CI so Playwright picks its default — passing an
  // explicit `undefined` is rejected under `exactOptionalPropertyTypes`.
  ...(isCi ? { workers: 2 } : {}),
  reporter: isCi ? [["html", { open: "never" }], ["github"]] : "list",
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
      testIgnore: /visual\//,
    },
    { name: "firefox", use: { ...devices["Desktop Firefox"] }, testIgnore: /visual\// },
    { name: "webkit", use: { ...devices["Desktop Safari"] }, testIgnore: /visual\// },
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
