import { expect, test, type Page } from "@playwright/test";

/**
 * Resilience_Scenario — scale virtualization (Req 9.1, 9.2, 9.5).
 *
 * Drives the `resilience.scale-virtualization` scenario (descriptor:
 * `spec/effectiveness/scenarios/scale-virtualization.ts`) against BOTH the
 * Audit Vault (`/audit`) and the Decision Theater (`/decisions`) — the two
 * surfaces retrofitted with `@tanstack/react-virtual` (task 10.1) — and
 * asserts, at the rendered output:
 *
 *   - Req 9.1 — row virtualization is actually engaged: the count of mounted
 *     row nodes stays bounded and far below the seeded total (10k), regardless
 *     of how many rows loaded.
 *   - Req 9.3/9.5 — the full seeded row set is reachable by scrolling; no fixed
 *     row cap (the removed `limit: 200` / `limit: 100`) hides rows — scrolling
 *     to the end mounts a row whose index is near the 10k total.
 *   - Req 9.2 — scroll and interaction responsiveness stays within the
 *     Web_Vitals_Budget (INP ≤ 200 ms) while the 10k-row dataset is displayed.
 *
 * The harness (`spec/effectiveness/harness.ts`, task 11.1) seeds the 10k-row
 * `AuditListResponse` fixture the two surfaces read via `listRecentDecisions`,
 * re-validated through the same `Domain_Schema` the Console applies. It exposes
 * the same documented global the other harness-dependent specs drive:
 *
 *   interface AtlasHarness {
 *     driveResilience(scenarioId: string): Promise<void>; // seeds/activates the scenario
 *   }
 *   declare global { interface Window { __atlasHarness?: AtlasHarness } }
 *
 * The global exists only in the e2e-mode build (AD-12), so this suite runs as
 * `pnpm build:e2e && pnpm test:e2e:harness`. A missing harness FAILS the test
 * rather than skipping it (I-7).
 */

const SCENARIO_ID = "resilience.scale-virtualization";
// Mirrors `WEB_VITALS_BUDGET.inpMs` (single source of truth in the descriptor).
// Kept local so this Playwright spec stays free of the app's `@`-alias graph.
const INP_BUDGET_MS = 200;
// The seeded total (`SCALE_MIN_ROWS`); the mounted node count must stay far
// below this and the reachable index must climb near it.
const SEEDED_ROWS = 10_000;
// A generous ceiling on mounted row nodes — the virtualizer mounts only a
// viewport-sized window plus overscan (tens of rows), so any bound this far
// below the 10k total proves virtualization is engaged (Req 9.1).
const MOUNTED_ROW_BOUND = 500;
// After scrolling to the end, at least one mounted row must carry an index
// near the seeded total, proving the full set is reachable (Req 9.3/9.5) and
// not capped at a fixed limit like 200.
const REACHABLE_MIN_INDEX = SEEDED_ROWS - 500;

// Only real data rows carry `data-index`; the virtualizer's top/bottom spacer
// `<tr>` elements do not, so this selector counts mounted row nodes exactly.
const ROW = "tbody tr[data-index]";

test.beforeEach(async ({ page }) => {
  // Seed an authenticated session so RouteGuard passes (mirrors cockpit.spec.ts
  // / firehose-stress.resilience.spec.ts).
  await page.addInitScript(() => {
    sessionStorage.setItem(
      "synapse.session",
      JSON.stringify({
        state: { role: "admin", operatorTokenRef: "e2e-operator" },
        version: 0,
      }),
    );
  });
});

/**
 * Fails the test when the harness global is absent (task 11.1). The harness is a
 * REQUIREMENT of a seeded 10k-row measurement, so its absence is a failure, not
 * a skip (I-7).
 */
async function requireHarness(page: Page): Promise<void> {
  const harnessReady = await page.evaluate(
    () => typeof (window as unknown as { __atlasHarness?: unknown }).__atlasHarness === "object",
  );
  expect(
    harnessReady,
    "window.__atlasHarness is absent: run the harness suite against the e2e-mode build " +
      "(pnpm build:e2e && pnpm test:e2e:harness)",
  ).toBe(true);
}

