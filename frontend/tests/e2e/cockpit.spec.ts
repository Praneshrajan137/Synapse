import { test, expect } from "@playwright/test";

// The Override Cockpit is gated behind the `ops` role (RouteGuard). E2E runs
// without a backend, so we seed an authenticated session directly into
// sessionStorage — the shape zustand `persist` ("synapse.session") rehydrates
// — before the app boots. The surface itself renders backend-free (empty
// state + connection pill), which is exactly what this test asserts.
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

test("Override Cockpit shows empty-state and connection pill", async ({ page }) => {
  await page.goto("/cockpit");
  await expect(page.getByRole("heading", { name: /Override Cockpit/i })).toBeVisible();
  await expect(page.getByRole("status").first()).toBeVisible();
});
