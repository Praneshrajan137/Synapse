import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// P0 smoke: every route reachable, every route a11y-clean.

const ROUTES = ["/", "/cockpit", "/decisions", "/agents", "/twin", "/demo"];

for (const route of ROUTES) {
  test(`route ${route} renders and is a11y-clean @a11y`, async ({ page }) => {
    await page.goto(route);
    await expect(page.locator("main")).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  });
}
