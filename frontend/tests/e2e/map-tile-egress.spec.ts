import { type Page, expect, test } from "@playwright/test";

/**
 * FE-INV-020 (I-1): map tiles come from the self-hosted PMTiles archive, and while a map surface
 * loads no request leaves the app's own origin, so none reaches Mapbox or Google.
 *
 * Observed at the browser's network edge, not read from the style JSON:
 *
 *   - `context.on("request")` reports every request the browser context makes: the page's own,
 *     its dedicated workers' (maplibre parses tiles in one), and the MSW service worker's
 *     pass-through fetches.
 *   - `page.on("websocket")` reports every socket the page opens. Under the harness the firehose
 *     socket is a scripted double, so none is expected; any that appears is checked too.
 *
 * Non-vacuity. A map that never loaded its style requests nothing and would pass the egress
 * check, so the test first waits for a request to the archive the basemap is configured with:
 * `CityMap.tsx` passes `import.meta.env.VITE_TILES_URL ?? "/tiles/india.pmtiles"` to
 * `buildBasemapStyle` (`basemap.ts`) as its only `pmtiles://` source, `.env.example` sets that
 * same path, and `.env.e2e` sets no override. maplibre issues that request only once it has a
 * WebGL2 context, which is why this spec runs in the harness project: its launch switches give
 * the GPU-less runner software WebGL. In production the archive's origin is the project nginx
 * (`frontend/nginx.conf`, `location /tiles/`); here it is the preview server.
 *
 * The archive's response is not part of the claim. `dist-e2e/` ships no tiles, so the preview
 * server answers the path with its SPA fallback page (or a 404), pmtiles fails to read a header,
 * and no tile-range request follows. That is acceptable for an egress claim, which is about where
 * requests go. Whether a drawn map decodes tiles is not observed in CI: no job serves the archive.
 *
 * The window. Requests are recorded from navigation until the archive has been requested and no
 * new request has started for QUIET_MS, capped at SETTLE_CAP_MS. A later request is outside this
 * claim.
 *
 * It calls no harness hook. Like the other e2e specs it stays out of the app's module graph.
 */

/** The archive the basemap is configured with (see the header). */
const PMTILES_ARCHIVE_PATH = "/tiles/india.pmtiles";

/** The hosts FE-INV-020 names. A request to one of them, or to a subdomain of one, fails. */
const FORBIDDEN_HOSTS: readonly string[] = [
  "mapbox.com",
  "googleapis.com",
  "google.com",
  "gstatic.com",
];

/**
 * Every surface that mounts a basemap. Only Mission Control does (LivingMap -> LivingMapCanvas ->
 * CityMap); the Twin Lab supply graph is sigma and loads no tiles.
 */
const MAP_SURFACES: readonly {
  readonly surfaceId: string;
  readonly path: string;
  /** The accessible name of CityMap's role=img container. */
  readonly mapLabel: RegExp;
}[] = [{ surfaceId: "mission-control", path: "/", mapLabel: /live map$/ }];

const ARCHIVE_TIMEOUT_MS = 20_000;
const QUIET_MS = 1_500;
const SETTLE_CAP_MS = 15_000;

/**
 * The origin a request to `url` reaches, or null when the URL never leaves the page (`data:`,
 * `about:`). `ws:` and `wss:` are read as the `http:` and `https:` origin they upgrade from, and
 * a `blob:` URL carries the origin that created it. A URL that does not parse is returned as
 * itself, so it is reported rather than assumed local.
 */
function originReached(url: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  if (parsed.protocol === "data:" || parsed.protocol === "about:") return null;
  if (parsed.protocol === "ws:") return `http://${parsed.host}`;
  if (parsed.protocol === "wss:") return `https://${parsed.host}`;
  return parsed.origin;
}

/** True when `url` is a request for the configured archive on the app's own origin. */
function isArchiveRequest(url: string, appOrigin: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.origin === appOrigin && parsed.pathname === PMTILES_ARCHIVE_PATH;
  } catch {
    return false;
  }
}

/** True when `url`'s host is one FE-INV-020 forbids, or a subdomain of one. */
function namesForbiddenHost(url: string): boolean {
  let hostname: string;
  try {
    hostname = new URL(url).hostname;
  } catch {
    return false;
  }
  return FORBIDDEN_HOSTS.some((host) => hostname === host || hostname.endsWith(`.${host}`));
}

/** Wait until no new request has started for QUIET_MS, or until SETTLE_CAP_MS has passed. */
async function settle(page: Page, requested: readonly string[]): Promise<void> {
  const startedAt = Date.now();
  let seen = requested.length;
  let quietSince = startedAt;
  while (Date.now() - quietSince < QUIET_MS && Date.now() - startedAt < SETTLE_CAP_MS) {
    await page.waitForTimeout(100);
    if (requested.length !== seen) {
      seen = requested.length;
      quietSince = Date.now();
    }
  }
}

test.beforeEach(async ({ page }) => {
  // A signed-in admin session, seeded the way the other harness specs seed it. The harness
  // answers GET /api/v1/auth/mode as `authenticated`, so an anonymous page would go to /login.
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

for (const surface of MAP_SURFACES) {
  test(`FE-INV-020: ${surface.surfaceId} requests its PMTiles archive and nothing outside the app's origin while its map loads`, async ({
    page,
  }) => {
    const requested: string[] = [];
    page.context().on("request", (request) => {
      requested.push(request.url());
    });
    const sockets: string[] = [];
    page.on("websocket", (socket) => {
      sockets.push(socket.url());
    });

    await page.goto(surface.path);
    const appOrigin = new URL(page.url()).origin;

    await expect(
      page.getByRole("img", { name: surface.mapLabel }),
      `${surface.path} never mounted its map; a page on /login means the seeded admin session ` +
        "did not hold",
    ).toBeVisible();
    await expect
      .poll(() => requested.filter((url) => isArchiveRequest(url, appOrigin)).length, {
        message:
          `no request reached ${appOrigin}${PMTILES_ARCHIVE_PATH}: maplibre never loaded its ` +
          "pmtiles source (no WebGL2 context, a failed canvas chunk, or an unregistered pmtiles " +
          "protocol), so this run observed nothing about where tiles come from",
        timeout: ARCHIVE_TIMEOUT_MS,
      })
      .toBeGreaterThan(0);
    await settle(page, requested);

    const reached = [...requested, ...sockets];
    const offOrigin = reached.filter((url) => {
      const origin = originReached(url);
      return origin !== null && origin !== appOrigin;
    });
    expect(offOrigin, `request(s) left ${appOrigin} while the map loaded`).toEqual([]);
    // Implied by the check above on any origin that is not itself one of these hosts. Kept so a
    // failure names the host FE-INV-020 forbids.
    expect(
      reached.filter(namesForbiddenHost),
      "request(s) reached Mapbox or Google, which FE-INV-020 forbids",
    ).toEqual([]);
  });
}
