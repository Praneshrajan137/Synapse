import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

/**
 * Assistive_Tech_Flow — scripted screen-reader walkthrough of resolving a live
 * escalation in the Override Cockpit (Req 15.1, 15.2, 15.6, 20.5).
 *
 * A real screen reader (NVDA / VoiceOver) cannot run in headless CI, so this
 * flow scripts the accessibility SEMANTICS that assistive technology actually
 * consumes — accessible names, roles, and live-region announcements — and
 * asserts an operator can, non-visually:
 *
 *   - Req 15.1 — PERCEIVE the escalation (the arrival live region names it and
 *     the active-escalation region carries an accessible name), PERCEIVE its
 *     guardrail violations (each conveyed as text: severity + code + message,
 *     never colour-only), and PERCEIVE/operate the override action affordances
 *     (Approve / Reject / Modify expose accessible names and key shortcuts).
 *   - Req 15.2 — when the override is performed, the action OUTCOME is announced
 *     through an appropriate live region so it reaches assistive technology.
 *
 * ── Honest ceiling (Req 15.6 / 20.5) ─────────────────────────────────────────
 * Every test on this report records the ceiling: a scripted Assistive_Tech_Flow
 * demonstrates OPERABILITY (the semantics assistive tech needs are present and
 * an operable path exists) but does NOT replace validation with real
 * assistive-technology users. Like the rest of the Effectiveness_Harness it is a
 * Scripted_Proxy — it proves a path exists and is operable, not that a human
 * using a screen reader comprehends it. Real effectiveness requires real-user
 * (RITE) testing with 3–5 assistive-technology operators.
 *
 * ── Harness wiring (REQUIRED — no graceful skip) ─────────────────────────────
 * Seeding a live escalation into the cockpit uses the documented in-browser
 * harness global implemented by `spec/effectiveness/harness.ts` (task 11.1):
 *
 *   interface AtlasHarness {
 *     seedScenario(scenarioId: string): Promise<void>;
 *   }
 *   declare global { interface Window { __atlasHarness?: AtlasHarness } }
 *
 * The global exists only in the e2e-mode build (AD-12), so this suite runs as
 * `pnpm build:e2e && pnpm test:e2e:harness` (`playwright.harness.config.ts`).
 * The static-semantics check (the non-visual escalation channels exist and the
 * surface is axe-clean) runs against the cockpit as it renders today. The
 * seeded-escalation walkthrough now FAILS when the harness cannot seed an
 * escalation instead of skipping — an unwalked flow is not an operable one
 * (I-7).
 */

/**
 * The honest ceiling recorded on EVERY test's report (Req 15.6, 20.5). Kept
 * verbatim so this suite and the effectiveness artifacts state the same caveat.
 */
const CEILING =
  "Assistive_Tech_Flow (Scripted_Proxy): this scripted screen-reader walkthrough demonstrates " +
  "OPERABILITY — the accessible names, roles, and live-region announcements assistive technology " +
  "consumes are present and an operable path exists — but it does NOT replace validation with " +
  "real assistive-technology users. Real effectiveness requires real-user (RITE) testing with " +
  "3–5 operators using NVDA / VoiceOver.";

/**
 * The JTBD scenario that seeds a pending escalation into the cockpit (mirrors
 * the `jtbd.resolve-escalation` descriptor / task 3.1). Kept local so this
 * Playwright spec stays free of the app's `@`-alias module graph (same
 * convention as the sibling harness e2e specs).
 */
const SCENARIO_ID = "jtbd.resolve-escalation";

/** True iff the in-browser harness global is present. */
async function harnessReady(page: Page): Promise<boolean> {
  return page.evaluate(
    () => typeof (window as unknown as { __atlasHarness?: unknown }).__atlasHarness === "object",
  );
}

/** True iff the harness can seed a scenario into the page. */
async function canSeed(page: Page): Promise<boolean> {
  return page.evaluate(
    () =>
      typeof (window as unknown as { __atlasHarness?: { seedScenario?: unknown } }).__atlasHarness
        ?.seedScenario === "function",
  );
}

/** Seed the pending-escalation scenario when the harness is wired (Req 15.1). */
async function seedScenario(page: Page, scenarioId: string): Promise<void> {
  await page.evaluate(async (id) => {
    await (
      window as unknown as { __atlasHarness: { seedScenario(id: string): Promise<void> } }
    ).__atlasHarness.seedScenario(id);
  }, scenarioId);
}

/**
 * Record the honest ceiling on the test's report (Req 15.6, 20.5). Runs on
 * EVERY test — driven or skipped — so no assistive-tech artifact omits it.
 */
async function recordCeiling(testInfo: TestInfo): Promise<void> {
  testInfo.annotations.push({ type: "assistive-tech-ceiling", description: CEILING });
  await testInfo.attach("assistive-tech-ceiling.txt", {
    body: CEILING,
    contentType: "text/plain",
  });
}

