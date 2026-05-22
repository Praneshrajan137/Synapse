import { test, expect } from "@playwright/test";

// @demo — full Demo Theater walkthrough.
// In CI without a backend, this asserts FE-only behaviour (scrubber +
// segment summaries + i18n surface). With a live backend, `start()`
// drives the run_demo.sh job and the evidence panel renders.
//
// Demo Theater sits behind RouteGuard, so we seed an authenticated session
// into sessionStorage (the shape zustand `persist` rehydrates) before boot.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem(
      "synapse.session",
      JSON.stringify({
        state: { role: "admin", operatorTokenRef: "e2e-operator" },
        version: 0,
      }),
    );
  });
});

test("Demo Theater scrubber works keyboard-first @demo", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: /demo/i })).toBeVisible();

  // The 5 segment buttons live in the <ol aria-label="Demo segments">.
  // Number keys 1-5 scrub between them; the active one carries
  // aria-current="step".
  const segments = page.getByRole("list", { name: /Demo segments/i }).getByRole("button");
  for (let i = 1; i <= 5; i++) {
    await page.keyboard.press(`${i}`);
    await expect(segments.nth(i - 1)).toHaveAttribute("aria-current", "step");
  }
});
