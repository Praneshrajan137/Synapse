import { test, expect } from "@playwright/test";

test("Override Cockpit shows empty-state and connection pill", async ({ page }) => {
  await page.goto("/cockpit");
  await expect(page.getByRole("heading", { name: /Override Cockpit/i })).toBeVisible();
  await expect(page.getByRole("status")).toBeVisible();
});
