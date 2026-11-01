import { type Locator, type Page, expect, test } from "@playwright/test";

import {
  DECK_INFO,
  DECK_RISK,
  DECK_RISK_SOFT,
  DECK_WARN,
} from "../../src/visualization/deck-gl/palette";

/**
 * Spatial_Visualization correctness in a real browser (Req 10, FE-INV-063).
 *
 * The two Spatial_Visualizations are the deck.gl/MapLibre living map (Mission Control, `/`) and
 * the sigma/graphology supply-network graph (Twin Lab, `/twin`). Req 10 covers what jsdom cannot
 * show: a WebGL context, and token values as a browser resolves them.
 *
 *   - Req 10.1. Each surface gets a WebGL context and renders with no uncaught error. The context
 *     is observed: an init script marks every canvas a WebGL context is created on, and the test
 *     looks for a marked canvas inside the surface's role=img region.
 *   - Req 10.2. The living map paints with the token values the Console resolves. The tuples are
 *     imported from `visualization/deck-gl/palette.ts`, where the map's layers take their colour,
 *     so a palette that drifts from the tokens fails here. The supply graph colours nodes by type
 *     (`lib/supply-graph.ts`), which is not agent, tier or confidence data, so Req 10.2 sets it no
 *     condition and it has no case here.
 *   - Req 10.3. A forced WebGL init failure renders the surface's own error Universal_State with a
 *     retry affordance, never a blank canvas.
 *   - Req 10.4. The non-spatial equivalent takes keyboard focus and opens from the keyboard, and
 *     every loading moment of the surface shows the loading Universal_State beside it. The loading
 *     Universal_State is the block `UniversalStateView` renders (`data-universal-state="loading"`),
 *     the DOM contract the fault-transition spec and the harness read. A bare `aria-busy`
 *     skeleton is a loading placeholder, not that state.
 *
 * Where it runs: `playwright.harness.config.ts`, against the e2e-mode build
 * (`pnpm build:e2e && pnpm test:e2e:harness`). The harness global seeds the fixtures (Req 10.5)
 * and forces the WebGL failure, and that project's launch switches give the GPU-less runner
 * software WebGL (SwiftShader). Nothing here skips: a missing harness, a session that did not
 * hold, or a token that did not resolve each fails with a message naming the cause (I-7).
 *
 * Each test seeds a signed-in admin session as the other harness specs do; the harness answers
 * GET /api/v1/auth/mode as `authenticated`, so RouteGuard opens the surface.
 *
 * Like the other e2e specs this stays out of the app's `@`-alias module graph. Its one import from
 * `src/` is `palette.ts`, which imports nothing.
 */

const SCENARIO_ID = "spatial.visualization-correctness";

/** Set by the init script on every canvas a WebGL context has been created on. */
const WEBGL_MARK = "data-e2e-webgl-context";

/** Set on `<html>` once a visible loading Universal_State sits beside the non-spatial equivalent. */
const LOADING_STATE_SEEN = "data-e2e-spatial-loading-state-seen";

/** Set on `<html>`, to its text, once a visible loading placeholder there is not that state. */
const LOADING_PLACEHOLDER_SEEN = "data-e2e-spatial-loading-placeholder";

const HARNESS_ABSENT =
  "is absent from window.__atlasHarness: run this suite against the e2e-mode build " +
  "(pnpm build:e2e && pnpm test:e2e:harness)";

/** The two hooks of `spec/effectiveness/harness.ts` this spec calls. */
interface SpatialHarness {
  readonly seedScenario: (scenarioId: string) => Promise<void>;
  readonly failWebGL: (surfaceId: string) => Promise<void>;
}

interface SpatialSurface {
  readonly kind: "geospatial" | "network-graph";
  readonly surfaceId: string;
  readonly path: string;
  /** The accessible name of the role=img region the WebGL canvases render in. */
  readonly canvasLabel: RegExp;
  /** The text of the non-spatial equivalent's `<summary>`. */
  readonly nonSpatialSummary: RegExp;
  /** The `label` the surface gives its SpatialErrorBoundary, which names the error copy. */
  readonly boundaryLabel: string;
}

const LIVING_MAP: SpatialSurface = {
  kind: "geospatial",
  surfaceId: "mission-control",
  path: "/",
  canvasLabel: /live map$/,
  nonSpatialSummary: /^Map data as a table/,
  boundaryLabel: "living map",
};

