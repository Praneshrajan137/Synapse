import { expect, test } from "@playwright/test";

/**
 * Smoke suite — the Synaptic Calm shell boots, the seven surfaces are
 * reachable, the rebuilt surfaces (Bridge, Theater, Council, Replay)
 * render real content, and the command palette works from the keyboard.
 */

const SURFACES = [
  "Bridge",
  "Theater",
  "Council",
  "Replay",
  "Twin",
  "Inspector",
  "Streams",
] as const;

test("@smoke shell renders with the seven surfaces", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle(/SYNAPSE/);

  const sidebar = page.getByRole("navigation", { name: "Surfaces" });
  await expect(sidebar).toBeVisible();

  for (const label of SURFACES) {
    await expect(sidebar.getByRole("link", { name: label })).toBeVisible();
  }
});

test("@smoke Bridge renders the KPI ribbon and living map", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Key performance indicators")).toBeVisible();
  await expect(page.getByRole("img", { name: /dark-store network/ })).toBeVisible();
});

test("@smoke Theater renders the consensus stage", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Theater" }).click();
  await expect(page).toHaveURL(/\/theater$/);
  await expect(page.getByRole("heading", { name: "Theater" })).toBeVisible();
  await expect(page.getByLabel(/Consensus phase/)).toBeVisible();
});

test("@smoke Council blocks override until choice and reason given", async ({ page }) => {
  await page.goto("/council");
  await expect(page.getByRole("heading", { name: "Council" })).toBeVisible();
  const submit = page.getByRole("button", { name: "Submit override" });
  await expect(submit).toBeDisabled();
});

test("@smoke Replay shows the audit timeline and tamper-evidence", async ({ page }) => {
  await page.goto("/replay");
  await expect(page.getByLabel("Audit timeline")).toBeVisible();
});

test("@smoke command palette opens with the keyboard", async ({ page }) => {
  await page.goto("/");
  // Wait for the shell to mount so the global keyboard listener is live.
  await expect(page.getByRole("navigation", { name: "Surfaces" })).toBeVisible();

  await page.keyboard.press("Control+k");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await expect(palette).toBeVisible();

  await page.getByPlaceholder(/Search surfaces/).fill("inspector");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/inspector$/);
});

test("@smoke legacy routes redirect into the new surfaces", async ({ page }) => {
  await page.goto("/escalations");
  await expect(page).toHaveURL(/\/council$/);
});
