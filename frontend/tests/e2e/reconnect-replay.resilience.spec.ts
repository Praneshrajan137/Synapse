import { expect, test, type Page } from "@playwright/test";

/**
 * Resilience_Scenario — reconnect and replay reconciliation (Req 7.1, 7.2, 7.4, 7.5).
 *
 * Drives the `resilience.reconnect-replay` scenario (descriptor:
 * `spec/effectiveness/scenarios/reconnect-replay.ts`) against the decision
 * surface and asserts, AT THE RENDERED OUTPUT (not only the reducer), the
 * reconnect/replay guarantees:
 *
 *   - Req 7.1 — on reconnect the Console requests replay from its last applied
 *     sequence (`since_seq`) and reconciles the burst WITHOUT rendering
 *     duplicate rows.
 *   - Req 7.2 — a replayed message that references an already-acted decision
 *     keeps that decision in its acted state and NEVER reverts it to pending,
 *     verified at the rendered output.
 *   - Req 7.4 — when the scenario completes, the rendered row set equals the
 *     deduplicated union of the pre-drop and replayed/live state with no
 *     duplicate, lost, or reverted rows.
 *   - Req 7.5 — the scenario scripts a drop, a `since_seq` replay burst
 *     containing at least one already-acted decision, and a resumed live
 *     stream, exercised deterministically.
 *
 * ── Harness wiring (graceful-skip convention) ────────────────────────────────
 * The Effectiveness_Harness drives the seeded drop/replay/resume in-browser
 * through a documented global, mirroring the stream driver
 * (`spec/effectiveness/stream-driver.ts` — `drive`/`flap`) and the reconcile
 * reducer (`src/lib/reconcile.ts`):
 *
 *   interface AtlasHarness {
 *     seedScenario?(scenarioId: string): Promise<void>;      // reach the populated + acted baseline
 *     driveResilience?(scenarioId: string): Promise<void>;   // drop → since_seq replay → resumed live
 *   }
 *   declare global { interface Window { __atlasHarness?: AtlasHarness } }
 *
 * Until that global is wired (the browser worker + stream driver expose it) the
 * reconciliation assertions skip cleanly rather than failing — the same
 * graceful-skip convention as the other harness-dependent e2e specs
 * (firehose-stress.resilience.spec.ts, fault-transition.resilience.spec.ts).
 * The base render check (the surface is reachable and not bounced to /login)
 * runs regardless, so this spec is committed and ready the moment the driver
 * lands.
 *
 * The scenario plan below MIRRORS the descriptor but is kept LOCAL so this
 * Playwright spec stays free of the app's `@`-alias / spec module graph (same
 * convention as the sibling e2e specs).
 */

const SCENARIO_ID = "resilience.reconnect-replay";

/** A decision row is rendered with its decision id and terminal status.
 *  Mirrors the `data-stream-row` convention used by the firehose spec. */
const DECISION_ROW = "[data-decision-row]";
const ACTED_ROW = '[data-decision-row][data-decision-status="acted"]';

/** The decision ids expected in the final rendered set — the deduplicated union
 *  of the pre-drop, replayed, and resumed-live rows from the descriptor. Kept
 *  local (mirrors `RECONNECT_REPLAY.replay`). */
const EXPECTED_DECISION_IDS = [
  "dec-1",
  "dec-2",
  "dec-3",
  "dec-4",
  "dec-5",
  "dec-6",
  "dec-7",
] as const;

/** The decision that is acted before the drop and re-carried (as a stale
 *  pending) in the replay burst — it must stay acted (Req 7.2). */
const ACTED_DECISION_ID = "dec-2";

/** True iff the harness global exposes the reconnect/replay driver in the page. */
async function replayHarnessReady(page: Page): Promise<boolean> {
  return page.evaluate(
    () =>
      typeof (window as unknown as { __atlasHarness?: { driveResilience?: unknown } })
        .__atlasHarness?.driveResilience === "function",
  );
}