const SUPPLY_GRAPH: SpatialSurface = {
  kind: "network-graph",
  surfaceId: "twin-lab",
  path: "/twin",
  canvasLabel: /^Supply network:/,
  nonSpatialSummary: /^Supply network as a table/,
  boundaryLabel: "supply network",
};

const SPATIAL_SURFACES: readonly SpatialSurface[] = [LIVING_MAP, SUPPLY_GRAPH];

/**
 * The tokens the living map's layers paint with (`visualization/deck-gl/layers.ts`), each beside
 * the palette tuple the layer is handed. The fourth channel is the layer's alpha, not the token's.
 */
const MAP_TOKEN_ENCODINGS: readonly {
  readonly cssVar: string;
  readonly paints: readonly number[];
  readonly encodes: string;
}[] = [
  { cssVar: "--syn-signal-info", paints: DECK_INFO, encodes: "a healthy route's arc end" },
  { cssVar: "--syn-signal-warning", paints: DECK_WARN, encodes: "a congested store" },
  {
    cssVar: "--syn-signal-danger",
    paints: DECK_RISK,
    encodes: "a saturated store and a freshness-violating route's arc start",
  },
  {
    cssVar: "--syn-confidence-risk",
    paints: DECK_RISK_SOFT,
    encodes: "a freshness-violating route's arc end",
  },
];

/**
 * Runs in the page before any app script. Each WebGL context request goes to the browser's own
 * `getContext` unchanged; when it returns a context, the canvas gets `mark`. The harness's
 * `failWebGL` wraps this function in turn, so a forced failure throws before any context exists
 * and marks nothing.
 */
function markWebGLCanvases(mark: string): void {
  const browserGetContext = HTMLCanvasElement.prototype.getContext;
  function recording(this: HTMLCanvasElement, contextId: string, ...rest: unknown[]): unknown {
    const context = (
      browserGetContext as (this: HTMLCanvasElement, id: string, ...args: unknown[]) => unknown
    ).call(this, contextId, ...rest);
    if (context !== null && /^(?:webgl2?|experimental-webgl)$/.test(contextId)) {
      this.setAttribute(mark, contextId);
    }
    return context;
  }
  HTMLCanvasElement.prototype.getContext =
    recording as typeof HTMLCanvasElement.prototype.getContext;
}

/**
 * Runs in the page before any app script. On every DOM change it reads the region that holds the
 * non-spatial equivalent whose `<summary>` matches `summary` (that `<details>` element's parent,
 * where LivingMap and TwinLab render the spatial boundary beside it) and records on `<html>`:
 * `seenMark` once a visible loading Universal_State is in that region, and `placeholderMark`,
 * set to its text, once a visible `aria-busy` placeholder is there while no visible loading
 * Universal_State is. Visibility matters because a suspended update keeps the previous content in
 * the DOM under `display: none`.
 */
function watchSpatialLoading(args: {
  readonly summary: string;
  readonly seenMark: string;
  readonly placeholderMark: string;
}): void {
  const pattern = new RegExp(args.summary);
  const visibleIn = (region: Element, selector: string): Element | null =>
    Array.from(region.querySelectorAll(selector)).find((element) => element.checkVisibility()) ??
    null;
  const inspect = (): void => {
    const root = document.documentElement;
    for (const summary of Array.from(document.querySelectorAll("summary"))) {
      if (!pattern.test((summary.textContent ?? "").trim())) continue;
      const region = summary.closest("details")?.parentElement ?? null;
      if (region === null) continue;
      if (visibleIn(region, '[data-universal-state="loading"]') !== null) {
        root.setAttribute(args.seenMark, "true");
        continue;
      }
      const placeholder = visibleIn(region, '[aria-busy="true"]');
      if (placeholder !== null && !root.hasAttribute(args.placeholderMark)) {
        root.setAttribute(args.placeholderMark, (placeholder.textContent ?? "").trim());
      }
    }
  };
  new MutationObserver(inspect).observe(document, {
    attributeFilter: ["aria-busy", "data-universal-state"],
    attributes: true,
    childList: true,
    subtree: true,
  });
}

