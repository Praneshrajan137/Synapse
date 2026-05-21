/**
 * SYNAPSE Atlas Console — Playwright golden paths · Living City.
 *
 * Mirrors _living-city/bdd/city-pulse.feature.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const URL = "/bengaluru/";

test.describe("@smoke @living-city", () => {
  test("renders header + KPI band + map placeholder", async ({ page }) => {
    await page.goto(URL);
    await expect(page.getByRole("heading", { level: 1, name: /living city/i })).toBeVisible();
    await expect(page.getByRole("region", { name: /key performance indicators/i })).toBeVisible();
    await expect(page.getByRole("region", { name: /living city map/i })).toBeVisible();
  });

  test("event tail filter chips are reachable by keyboard", async ({ page }) => {
    await page.goto(URL);
    const tail = page.getByRole("complementary", { name: /live event tail/i });
    await expect(tail).toBeVisible();
    const allChip = tail.getByRole("button", { name: /^all$/ });
    await allChip.focus();
    await expect(allChip).toBeFocused();
  });

  test("axe finds zero serious or critical violations on first paint", async ({ page }) => {
    await page.goto(URL);
    const r = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      r.violations.filter((v) => v.impact === "serious" || v.impact === "critical"),
    ).toEqual([]);
  });
});