/** Reach the populated + acted baseline for the scenario if the harness seeds it. */
async function seedBaseline(page: Page, scenarioId: string): Promise<void> {
  await page.evaluate(async (id) => {
    const harness = (
      window as unknown as { __atlasHarness?: { seedScenario?(id: string): Promise<void> } }
    ).__atlasHarness;
    if (harness?.seedScenario) await harness.seedScenario(id);
  }, scenarioId);
}

/** Drive the drop → since_seq replay burst → resumed live stream to completion. */
async function driveReconnectReplay(page: Page, scenarioId: string): Promise<void> {
  await page.evaluate(async (id) => {
    const harness = (
      window as unknown as { __atlasHarness: { driveResilience(id: string): Promise<void> } }
    ).__atlasHarness;
    await harness.driveResilience(id);
  }, scenarioId);
}

/** The decision id of every currently-rendered row, in DOM order. */
async function renderedDecisionIds(page: Page): Promise<string[]> {
  return page
    .locator(DECISION_ROW)
    .evaluateAll((nodes) =>
      nodes
        .map((n) => n.getAttribute("data-decision-row"))
        .filter((id): id is string => id !== null),
    );
}

test.beforeEach(async ({ page }) => {
  // Seed an authenticated (admin) session so RouteGuard passes (mirrors the
  // sibling harness e2e specs).
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

test.describe("Resilience — reconnect and replay reconciliation (Req 7)", () => {
  test("keeps acted decisions acted and renders no duplicate rows after replay", async ({
    page,
  }) => {
    // Base reachability: the decision surface loads and is not bounced to /login.
    await page.goto("/");
    if (page.url().includes("/login")) {
      test.skip(true, "needs an authenticated session fixture");
    }
    await expect(page.locator("main")).toBeVisible();

    // Driving the seeded drop/replay/resume needs the in-browser harness global;
    // skip the reconciliation assertions cleanly until it is wired (same
    // convention as the other harness-dependent e2e specs).
    if (!(await replayHarnessReady(page))) {
      test.skip(
        true,
        "reconnect-replay harness (window.__atlasHarness.driveResilience) not wired yet",
      );
    }

    // Reach the populated + acted baseline: the pre-drop rows are rendered and
    // one decision (dec-2) is already acted (Req 7.5).
    await seedBaseline(page, SCENARIO_ID);

    // Snapshot the rows rendered before the drop so we can prove none are lost
    // (Req 7.4) and the acted one stays acted (Req 7.2).
    const beforeIds = await renderedDecisionIds(page);
    await expect(
      page.locator(`${ACTED_ROW}[data-decision-row="${ACTED_DECISION_ID}"]`),
      "the pre-drop baseline must render an already-acted decision",
    ).toBeVisible();

    // Drive the drop → since_seq replay burst (re-carrying the acted decision as
    // a stale pending, plus an already-held sequence) → resumed live stream.
    await driveReconnectReplay(page, SCENARIO_ID);

    const afterIds = await renderedDecisionIds(page);

    // Req 7.2 — the already-acted decision stays acted after the replay burst
    // re-carried it as a stale pending; it is NEVER reverted to pending.
    await expect(
      page.locator(`${ACTED_ROW}[data-decision-row="${ACTED_DECISION_ID}"]`),
      "an already-acted decision was reverted to pending after replay",
    ).toBeVisible();

    // Req 7.1 / 7.4 — no replayed sequence renders a duplicate row.
    const uniqueAfter = new Set(afterIds);
    expect(uniqueAfter.size, "a replayed sequence rendered a duplicate row").toBe(afterIds.length);

    // Req 7.4 — no pre-drop row is lost by the reconciliation.
    for (const id of beforeIds) {
      expect(afterIds, `pre-drop row "${id}" was lost after reconciliation`).toContain(id);
    }

    // Req 7.4 — the final rendered set equals the deduplicated union of the
    // pre-drop, replayed, and resumed-live rows (no duplicate, lost, or extra).
    expect(uniqueAfter).toEqual(new Set(EXPECTED_DECISION_IDS));
  });
});