/**
 * Open a surface and wait for its non-spatial equivalent, which renders only inside the guarded
 * route, then return that equivalent's `<summary>`. A session that did not hold sends the page to
 * /login, and this fails there naming that cause instead of skipping (I-7).
 */
async function openSurface(page: Page, surface: SpatialSurface): Promise<Locator> {
  await page.goto(surface.path);
  const summary = page.locator("summary").filter({ hasText: surface.nonSpatialSummary }).first();
  await expect(
    summary,
    `${surface.path} never rendered its non-spatial equivalent; a page on /login means the ` +
      "seeded admin session did not hold",
  ).toBeVisible();
  await expect(page, "RouteGuard sent the seeded admin session to /login").not.toHaveURL(
    /\/login/,
  );
  return summary;
}

/** Seed the scenario's deterministic geospatial and network-graph fixtures (Req 10.5). */
async function seedSpatialFixtures(page: Page): Promise<void> {
  const seeded = await page.evaluate(async (scenarioId) => {
    const harness = (window as unknown as { __atlasHarness?: Partial<SpatialHarness> })
      .__atlasHarness;
    const seedScenario = harness?.seedScenario;
    if (seedScenario === undefined) return false;
    await seedScenario(scenarioId);
    return true;
  }, SCENARIO_ID);
  expect(seeded, `seedScenario ${HARNESS_ABSENT}`).toBe(true);
}

/** Make the surface's next WebGL init throw, then re-enter its route (`harness.failWebGL`). */
async function forceWebGLFailure(page: Page, surfaceId: string): Promise<void> {
  const forced = await page.evaluate(async (id) => {
    const harness = (window as unknown as { __atlasHarness?: Partial<SpatialHarness> })
      .__atlasHarness;
    const failWebGL = harness?.failWebGL;
    if (failWebGL === undefined) return false;
    await failWebGL(id);
    return true;
  }, surfaceId);
  expect(forced, `failWebGL ${HARNESS_ABSENT}`).toBe(true);
}

/** The canvases in the surface's role=img region that hold a WebGL context. */
function webglCanvases(page: Page, surface: SpatialSurface): Locator {
  return page.getByRole("img", { name: surface.canvasLabel }).locator(`canvas[${WEBGL_MARK}]`);
}

/** The error Universal_State rendered by the surface's own SpatialErrorBoundary. */
function boundaryError(page: Page, surface: SpatialSurface): Locator {
  return page
    .locator('[data-universal-state="error"]')
    .filter({ hasText: `The ${surface.boundaryLabel} failed to load` });
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem(
      "synapse.session",
      JSON.stringify({
        state: { role: "admin", operatorTokenRef: "e2e-operator" },
        version: 0,
      }),
    );
  });
  await page.addInitScript(markWebGLCanvases, WEBGL_MARK);
});

