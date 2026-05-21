import { defineConfig, devices } from "@playwright/test";

// SYNAPSE Atlas Console — Playwright config.
//
// Two persona profiles + an axe-only project for accessibility regressions.
// BDD scenarios live in src/surfaces/*/bdd/*.feature and are mounted via
// the @cucumber/cucumber adapter; @smoke-tagged scenarios run on every PR,
// the full set runs nightly per plan §14.
//
// Determinism:
//   - workers: fixed at 1 in CI to avoid Kafka/SSE flakiness on shared boxes.
//   - traces, video, screenshots on first failure only — review-friendly.
const isCI = !!process.env["CI"];

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: !isCI,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 1 : undefined,
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["junit", { outputFile: "test-results/junit.xml" }],
  ],
  use: {
    baseURL: process.env["E2E_BASE_URL"] ?? "http://localhost:3001",
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
    extraHTTPHeaders: {
      // Forward a deterministic request id so SSE bridge logs are correlatable.
      "X-Request-ID": "playwright-${random}",
    },
  },
  projects: [
    {
      name: "ops-controller-chromium",
      use: { ...devices["Desktop Chrome"] },
      grepInvert: /@a11y-only/,
    },
    {
      name: "ops-controller-firefox",
      use: { ...devices["Desktop Firefox"] },
      grep: /@cross-browser|@smoke/,
    },
    {
      name: "a11y-aaa",
      testDir: "./tests/a11y",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-supply-analyst",
      use: { ...devices["Pixel 7"] },
      grep: /@mobile|@smoke/,
    },
  ],
  webServer: isCI
    ? undefined
    : {
        command: "pnpm dev",
        url: "http://localhost:3001",
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
