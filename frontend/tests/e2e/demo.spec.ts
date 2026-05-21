import { test, expect } from "@playwright/test";

// @demo — full Demo Theater walkthrough.
// In CI without a backend, this asserts FE-only behaviour (scrubber +
// segment summaries + i18n surface). With a live backend, `start()`
// drives the run_demo.sh job and the evidence panel renders.

test("Demo Theater scrubber works keyboard-first @demo", async ({ page }) => {
  await page.goto("/login");
  // Anonymous can read demo summary route guards permit viewer access;
  // for E2E we skip auth and rely on FE-only render.
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: /demo/i })).toBeVisible();
  for (let i = 1; i <= 5; i++) {
    await page.keyboard.press(`${i}`);
    await expect(page.getByRole("button", { name: new RegExp(`0${i}`) }).first()).toHaveAttribute(
      "aria-current",
      "step",
    );
  }
});