test.describe("Spatial visualization correctness (Req 10)", () => {
  for (const surface of SPATIAL_SURFACES) {
    test.describe(`${surface.surfaceId} (${surface.kind})`, () => {
      test("FE-INV-063: WebGL smoke: a WebGL context initializes and the surface renders with no uncaught error (Req 10.1)", async ({
        page,
      }) => {
        const pageErrors: string[] = [];
        page.on("pageerror", (error) => {
          pageErrors.push(error.message);
        });

        await openSurface(page, surface);
        await seedSpatialFixtures(page);

        await expect(
          page.getByRole("img", { name: surface.canvasLabel }),
          `the ${surface.boundaryLabel} never rendered its role=img region`,
        ).toBeVisible();
        await expect
          .poll(() => webglCanvases(page, surface).count(), {
            message:
              `no canvas in the ${surface.boundaryLabel} holds a WebGL context; this project's ` +
              "SwiftShader switches make one available, so the context was refused or never " +
              "requested",
          })
          .toBeGreaterThan(0);
        await expect(
          boundaryError(page, surface),
          `the ${surface.boundaryLabel} rendered its error state although WebGL was available`,
        ).toHaveCount(0);
        expect(
          pageErrors,
          `uncaught error(s) while the ${surface.boundaryLabel} rendered: ${pageErrors.join("; ")}`,
        ).toEqual([]);
      });

      test("FE-INV-063: a WebGL init failure renders the error Universal_State with a retry affordance, never a blank canvas (Req 10.3)", async ({
        page,
      }) => {
        await openSurface(page, surface);
        await seedSpatialFixtures(page);
        await forceWebGLFailure(page, surface.surfaceId);

        const errorState = boundaryError(page, surface);
        await expect(
          errorState,
          `after a forced WebGL init failure the ${surface.boundaryLabel} rendered no error ` +
            `Universal_State ("The ${surface.boundaryLabel} failed to load"), so its canvas is blank`,
        ).toBeVisible();
        await expect(errorState).toHaveAttribute("role", "alert");
        await expect(
          errorState.getByRole("button", { name: /retry/i }),
          `the ${surface.boundaryLabel} error state carries no retry affordance`,
        ).toBeVisible();
      });

      test("FE-INV-063: the non-spatial equivalent takes keyboard focus and opens from the keyboard (Req 10.4)", async ({
        page,
      }) => {
        const summary = await openSurface(page, surface);

        await summary.focus();
        await expect(
          summary,
          "the non-spatial equivalent's summary does not take keyboard focus",
        ).toBeFocused();
        await summary.press("Enter");
        await expect(
          summary.locator("xpath=ancestor::details[1]"),
          "Enter on the summary did not open the non-spatial equivalent",
        ).toHaveJSProperty("open", true);
      });

      test("FE-INV-063: every loading moment shows the loading Universal_State beside the non-spatial equivalent (Req 10.4)", async ({
        page,
      }) => {
        await page.addInitScript(watchSpatialLoading, {
          summary: surface.nonSpatialSummary.source,
          seenMark: LOADING_STATE_SEEN,
          placeholderMark: LOADING_PLACEHOLDER_SEEN,
        });

        await openSurface(page, surface);
        await seedSpatialFixtures(page);
        // The visualization has mounted, so every loading moment of this page load has passed.
        await expect(
          page.getByRole("img", { name: surface.canvasLabel }),
          `the ${surface.boundaryLabel} never finished loading`,
        ).toBeVisible();

        const html = page.locator("html");
        const placeholder = await html.getAttribute(LOADING_PLACEHOLDER_SEEN);
        expect(
          await html.getAttribute(LOADING_STATE_SEEN),
          `while the ${surface.boundaryLabel} loaded, no loading Universal_State ` +
            '([data-universal-state="loading"]) rendered beside its non-spatial equivalent' +
            (placeholder === null ? "" : `; the region showed "${placeholder}" instead`),
        ).toBe("true");
        expect(
          placeholder,
          `while the ${surface.boundaryLabel} loaded, its region showed a loading placeholder ` +
            `that is not the loading Universal_State: "${placeholder ?? ""}"`,
        ).toBeNull();
      });
    });
  }

  test("FE-INV-063: the living map paints with the token values the Console resolves, in the default dark theme (Req 10.2)", async ({
    page,
  }) => {
    await openSurface(page, LIVING_MAP);
    await seedSpatialFixtures(page);
    await expect
      .poll(() => webglCanvases(page, LIVING_MAP).count(), {
        message: "the living map holds no WebGL context, so no rendered map is being checked",
      })
      .toBeGreaterThan(0);
    // The palette mirrors the dark theme, the Console's default. Another theme is outside this
    // claim: the palette is static, so it would need its own case.
    await expect(
      page.locator("html"),
      "the Console did not open in its default dark theme",
    ).toHaveAttribute("data-theme", "dark");

    const resolved = await page.evaluate(
      (names) => {
        const style = getComputedStyle(document.documentElement);
        return names.map((name) => style.getPropertyValue(name).trim());
      },
      MAP_TOKEN_ENCODINGS.map((encoding) => encoding.cssVar),
    );

    for (const [index, encoding] of MAP_TOKEN_ENCODINGS.entries()) {
      const value = resolved[index] ?? "";
      expect(
        value,
        `${encoding.cssVar} resolved to nothing: the token stylesheet (src/styles/tokens.css) ` +
          "did not apply in this bundle, so the map's palette has nothing to match",
      ).not.toBe("");
      const rgb = encoding.paints.slice(0, 3);
      expect(
        value.split(/\s+/).map(Number),
        `the living map paints ${encoding.encodes} with ${rgb.join(" ")}, but the Console ` +
          `resolves ${encoding.cssVar} to "${value}"`,
      ).toEqual(rgb);
    }
  });
});
