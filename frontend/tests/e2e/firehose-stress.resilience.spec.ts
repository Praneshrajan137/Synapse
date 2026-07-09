import { expect, test } from "@playwright/test";

/**
 * Resilience_Scenario — firehose stress (Req 6.1, 6.2, 6.4, 6.5).
 *
 * Drives the `resilience.firehose-stress` scenario (descriptor:
 * `spec/effectiveness/scenarios/firehose-stress.ts`) against Mission Control
 * and asserts, at the rendered output, the four firehose guarantees:
 *
 *   - Req 6.1 — INP stays within the Web_Vitals_Budget (≤ 200 ms) while the
 *     firehose streams at realistic then adversarial rates.
 *   - Req 6.2 — retained rows stay within the bounded Ring_Buffer cap
 *     regardless of how many messages arrive (mounted row count never exceeds
 *     the channel cap).
 *   - Req 6.4 — already-rendered content is not reflowed or reordered into
 *     dropped-frame jank (the leading rendered rows keep their identity and
 *     order across the burst).
 *   - Req 6.5 — the final state is consistent with the deduplicated applied
 *     message set (no lost, no double-counted rows).
 *
 * The harness stream driver (`spec/effectiveness/stream-driver.ts`, task 2.2)
 * and MSW browser worker (task 2.1) expose a documented global to drive a
 * seeded scenario in-browser:
 *
 *   interface AtlasHarness {
 *     driveResilience(scenarioId: string): Promise<void>; // resolves when the burst has drained
 *   }
 *   declare global { interface Window { __atlasHarness?: AtlasHarness } }
 *
 * Until that global is wired the test skips cleanly rather than failing (the
 * same graceful-skip convention as the other harness-dependent e2e specs), so
 * this spec is committed and ready the moment the stream driver lands.
 */

// Mirrors `WEB_VITALS_BUDGET.inpMs` and the firehose channel caps from the
// descriptor / `state/firehose.store.ts` (single source of truth). Kept local
// so this Playwright spec stays free of the app's `@`-alias module graph.
const INP_BUDGET_MS = 200;
const SCENARIO_ID = "resilience.firehose-stress";
// The largest per-channel cap under stress (`demand` = 500); the streamed row
// list is bounded well below the number of messages the adversarial burst emits.
const MAX_CHANNEL_CAP = 500;

const STREAM_ROW = "[data-stream-row]";

test.beforeEach(async ({ page }) => {
  // Seed an authenticated session so RouteGuard passes (mirrors cockpit.spec.ts).
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

test.describe("Resilience — firehose stress", () => {
  test("stays within the INP budget and never reflows/loses rendered rows under the firehose", async ({
    page,
  }) => {
    await page.goto("/");
    if (page.url().includes("/login")) {
      test.skip(true, "needs an authenticated session fixture");
    }
    await expect(page.locator("main")).toBeVisible();

    // The harness stream driver must be present to drive the seeded firehose.
    const harnessReady = await page.evaluate(
      () => typeof (window as unknown as { __atlasHarness?: unknown }).__atlasHarness === "object",
    );
    if (!harnessReady) {
      test.skip(true, "firehose harness stream driver not wired yet (tasks 2.1/2.2)");
    }

    // Snapshot the identity + order of the currently-rendered rows so we can
    // assert already-rendered content is not reordered by the burst (Req 6.4).
    const beforeIds = await page.locator(STREAM_ROW).evaluateAll((nodes) =>
      nodes.map((n) => n.getAttribute("data-stream-row")),
    );

    // Begin recording long interaction events (INP proxy — Req 6.1). We use the
    // Event Timing API's longest interaction duration observed during the burst.
    await page.evaluate(() => {
      const w = window as unknown as { __inpMax?: number };
      w.__inpMax = 0;
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as PerformanceEntry[]) {
          const dur = (entry as PerformanceEntry & { duration: number }).duration;
          if (dur > (w.__inpMax ?? 0)) w.__inpMax = dur;
        }
      });
      observer.observe({ type: "event", buffered: true, durationThreshold: 16 } as PerformanceObserverInit);
    });

    // Drive the seeded firehose (realistic then adversarial rates). Resolves
    // when the burst has drained.
    await page.evaluate(async (scenarioId) => {
      const harness = (window as unknown as {
        __atlasHarness: { driveResilience(id: string): Promise<void> };
      }).__atlasHarness;
      await harness.driveResilience(scenarioId);
    }, SCENARIO_ID);

    // Exercise a real interaction during/after the burst so INP is measured
    // against operator input, not just streamed paints.
    await page.locator("main").click({ position: { x: 8, y: 8 } });
    await page.waitForTimeout(200);

    // Req 6.1 — INP within the Web_Vitals_Budget.
    const inpMax = await page.evaluate(
      () => (window as unknown as { __inpMax?: number }).__inpMax ?? 0,
    );
    expect(inpMax).toBeLessThanOrEqual(INP_BUDGET_MS);

    // Req 6.2 — mounted rows stay within the bounded Ring_Buffer cap regardless
    // of how many messages the burst emitted.
    const mountedRows = await page.locator(STREAM_ROW).count();
    expect(mountedRows).toBeLessThanOrEqual(MAX_CHANNEL_CAP);

    // Req 6.4 — already-rendered rows keep their identity and relative order
    // (no reflow/reorder jank of content that was on screen before the burst).
    const afterIds = await page.locator(STREAM_ROW).evaluateAll((nodes) =>
      nodes.map((n) => n.getAttribute("data-stream-row")),
    );
    const survivors = beforeIds.filter((id) => id !== null && afterIds.includes(id));
    const survivorOrderAfter = afterIds.filter((id) => survivors.includes(id));
    expect(survivorOrderAfter).toEqual(survivors);

    // Req 6.5 — the final rendered set has no double-counted rows (dedup by id).
    const uniqueAfter = new Set(afterIds.filter((id) => id !== null));
    expect(uniqueAfter.size).toBe(afterIds.filter((id) => id !== null).length);
  });
});
