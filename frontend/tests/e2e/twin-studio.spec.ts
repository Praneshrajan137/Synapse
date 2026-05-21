import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const URL = "/bengaluru/twin";

test.describe("@smoke @twin-studio", () => {
  test("loads form + scenario library shell", async ({ page }) => {
    await page.goto(URL);
    await expect(page.getByRole("heading", { level: 1, name: /twin studio/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /run simulation/i })).toBeVisible();
  });

  test("input changes mirror to URL search-params", async ({ page }) => {
    await page.goto(URL);
    const input = page.getByLabel(/demand multiplier/i);
    await input.fill("1.5");
    await input.blur();
    await expect(page).toHaveURL(/demand_multiplier=1\.5/);
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
