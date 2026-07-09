import { expect, test } from "@playwright/test";

/**
 * Visual_Regression_Gate — deterministic screenshot diffing (Req 14.1–14.6, 20.2).
 *
 * Captures deterministic screenshots of a defined set of key Surfaces across
 * every Theme_Mode and compares each against its committed baseline, using ONLY
 * Playwright's built-in `toHaveScreenshot()` diffing — a $0-cost / OSS tool
 * already in the stack (`@playwright/test`). No paid visual-diffing SaaS is
 * used (Req 14.6, 20.2).
 *
 * What each acceptance criterion maps to here:
 *
 *   - Req 14.1 — screenshots are captured under a FIXED viewport, theme, and
 *     seed. The viewport is pinned per test; the theme is forced through the
 *     persisted `synapse.theme` store before the app boots; the seed is fixed
 *     by freezing the page clock (so every relative-time render is stable) and,
 *     when the Effectiveness_Harness is wired, by seeding its deterministic
 *     fixtures.
 *   - Req 14.2 — `toHaveScreenshot()` fails the check when the rendered diff
 *     exceeds the threshold defined in `playwright.config.ts`
 *     (`expect.toHaveScreenshot`), and the assertion message names the changed
 *     Surface + Theme_Mode via the snapshot name (`<surface>-<theme>`).
 *   - Req 14.3 — determinism guards keep the gate non-flaky: fixed fonts
 *     (font-smoothing pinned + web-font load awaited), disabled animation
 *     (reduced-motion emulation + an all-animations-off stylesheet +
 *     `animations: "disabled"`), a frozen clock, and masked volatile regions
 *     (live WebGL canvases and `aria-live` streaming regions).
 *   - Req 14.4 — an approved visual change advances the committed baseline via
 *     `pnpm test:e2e:visual:update` (Playwright `--update-snapshots`); see
 *     `tests/e2e/visual/README.md`.
 *   - Req 14.5 — the target matrix covers at least one Surface per Theme_Mode
 *     (light via Decision Theater, dark via Override Cockpit, hc via Audit
 *     Vault) so a Chromatic_Token regression in ANY mode is caught. (Mission
 *     Control is a tracked ratchet — see VISUAL_TARGETS.)
 *
 * Graceful-skip convention: harness-seeded fixtures are optional. When the
 * Effectiveness_Harness global is not wired (or the route guard redirects to
 * login without a session fixture) the affected capture skips cleanly rather
 * than failing — the same convention as the other harness-dependent e2e specs
 * (see firehose-stress.resilience.spec.ts / spatial-visualization.spec.ts).
 */

type ThemeMode = "light" | "dark" | "hc";

interface VisualTarget {
  /** Surface id, used (with the theme) as the snapshot name. */
  readonly surface: string;
  /** Route path for the Surface. Mirrors `src/app/primary-surfaces.ts`. */
  readonly path: string;
  /** Theme_Mode to force before boot (Req 14.1, 14.5). */
  readonly theme: ThemeMode;
}

/**
 * The defined set of key Surfaces × Theme_Modes (Req 14.1, 14.5). The three
 * Theme_Modes are each exercised across real, token-dense keystone Surfaces:
 * Override Cockpit (dark), Decision Theater (light), Audit Vault (hc).
 *
 * RATCHET — mission-control (`/`) is intentionally NOT captured here yet. Against
 * the backendless `pnpm preview`, its live map (WebGL) + firehose + data-hook
 * loading/error states re-render continuously (every /api call proxy-errors), so
 * `toHaveScreenshot` cannot reach a stable capture and the shot flakes even in
 * update-mode. Re-add mission-control once its volatile regions are fully frozen
 * (deterministic MSW seed for the map/firehose) so a Chromatic_Token regression
 * on `/` is caught in all three modes. Theme coverage (Req 14.5) is preserved by
 * the three keystone Surfaces below.
 */
const VISUAL_TARGETS: readonly VisualTarget[] = [
  { surface: "override-cockpit", path: "/cockpit", theme: "dark" },
  { surface: "decision-theater", path: "/decisions", theme: "light" },
  { surface: "audit-vault", path: "/audit", theme: "hc" },
];

/** Fixed viewport for every capture (Req 14.1). */
const VIEWPORT = { width: 1280, height: 800 } as const;

/** Fixed instant so every `fmt.relativeTime(...)` render is deterministic (Req 14.1, 14.3). */
const FROZEN_TIME = new Date("2025-01-01T12:00:00.000Z");

