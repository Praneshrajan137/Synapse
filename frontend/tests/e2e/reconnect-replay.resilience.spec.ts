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
 * -- Why this spec still skips, and what would un-skip it (task 11.1, I-7) -----
 * The other six harness-dependent specs were un-skipped when
 * `window.__atlasHarness` landed (`spec/effectiveness/harness.ts`): a missing
 * harness now FAILS them. This one was NOT, and the reason is not the harness
 * global -- `driveResilience` exists. Three things this spec asserts are absent
 * from the shipped Console, and none of them can be supplied from the harness:
 *
 *   1. **No row identity in the DOM.** `renderedDecisionIds()` and `ACTED_ROW`
 *      read `[data-decision-row]` / `[data-decision-status]`. Neither attribute
 *      is rendered anywhere under `frontend/src/` (grep: zero hits), so every
 *      assertion below would compare an empty set against
 *      `EXPECTED_DECISION_IDS` and fail while naming the wrong cause.
 *   2. **No `replay`-plan driver.** `RECONNECT_REPLAY` scripts a
 *      `replay: { preDrop, sinceSeq, replay, live }` plan and declares no
 *      `rates`, so `harness.driveResilience` seeds the fixture and returns
 *      without driving a drop or a `since_seq` burst. Adding that driver is
 *      cheap; on its own it changes nothing while (1) and (3) hold.
 *   3. **The reconciler is dormant.** `src/lib/reconcile.ts` -- the
 *      acted-never-reverted reducer whose guarantee Req 7.2 is about -- is
 *      imported only by its own property tests (audit R13). The live socket
 *      dedups by `isFreshSeq` (`transport/ws-multiplex.ts`) and resumes with
 *      `since_seq` (`hooks/use-firehose.ts`), so (1)/(3) are the production
 *      work, not test work.
 *
 * So the skip is retained deliberately and its reason is stated above rather
 * than as "not wired yet", which is no longer true. A skip is not a pass
 * (I-7): this spec contributes no evidence for Req 7 and must not be counted
 * as if it did. RATCHET -- un-skip in one change, once the decision surfaces
 * render `data-decision-row`/`data-decision-status`, the Console reconciles a
 * `since_seq` burst through `reconcile`, and the harness drives the `replay`
 * plan. The base render check runs regardless.
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

    // The reconciliation assertions below cannot run honestly yet — see the
    // three blockers in this file's header. The harness global is necessary but
    // NOT sufficient, so gate on both: the harness driver AND the row identity
    // attributes the assertions read. This skip records "no evidence for Req 7",
    // never "Req 7 holds" (I-7).
    const rowIdentityRendered = await page.evaluate(
      () => document.querySelector("[data-decision-row]") !== null,
    );
    if (!(await replayHarnessReady(page)) || !rowIdentityRendered) {
      test.skip(
        true,
        "Req 7 reconciliation is unmeasured: the decision surfaces render no " +
          "[data-decision-row]/[data-decision-status] identity, src/lib/reconcile.ts is not on " +
          "the production path, and the harness has no replay-plan driver. This is a SKIP, not " +
          "a PASS (see the header ratchet).",
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
