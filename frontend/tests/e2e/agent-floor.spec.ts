/**
 * SYNAPSE Atlas Console — Playwright golden paths · Agent Floor.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const URL = "/bengaluru/agents";

test.describe("@smoke @agent-floor", () => {
  test("renders 8 agent panels derived from spec.yaml", async ({ page }) => {
    await page.goto(URL);
    await expect(page.getByRole("heading", { level: 1, name: /agent floor/i })).toBeVisible();
    // 8 spec.yaml files in agents/. The plan acceptance is exact: panel
    // count tracks spec count without UI code change.
    const panels = page.getByRole("article").or(page.locator("[data-slot='card']"));
    const count = await page.locator("text=Details →").count();
    expect(count).toBe(8);
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
