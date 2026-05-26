import { expect, test } from "@playwright/test";

/**
 * Steering surface — Pareto weights + tier thresholds + live preview.
 * Covers FE-INV-033 (operator-tunable governance, audit-logged on
 * change).
 *
 * The auth + nav setup uses the same pattern as cockpit.spec.ts; the
 * shell renders the surface inside the authenticated layout.
 */
test.describe("@smoke Steering", () => {
  test("renders all 7 sliders and the constellation preview", async ({ page }) => {
    await page.goto("/steering");
    // If not authenticated, a real ops-role login fixture should run first.
    // For smoke we accept either the surface itself or the login redirect
    // — the assertion below checks the surface only when we land on it.
    if (page.url().includes("/login")) {
      test.skip(true, "needs ops-role login fixture");
    }
    await expect(page.getByRole("heading", { name: /Steering/i, level: 1 })).toBeVisible();

    // 4 Pareto weight sliders
    for (const name of ["Cost", "Time", "Sustainability", "Fairness"]) {
      await expect(page.getByRole("slider", { name: new RegExp(name, "i") })).toBeVisible();
    }
    // 3 tier-threshold sliders
    for (const tier of ["Tier 2", "Tier 3", "Tier 4"]) {
      await expect(page.getByRole("slider", { name: new RegExp(tier, "i") })).toBeVisible();
    }
    // Constellation preview is the 8-agent figure
    await expect(page.getByRole("figure", { name: /Agent proposal constellation/i })).toBeVisible();

    // Audit note is visible
    await expect(page.getByText(/audit-logged to synapse\.steering\.config/i)).toBeVisible();
  });

  test("@needs-backend persists weight changes across reload", async ({ page }) => {
    await page.goto("/steering");
    if (page.url().includes("/login")) {
      test.skip(true, "needs ops-role login fixture");
    }
    const cost = page.getByRole("slider", { name: /Cost/i });
    await cost.fill("0.6");
    await page.reload();
    // Reload should restore from localStorage["synapse.steering"]
    await expect(page.getByRole("slider", { name: /Cost/i })).toHaveValue("0.6");
  });
});