test.beforeEach(async ({ page }) => {
  // Seed an authenticated (admin) session so RouteGuard passes for /cockpit
  // (mirrors cockpit.spec.ts / the sibling harness e2e specs).
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

test.describe("Assistive_Tech_Flow — Override Cockpit (Req 15)", () => {
  test("exposes the escalation status non-visually and is axe-clean (Req 15.1)", async ({
    page,
  }, testInfo) => {
    // Req 15.6 / 20.5 — the honest ceiling is on EVERY report, first thing.
    await recordCeiling(testInfo);

    await page.goto("/cockpit");
    if (page.url().includes("/login")) {
      test.skip(true, "needs an authenticated session fixture");
    }
    await expect(page.locator("main")).toBeVisible();

    // The escalation-arrival channel is an ASSERTIVE live region so a screen
    // reader is interrupted with a newly-arrived escalation even while focus is
    // elsewhere on the surface (Req 15.1 — perceive the escalation non-visually).
    const arrival = page.getByTestId("escalation-arrival");
    await expect(arrival).toHaveAttribute("aria-live", "assertive");

    // The pending-count is a POLITE live region so the operator hears how many
    // escalations await judgement without an interruption.
    const politeStatus = page.locator('output[aria-live="polite"]');
    await expect(politeStatus.first()).toBeAttached();

    // axe verifies the accessible names/roles the screen reader relies on are
    // well-formed across the cockpit (wcag2a/2aa), matching the smoke matrix.
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(results.violations, "cockpit must be a11y-clean for assistive tech").toEqual([]);
  });

  test("screen-reader walkthrough: a seeded escalation, its violations, and the override outcome are perceivable non-visually (Req 15.1, 15.2)", async ({
    page,
  }, testInfo) => {
    // Req 15.6 / 20.5 — record the ceiling first, so it is present even when the
    // harness-dependent assertions below skip.
    await recordCeiling(testInfo);

    await page.goto("/cockpit");
    if (page.url().includes("/login")) {
      test.skip(true, "needs an authenticated session fixture");
    }
    await expect(page.locator("main")).toBeVisible();

    // Seeding a LIVE escalation (and answering the override POST) requires the
    // in-browser harness + its MSW worker (task 11.1). Its absence FAILS this
    // walkthrough rather than skipping it (I-7).
    expect(
      (await harnessReady(page)) && (await canSeed(page)),
      "window.__atlasHarness.seedScenario is absent: run the harness suite against the e2e-mode " +
        "build (pnpm build:e2e && pnpm test:e2e:harness)",
    ).toBe(true);
    await seedScenario(page, SCENARIO_ID);

    // ── Perceive the escalation (Req 15.1) ────────────────────────────────────
    // The active escalation is a region with an accessible name a screen reader
    // announces ("Active escalation <decision id>").
    const activeEscalation = page.getByRole("region", { name: /Active escalation/i });
    await expect(activeEscalation.first()).toBeVisible();

    // The assertive arrival region names the seeded escalation so it is
    // announced non-visually.
    await expect
      .poll(async () => (await page.getByTestId("escalation-arrival").textContent()) ?? "", {
        message: "arrival live region never named the seeded escalation",
      })
      .toMatch(/escalation arrived/i);

    // ── Perceive its guardrail violations (Req 15.1) ──────────────────────────
    // The guardrail-violations region is always rendered and carries an
    // accessible name; each violation is conveyed as TEXT (severity + code +
    // message), never colour-only, so it is perceivable non-visually.
    const violations = page.getByRole("region", { name: /Guardrail violations/i });
    await expect(violations.first()).toBeVisible();
    const violationText = (await violations.first().textContent()) ?? "";
    expect(violationText.trim().length, "guardrail-violations region conveyed no text").toBeGreaterThan(
      0,
    );

    // ── Perceive & operate the override action affordances (Req 15.1) ─────────
    // Each override action exposes an accessible name and its key shortcut, so a
    // screen-reader operator can find and operate it non-visually.
    const rejectButton = page.getByRole("button", { name: /Reject/i });
    await expect(rejectButton).toBeVisible();
    await expect(rejectButton).toHaveAttribute("aria-keyshortcuts", "R");
    await expect(page.getByRole("button", { name: /Approve/i })).toHaveAttribute(
      "aria-keyshortcuts",
      "A",
    );

    // ── Perform the override & hear the outcome (Req 15.2) ────────────────────
    // Open the reject dialog, give the mandatory reason, and commit — the same
    // path a keyboard/screen-reader operator takes.
    await rejectButton.click();
    const reason = page.getByRole("textbox", { name: /Reason for rejection/i });
    await expect(reason).toBeVisible();
    await reason.fill("Rejecting: the guardrail violation makes this action unsafe.");
    await page.getByRole("button", { name: /Commit reject/i }).click();

    // The override OUTCOME must be announced through an appropriate live region
    // so it reaches assistive technology (Req 15.2). Assert the outcome text
    // ("Override committed …") lands inside an announcing container — an element
    // (or ancestor) carrying aria-live or a status/alert role.
    await expect
      .poll(
        async () =>
          page.evaluate(() => {
            const rx = /override committed/i;
            const announcers = Array.from(
              document.querySelectorAll('[aria-live], [role="status"], [role="alert"], output'),
            );
            return announcers.some((el) => rx.test(el.textContent ?? ""));
          }),
        {
          message: "override outcome was not announced through a live region (Req 15.2)",
        },
      )
      .toBe(true);
  });
});
