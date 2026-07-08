import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// P0 smoke: every route reachable, every route a11y-clean.
//
// This list MUST mirror every primary Surface path in
// `src/app/primary-surfaces.ts` (PRIMARY_SURFACES), in operator-loop order
// (Monitor → Intervene → Investigate → Configure). Adding a primary Surface
// there requires adding its path here so the axe smoke matrix keeps full
// route coverage (Req 15.3 smoke/axe matrix).
const ROUTES = [
  "/", // mission-control  (Monitor)
  "/markets", // live-markets     (Monitor)
  "/operations", // operations       (Monitor)
  "/cockpit", // override-cockpit (Intervene)
  "/ingress", // ingress          (Intervene)
  "/decisions", // decision-theater (Investigate)
  "/agents", // agent-council    (Investigate)
  "/twin", // twin-lab         (Investigate)
  "/audit", // audit-vault      (Investigate)
  "/steering", // steering         (Configure)
  "/demo", // demo-theater     (Configure)
];

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
