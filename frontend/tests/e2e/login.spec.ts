import { test, expect } from "@playwright/test";

// FE-INV-022 + FE-INV-023 smoke. With no auth wired to a real backend in
// E2E this test is anchored to the FE-only behaviours: the Login surface
// is reachable, RouteGuard punts unauthenticated visitors back to /login.

test("anonymous visit to /cockpit redirects to /login", async ({ page }) => {
  await page.goto("/cockpit");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("form", { name: /Operator sign-in/i })).toBeVisible();
});

test("Login form is accessible (a11y) @a11y", async ({ page }) => {
  await page.goto("/login");
  const inputs = await page.getByRole("textbox").count();
  expect(inputs).toBeGreaterThanOrEqual(1);
  await expect(page.getByRole("button", { name: /Sign in/i })).toBeVisible();
});
