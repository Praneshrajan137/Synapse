import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// P0 smoke: every primary Surface renders itself, and axe judges that surface (FE-INV-011).
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
] as const;

type Route = (typeof ROUTES)[number];

// Each surface's own h1, rendered on mount before any of its data arrives: PageHeader's title,
// or the Override Cockpit's h1; Steering and Demo Theater read theirs from their i18n catalog's
// "title". <main> alone proves nothing, because it is the Shell's and stays visible under the
// boot splash, "Insufficient authority" and a lazy surface's loading fallback alike. A typed
// record, so a route added above without its heading fails tsconfig.spec.json's type check.
const SURFACE_HEADING: Readonly<Record<Route, string>> = {
  "/": "Mission Control",
  "/markets": "Live Markets",
  "/operations": "Operations",
  "/cockpit": "Override Cockpit",
  "/ingress": "Ingress Console",
  "/decisions": "Decision Theater",
  "/agents": "Agent Council",
  "/twin": "Twin Lab",
  "/audit": "Audit Vault",
  "/steering": "Steering",
  "/demo": "Demo Theater",
};

// RouteGuard's boot splash (i18n/en/common.json "auth.signing_in"). RouteGuard renders either
// the splash or the surface, so the heading check already excludes it there; this check is for
// a splash rendered anywhere else on the page.
const BOOT_SPLASH = "Connecting to the console…";

// Access: a reloaded admin session whose gateway is unreachable. Of ADR-057's boot states it is
// the only one in which RouteGuard admits all eleven surfaces: an anonymous visitor reads at
// viewer rank and a preview grant is never above ops, so /agents and /twin (engineer), and
// without an `act` grant /cockpit, /ingress and /steering (ops), would show "Insufficient
// authority" instead. The store persists the role, never the token, so the boot hook still
// asks GET /api/v1/auth/mode. The e2e job's `pnpm preview` has no backend, its proxy answers
// 500, and after its retries the hook leaves the seeded role in place. A gateway that answered
// would swap the role for a preview grant, and the heading check would then fail on those
// routes, never pass. The seed is the shape zustand `persist` rehydrates, as in cockpit.spec.ts.
test.beforeEach(async ({ page }) => {
  // Motion at rest, as Storybook's runner and the visual gate emulate it: the constellation's
  // nodes spring in from opacity 0, and an axe scan taken mid-spring judges a transient frame.
  await page.emulateMedia({ reducedMotion: "reduce" });
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

for (const route of ROUTES) {
  test(`route ${route} renders and is a11y-clean @a11y`, async ({ page }) => {
    const name = SURFACE_HEADING[route];
    const main = page.getByRole("main");
    const heading = main.getByRole("heading", { level: 1, name, exact: true });

    await page.goto(route);
    // The route's own surface, and nothing in its place, before axe reads the page: its h1
    // inside <main>, the URL still this path (not /login, and not the "/" the router's
    // catch-all falls back to), and no boot splash anywhere.
    await expect(heading, `${route} did not render its own surface`).toBeVisible();
    expect(new URL(page.url()).pathname, `${route} navigated away`).toBe(route);
    await expect(page.getByText(BOOT_SPLASH)).toHaveCount(0);

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();

    // Still that surface after the scan, so nothing replaced it while axe was reading.
    await expect(heading, `${route} lost its surface during the scan`).toBeVisible();
    expect(results.violations).toEqual([]);
  });
}