/**
 * Optional Effectiveness_Harness seeding global. Mirrors the shape documented
 * in the other harness-dependent e2e specs; used only when present.
 */
interface AtlasHarness {
  seedScenario?(scenarioId: string): Promise<void>;
}
const VISUAL_SCENARIO_ID = "visual.regression-baseline";

test.beforeEach(async ({ page }) => {
  // Seed an authenticated session so RouteGuard passes (mirrors cockpit.spec.ts
  // / the resilience specs).
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

/** True iff the Effectiveness_Harness seeding global is present in the page. */
async function harnessReady(page: import("@playwright/test").Page): Promise<boolean> {
  return page.evaluate(
    () => typeof (window as unknown as { __atlasHarness?: unknown }).__atlasHarness === "object",
  );
}

/** Seed the deterministic visual fixtures when the harness is wired (Req 14.1 seed). */
async function seedIfPossible(page: import("@playwright/test").Page): Promise<void> {
  await page.evaluate(async (scenarioId) => {
    const harness = (window as unknown as { __atlasHarness?: AtlasHarness }).__atlasHarness;
    if (harness?.seedScenario) await harness.seedScenario(scenarioId);
  }, VISUAL_SCENARIO_ID);
}

test.describe("Visual regression gate (Req 14)", () => {
  for (const target of VISUAL_TARGETS) {
    test(`${target.surface} renders stably in ${target.theme} theme`, async ({ page }) => {
      // Req 14.1 — fixed viewport.
      await page.setViewportSize(VIEWPORT);

      // Req 14.3 — disabled animation: emulate reduced-motion so framer-motion
      // and CSS transitions collapse to their resting state.
      await page.emulateMedia({ reducedMotion: "reduce" });

      // Req 14.1 — force the Theme_Mode before the app boots by writing the
      // persisted zustand store; `providers.tsx` applies it via `applyTheme`
      // on mount so `<html data-theme>` matches the target.
      await page.addInitScript((theme: string) => {
        localStorage.setItem(
          "synapse.theme",
          JSON.stringify({ state: { theme }, version: 0 }),
        );
      }, target.theme);

      // Req 14.1 / 14.3 — freeze the clock so `fmt.relativeTime(...)` and any
      // `new Date()` render to a fixed, seed-stable value on every run.
      await page.clock.setFixedTime(FROZEN_TIME);

      await page.goto(target.path);
      if (page.url().includes("/login")) {
        test.skip(true, "needs an authenticated session fixture");
      }
      await expect(page.locator("main")).toBeVisible();

      // Seed deterministic fixtures when the harness is wired; otherwise the
      // Surface renders its deterministic empty/error Universal_State, which is
      // itself a stable baseline (graceful-skip convention).
      if (await harnessReady(page)) await seedIfPossible(page);

      // Confirm the forced Theme_Mode actually applied before we capture.
      await expect(page.locator("html")).toHaveAttribute("data-theme", target.theme);

      // Req 14.3 — fixed fonts + disabled animation belt-and-braces: pin
      // font-smoothing and hard-stop every animation/transition/caret so
      // sub-pixel and timing jitter cannot flake the diff.
      await page.addStyleTag({
        content: `
          *, *::before, *::after {
            animation-duration: 0s !important;
            animation-delay: 0s !important;
            transition-duration: 0s !important;
            transition-delay: 0s !important;
            caret-color: transparent !important;
            scroll-behavior: auto !important;
          }
          html { -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision; }
        `,
      });

      // Req 14.3 — fixed fonts: wait for web fonts to finish loading so glyph
      // fallback swaps cannot shift the baseline.
      await page.evaluate(async () => {
        if (document.fonts?.ready) await document.fonts.ready;
      });

      // Req 14.3 — mask volatile regions. Live WebGL canvases (deck.gl living
      // map, sigma supply graph) render non-deterministically, and `aria-live`
      // regions carry streaming/live data; both are masked so only stable,
      // token-driven layout is diffed.
      const masks = [
        page.locator("canvas"),
        page.locator('[aria-live="polite"]'),
        page.locator('[aria-live="assertive"]'),
      ];

      // Req 14.2 — compare against the committed baseline; the threshold is
      // defined in playwright.config.ts. The snapshot name encodes the Surface
      // and Theme_Mode so a failing diff names exactly what changed.
      await expect(page).toHaveScreenshot(`${target.surface}-${target.theme}.png`, {
        fullPage: true,
        animations: "disabled",
        mask: masks,
      });
    });
  }
});
