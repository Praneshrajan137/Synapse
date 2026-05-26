import { expect, test } from "@playwright/test";

/**
 * Steering surface — Pareto weights + tier thresholds + live preview.
 * Covers FE-INV-033 (operator-tunable governance, audit-logged on
 * change).
 *
 * The /steering route is `RouteGuard minRole="ops"` — we seed a session
 * directly into sessionStorage before the app boots, mirroring the
 * cockpit.spec.ts pattern. The surface itself renders backend-free
 * (Zustand+persist state, no fetch), so the entire suite runs without
 * the orchestrator stack.
 */
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

test("@smoke Steering renders all 7 sliders and the constellation preview", async ({ page }) => {
  await page.goto("/steering");
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

test("@smoke Steering persists weight changes across reload (Zustand+persist)", async ({ page }) => {
  await page.goto("/steering");
  await expect(page.getByRole("heading", { name: /Steering/i, level: 1 })).toBeVisible();

  // Set Cost weight to 0.6 (default is 0.35) via the native range input.
  const cost = page.getByRole("slider", { name: /Cost/i });
  await cost.fill("0.6");
  // Round-trip: reload, then the localStorage["synapse.steering"] hydrate
  // path should restore the slider to 0.6.
  await page.reload();
  await expect(page.getByRole("slider", { name: /Cost/i })).toHaveValue("0.6");
});
