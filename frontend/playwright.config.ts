import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright — end-to-end and surface-invariant testing.
 *
 * The dev server is started automatically. Backend calls are mocked by
 * MSW in the browser unless VITE_E2E_LIVE is set, so smoke tests run
 * without the Python stack.
 */
const isCI = !!process.env["CI"];

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 2 : undefined,
  reporter: isCI
    ? [["html", { open: "never" }], ["github"]]
    : [["list"]],
  timeout: 30_000,
  expect: { timeout: 7_000 },
  use: {
    baseURL: "http://localhost:4173",
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // E2E runs against the production preview build: no cold dep
  // optimization, deterministic page loads, representative of ship.
  webServer: {
    command: "npm run build && npm run preview -- --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: !isCI,
    timeout: 180_000,
  },
});
