/**
 * SYNAPSE Atlas Console — Playwright golden paths · Decision Trace.
 *
 * Mirrors decisions/bdd/replay-window.feature.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const DT_URL = "/bengaluru/decisions";

test.describe("@smoke @decision-trace", () => {
  test("renders title + filter rail + table", async ({ page }) => {
    await page.goto(DT_URL);
    await expect(page.getByRole("heading", { level: 1, name: /decision trace/i })).toBeVisible();
    await expect(page.getByRole("search")).toBeVisible();
    await expect(page.getByRole("region", { name: /decision trace/i })).toBeVisible();
  });

  test("filtering on tier writes the search-param to the URL", async ({ page }) => {
    await page.goto(DT_URL);
    await page.getByLabel(/tier/i).first().selectOption("tier_4");
    await expect(page).toHaveURL(/[?&]tier=tier_4/);
  });

  test("axe finds zero serious or critical violations on first paint", async ({ page }) => {
    await page.goto(DT_URL);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    const blockers = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(blockers).toEqual([]);
  });
});

test.describe("@decision-trace @needs-backend", () => {
  test.skip(true, "requires the gateway + audit_consensus seed; runs in nightly Playwright");
  test("opening a row renders the chain-proof banner", async () => {
    /* future: seed Postgres → click row → chain banner verified. */
  });
});