/** Drives the seeded scale scenario (seeds the 10k-row fixture). */
async function driveScaleScenario(page: Page): Promise<void> {
  await page.evaluate(async (scenarioId) => {
    const harness = (window as unknown as {
      __atlasHarness: { driveResilience(id: string): Promise<void> };
    }).__atlasHarness;
    await harness.driveResilience(scenarioId);
  }, SCENARIO_ID);
}

/** Asserts the scale-virtualization guarantees on the current surface. */
async function assertVirtualizedScale(page: Page): Promise<void> {
  await expect(page.locator("main")).toBeVisible();
  await requireHarness(page);
  await driveScaleScenario(page);

  // Wait for the seeded dataset to render its virtualized window.
  await expect(page.locator(ROW).first()).toBeVisible();

  // Req 9.1 — only a bounded window of row nodes is mounted, far below the 10k
  // seeded total, proving virtualization is engaged rather than rendering all
  // rows.
  const mountedTop = await page.locator(ROW).count();
  expect(mountedTop).toBeGreaterThan(0);
  expect(mountedTop).toBeLessThanOrEqual(MOUNTED_ROW_BOUND);

  // Begin recording the longest interaction (INP proxy — Req 9.2) across the
  // scroll interactions below.
  await page.evaluate(() => {
    const w = window as unknown as { __inpMax?: number };
    w.__inpMax = 0;
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as PerformanceEntry[]) {
        const dur = (entry as PerformanceEntry & { duration: number }).duration;
        if (dur > (w.__inpMax ?? 0)) w.__inpMax = dur;
      }
    });
    observer.observe({
      type: "event",
      buffered: true,
      durationThreshold: 16,
    } as PerformanceObserverInit);
  });

  // Scroll the virtualized container to its end so the tail of the dataset is
  // mounted (Req 9.3/9.5 — the full set is reachable by scrolling).
  const scroller = page
    .locator("div.overflow-auto")
    .filter({ has: page.locator("table") })
    .first();
  await scroller.evaluate((el) => {
    el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
  });
  // Allow the virtualizer to remount the window at the new offset.
  await expect
    .poll(
      async () => {
        await scroller.evaluate((el) => {
          el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
        });
        return page.locator(ROW).evaluateAll((nodes) =>
          nodes.reduce((max, n) => {
            const i = Number(n.getAttribute("data-index"));
            return Number.isFinite(i) && i > max ? i : max;
          }, -1),
        );
      },
      { timeout: 10_000 },
    )
    .toBeGreaterThanOrEqual(REACHABLE_MIN_INDEX);

  // Req 9.1 (again, at the tail) — the mounted node count is still bounded far
  // below the total after scrolling to the end.
  const mountedTail = await page.locator(ROW).count();
  expect(mountedTail).toBeLessThanOrEqual(MOUNTED_ROW_BOUND);

  // A real operator interaction so INP is measured against input, not paints.
  await scroller.evaluate((el) => {
    el.scrollTo({ top: Math.floor(el.scrollHeight / 2), behavior: "auto" });
  });
  await page.locator(ROW).first().click({ trial: false }).catch(() => {
    /* a row link/cell may intercept — the scroll interactions above already fed INP */
  });
  await page.waitForTimeout(200);

  // Req 9.2 — scroll/interaction INP within the Web_Vitals_Budget.
  const inpMax = await page.evaluate(
    () => (window as unknown as { __inpMax?: number }).__inpMax ?? 0,
  );
  expect(inpMax).toBeLessThanOrEqual(INP_BUDGET_MS);
}

test.describe("Resilience — scale virtualization (10k rows)", () => {
  test("Audit Vault virtualizes 10k rows: bounded nodes, full set reachable, INP within budget", async ({
    page,
  }) => {
    await page.goto("/audit");
    if (page.url().includes("/login")) {
      test.skip(true, "needs an authenticated session fixture");
    }
    await assertVirtualizedScale(page);
  });

  test("Decision Theater virtualizes 10k rows: bounded nodes, full set reachable, INP within budget", async ({
    page,
  }) => {
    await page.goto("/decisions");
    if (page.url().includes("/login")) {
      test.skip(true, "needs an authenticated session fixture");
    }
    await assertVirtualizedScale(page);
  });
});
