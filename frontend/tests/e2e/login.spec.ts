import { expect, test } from "@playwright/test";

// Sprint 16 boot-auth contract: the console opens WITHOUT a login wall —
// useBootAutoLogin silently signs in the demo admin on boot. The login
// surface remains the honest fallback when the gateway rejects or is down.

const ADMIN_LOGIN_RESPONSE = {
  access_token: "e2e.jwt.token",
  token_type: "Bearer",
  expires_in: 900,
  role: "admin",
  operator_token_ref: "vault:tok-e2e-admin",
};

test("cold boot auto-logs-in and lands on Mission Control (no login wall)", async ({ page }) => {
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ json: ADMIN_LOGIN_RESPONSE }),
  );
  await page.goto("/");
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: /Mission Control/i })).toBeVisible();
});

test("a protected route is reachable directly after boot auth", async ({ page }) => {
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ json: ADMIN_LOGIN_RESPONSE }),
  );
  await page.goto("/cockpit");
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: /Override Cockpit/i })).toBeVisible();
});

test("boot-auth failure falls through to /login (the fallback survives)", async ({ page }) => {
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ status: 401, json: { detail: "invalid credentials" } }),
  );
  await page.goto("/cockpit");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("form", { name: /Operator sign-in/i })).toBeVisible();
});

test("Login form is accessible (a11y) @a11y", async ({ page }) => {
  // The fallback surface stays directly reachable and accessible.
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ status: 401, json: { detail: "invalid credentials" } }),
  );
  await page.goto("/login");
  const inputs = await page.getByRole("textbox").count();
  expect(inputs).toBeGreaterThanOrEqual(1);
  await expect(page.getByRole("button", { name: /Sign in/i })).toBeVisible();
});
