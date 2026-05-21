import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const URL = "/bengaluru/audit";

test.describe("@smoke @audit-vault", () => {
  test("renders title + residency chip + Reveal PII control", async ({ page }) => {
    await page.goto(URL);
    await expect(page.getByRole("heading", { level: 1, name: /audit vault/i })).toBeVisible();
    await expect(page.getByLabel(/data residency|residency/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /reveal pii/i })).toBeVisible();
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
