import { expect, test } from "@playwright/test";

// ADR-057 boot-access contract (finding 89): the console asks GET /api/v1/auth/mode how to
// enter. Open -> a preview grant and no sign-in; authenticated -> /login; unreachable -> the
// console still opens. No credential is compiled into the bundle, so none is sent.

const OPEN_VIEW = { mode: "open", authority: "view" };
const AUTHENTICATED = { mode: "authenticated", authority: null };
const VIEW_GRANT = {
  access_token: "e2e.preview.token",
  token_type: "Bearer",
  expires_in: 3600,
  role: "viewer",
  operator_token_ref: "e2e-preview",
  authority: "view",
};

test("open mode boots into Mission Control with a view-only preview badge", async ({ page }) => {
  await page.route("**/api/v1/auth/mode", (route) => route.fulfill({ json: OPEN_VIEW }));
  await page.route("**/api/v1/auth/preview", (route) => route.fulfill({ json: VIEW_GRANT }));
  await page.goto("/");
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: /Mission Control/i })).toBeVisible();
  await expect(page.getByText("Preview access - view only")).toBeVisible();
});

test("a view-only preview meets an ops surface with an authority state, not /login", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/mode", (route) => route.fulfill({ json: OPEN_VIEW }));
  await page.route("**/api/v1/auth/preview", (route) => route.fulfill({ json: VIEW_GRANT }));
  await page.goto("/cockpit");
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: /Insufficient authority/i })).toBeVisible();
});

test("authenticated mode sends an anonymous visitor to sign-in", async ({ page }) => {
  await page.route("**/api/v1/auth/mode", (route) => route.fulfill({ json: AUTHENTICATED }));
  await page.goto("/cockpit");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("form", { name: /Operator sign-in/i })).toBeVisible();
});

test("an unreachable gateway still opens the console", async ({ page }) => {
  await page.route("**/api/v1/auth/mode", (route) => route.abort());
  await page.goto("/");
  await expect(page).not.toHaveURL(/\/login/);
  // The mode probe retries a network failure with bounded full-jitter backoff (~3 s worst
  // case) before the console opens without a grant, hence the longer wait.
  await expect(page.getByRole("heading", { name: /Mission Control/i })).toBeVisible({
    timeout: 15_000,
  });
});

test("open mode keeps sign-in dormant on /login", async ({ page }) => {
  await page.route("**/api/v1/auth/mode", (route) => route.fulfill({ json: OPEN_VIEW }));
  await page.route("**/api/v1/auth/preview", (route) => route.fulfill({ status: 403, json: {} }));
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /Sign-in is not activated/i })).toBeVisible();
  await expect(page.getByRole("form", { name: /Operator sign-in/i })).toHaveCount(0);
});

test("Login form is accessible (a11y) @a11y", async ({ page }) => {
  // In authenticated mode the sign-in surface stays directly reachable and accessible.
  await page.route("**/api/v1/auth/mode", (route) => route.fulfill({ json: AUTHENTICATED }));
  await page.goto("/login");
  // Wait for the form itself before counting its fields (`count()` does not retry): Login is
  // route-split, so its fields exist only once its chunk has rendered, and it shows the boot
  // splash until the access posture is read (session 12, F-Q2 review).
  await expect(page.getByRole("form", { name: /Operator sign-in/i })).toBeVisible();
  const inputs = await page.getByRole("textbox").count();
  expect(inputs).toBeGreaterThanOrEqual(1);
  await expect(page.getByRole("button", { name: /Sign in/i })).toBeVisible();
});
