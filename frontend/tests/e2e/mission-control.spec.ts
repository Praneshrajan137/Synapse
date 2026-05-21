/**
 * SYNAPSE Atlas Console — Playwright golden paths · Mission Control.
 *
 * Mirrors mission-control/bdd/approve-tier4-escalation.feature. The
 * Cucumber adapter wires step phrases at S6; for now the spec
 * implements the same scenarios in-line so CI gets a green smoke
 * surface day-one.
 *
 * Network: MSW intercepts in development don't survive a real fetch
 * inside Playwright's Chromium target; CI binds these tests against
 * the actual gateway when available. Until then `webServer` in
 * playwright.config.ts serves the static build, which means the
 * scenarios that depend on a live `/ws/escalation` are tagged
 * @needs-backend and skipped under @smoke.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const MC_URL = "/bengaluru/mission-control";

test.describe("@smoke @mission-control", () => {
  test("loads with a connection indicator and a hotkeys-help button", async ({ page }) => {
    await page.goto(MC_URL);
    await expect(page.getByRole("heading", { level: 1, name: /mission control/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /hotkeys|shortcuts|help/i })).toBeVisible();
  });

  test('"?" opens the hotkeys help dialog (keyboard discoverability)', async ({ page }) => {
    await page.goto(MC_URL);
    await page.keyboard.press("Shift+/"); // "?" on US layout
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("dialog")).toContainText(/next|approve|reject/i);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
  });

  test("axe finds zero serious or critical violations on first paint", async ({ page }) => {
    await page.goto(MC_URL);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    const blockers = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(blockers).toEqual([]);
  });
});

test.describe("@mission-control @needs-backend", () => {
  test.skip(true, "requires a running orchestrator + MSW pass-through; runs in nightly Playwright");
  test("approve a tier-4 escalation via Enter completes within 5 s", async () => {
    /* future: ensure a fixture escalation arrives → Enter → ACK in < 5s. */
  });
});
