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
  expect: { timeout: 5_000 },
  use: {
    baseURL: baseUrlOverride ?? "http://localhost:3001",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    { name: "mobile-cockpit", use: { ...devices["iPhone 14"] }, testMatch: /cockpit\.spec\.ts/ },
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
