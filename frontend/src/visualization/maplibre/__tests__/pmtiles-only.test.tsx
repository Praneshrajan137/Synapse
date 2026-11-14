import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// FE-INV-024 (I-1; atlas-console-elevation Req 7.2): the map renders only self-hosted PMTiles and
// registers no remote tile server. Asserted on what CityMap.tsx hands maplibre-gl when it mounts:
// the style basemap.ts's buildBasemapStyle builds from CityMap's tiles URL, and the protocols
// prepareMapLibre registers. jsdom has no WebGL2, so maplibre-gl is replaced by a recorder and the
// deck.gl overlay by nothing. CityMap, basemap.ts and pmtiles run unmocked.
//
// The recorder defines only the members CityMap and basemap.ts call today. Any other maplibre call
// (a source added after load, setRTLTextPlugin with a remote plugin URL) throws a TypeError here,
// so a new way of pointing the map elsewhere fails this suite instead of passing unexamined.
//
// Disclosed, not claimed: the style names one URL off the app's origin, its glyph endpoint on
// protomaps.github.io. Neither FE-INV-024 nor Req 7.2 speaks of glyphs, and maplibre fetches them
// only to lay out a symbol layer's text, which the style does not have. The last test holds that.

interface MapLibreLog {
  /** The set-up and construction calls, in order. */
  readonly calls: string[];
  /** Each protocol registered with maplibre, and the type of its handler. */
  readonly protocols: Array<{ readonly name: string; readonly handler: string }>;
  /** The options each maplibre Map was constructed with. */
  readonly mapOptions: unknown[];
}

const maplibre = vi.hoisted((): MapLibreLog => ({ calls: [], protocols: [], mapOptions: [] }));

vi.mock("maplibre-gl", () => {
  class MockMap {
    constructor(options: unknown) {
      maplibre.calls.push("Map");
      maplibre.mapOptions.push(options);
    }
    addControl(): this {
      return this;
    }
    flyTo(): this {
      return this;
    }
    remove(): void {}
  }
  class MockNavigationControl {
    readonly options: unknown;
    constructor(options: unknown) {
      this.options = options;
    }
  }
  return {
    Map: MockMap,
    NavigationControl: MockNavigationControl,
    setWorkerUrl: (): void => {
      maplibre.calls.push("setWorkerUrl");
    },
    addProtocol: (name: string, handler: unknown): void => {
      maplibre.calls.push("addProtocol");
      maplibre.protocols.push({ name, handler: typeof handler });
    },
  };
});
// The deck.gl overlay needs a WebGL2 context jsdom cannot give it.
vi.mock("@deck.gl/react", () => ({ DeckGL: (): null => null }));

/** The scheme the pmtiles protocol handles. */
const PMTILES = "pmtiles://";

/** The source types maplibre requests tiles for. */
const TILE_SOURCE_TYPES: ReadonlySet<string> = new Set(["vector", "raster", "raster-dem"]);

/** The hosts FE-INV-020 names, as frontend/tests/e2e/map-tile-egress.spec.ts lists them. */
const FORBIDDEN_HOSTS: readonly string[] = [
  "mapbox.com",
  "googleapis.com",
  "google.com",
  "gstatic.com",
];

/** A source the style declares: its id and its specification. */
interface StyleSource {
  readonly id: string;
  readonly spec: Record<string, unknown>;
}

/** A URL the style gives maplibre, with the style field it sits in. */
interface StyleUrl {
  readonly field: string;
  readonly url: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Mounts CityMap in a fresh module graph, so its once-per-page maplibre set-up runs again, and
 * unmounts it.
 */
async function mountCityMap(): Promise<void> {
  vi.resetModules();
  const { CityMap } = await import("../CityMap");
  render(<CityMap />).unmount();
}

/** The options CityMap gave maplibre's Map, which it builds once per mount. */
function constructedOptions(): Record<string, unknown> {
  expect(maplibre.mapOptions, "CityMap builds exactly one maplibre Map").toHaveLength(1);
  const [options] = maplibre.mapOptions;
  if (!isRecord(options)) throw new Error("maplibre's Map was constructed without options");
  return options;
}

/** The style object in those options. A style URL would hide its sources, so it fails here. */
function constructedStyle(): Record<string, unknown> {
  const { style } = constructedOptions();
  if (isRecord(style)) return style;
  throw new Error(`CityMap gave maplibre's Map a ${typeof style} style, not a style object`);
}

/** The sources the style declares. */
function sourcesOf(style: Record<string, unknown>): StyleSource[] {
  const sources: Record<string, unknown> = isRecord(style.sources) ? style.sources : {};
  const found: StyleSource[] = [];
  for (const [id, spec] of Object.entries(sources)) {
    if (isRecord(spec)) found.push({ id, spec });
  }
  return found;
}

/** The sources maplibre requests tiles from: vector, raster and raster-dem. */
function tileSourcesOf(style: Record<string, unknown>): StyleSource[] {
  return sourcesOf(style).filter(({ spec }) => TILE_SOURCE_TYPES.has(String(spec.type)));
}

/** The layers the style declares. */
function layersOf(style: Record<string, unknown>): Record<string, unknown>[] {
  return Array.isArray(style.layers) ? style.layers.filter(isRecord) : [];
}

/** The URLs one source names: its `url`, a GeoJSON `data` string, each `tiles` and `urls` entry. */
function sourceUrls({ id, spec }: StyleSource): StyleUrl[] {
  const found: StyleUrl[] = [];
  const take = (field: string, value: unknown): void => {
    const at = `sources.${id}.${field}`;
    if (typeof value === "string") found.push({ field: at, url: value });
  };
  take("url", spec.url);
  take("data", spec.data);
  for (const field of ["tiles", "urls"]) {
    const list = spec[field];
    if (Array.isArray(list)) {
      for (const [index, value] of list.entries()) take(`${field}[${index}]`, value);
    }
  }
  return found;
}

/** Every URL in the style: each source's, the sprite's, and the glyph endpoint. */
function styleUrls(style: Record<string, unknown>): StyleUrl[] {
  const found = sourcesOf(style).flatMap(sourceUrls);
  if (typeof style.glyphs === "string") found.push({ field: "glyphs", url: style.glyphs });
  const sprite = style.sprite;
  if (typeof sprite === "string") found.push({ field: "sprite", url: sprite });
  if (Array.isArray(sprite)) {
    for (const entry of sprite) {
      if (isRecord(entry) && typeof entry.url === "string") {
        found.push({ field: `sprite.${String(entry.id)}`, url: entry.url });
      }
    }
  }
  return found;
}

/**
 * Where a request for `url` goes. The page resolves it against its own address, and the pmtiles
 * protocol first strips its scheme (pmtiles 3.2.1, dist/index.js line 812:
 * `params.url.substr(10)`). Null when the address does not parse.
 */
function requestTarget(url: string): URL | null {
  const address = url.startsWith(PMTILES) ? url.slice(PMTILES.length) : url;
  try {
    return new URL(address, window.location.href);
  } catch {
    return null;
  }
}

/** True when a request for `url` stays on the app's own origin. An unparseable URL does not. */
function onAppOrigin(url: string): boolean {
  return requestTarget(url)?.origin === window.location.origin;
}

/** The URLs whose requests would leave the app's own origin. */
function offOrigin(urls: readonly StyleUrl[]): StyleUrl[] {
  return urls.filter(({ url }) => !onAppOrigin(url));
}

/** True when `url` reaches a host FE-INV-020 names, a subdomain of one, or Mapbox's own scheme. */
function namesForbiddenHost(url: string): boolean {
  if (url.startsWith("mapbox://")) return true;
  const hostname = requestTarget(url)?.hostname ?? "";
  return FORBIDDEN_HOSTS.some((host) => hostname === host || hostname.endsWith(`.${host}`));
}

/** A tile source's URLs that are not a pmtiles:// archive on the app's own origin. */
function notSelfHostedPmtiles(source: StyleSource): string[] {
  const urls = sourceUrls(source);
  if (urls.length === 0) return [`sources.${source.id} names no URL`];
  const misses: string[] = [];
  for (const { field, url } of urls) {
    if (!url.startsWith(PMTILES) || !onAppOrigin(url)) misses.push(`${field}: ${url}`);
  }
  return misses;
}

/** The ids of the style's symbol layers, the only layers maplibre fetches glyphs for. */
function symbolLayers(style: Record<string, unknown>): string[] {
  const ids: string[] = [];
  for (const layer of layersOf(style)) {
    if (layer.type === "symbol") ids.push(String(layer.id));
  }
  return ids;
}

describe("CityMap basemap configuration (FE-INV-024)", () => {
  beforeEach(() => {
    maplibre.calls.length = 0;
    maplibre.protocols.length = 0;
    maplibre.mapOptions.length = 0;
  });

  // Wrong if prepareMapLibre registered a second protocol (a remote tile scheme), dropped
  // pmtiles, or registered it only after the Map was built, when the style already needed it.
  it("FE-INV-024: CityMap registers the pmtiles protocol with maplibre, and no other, before it builds its map", async () => {
    await mountCityMap();
    expect(maplibre.protocols).toEqual([{ name: "pmtiles", handler: "function" }]);
    const registered = maplibre.calls.indexOf("addProtocol");
    expect(registered).toBeGreaterThanOrEqual(0);
    expect(maplibre.calls.indexOf("Map")).toBeGreaterThan(registered);
  });

  // Wrong if a tile source named an http(s) tile server or a TileJSON endpoint rather than a
  // pmtiles:// archive, or an archive on another origin (VITE_TILES_URL set to another host).
  it("FE-INV-024: every tile source in the style CityMap hands maplibre is a pmtiles:// archive on the app's own origin", async () => {
    await mountCityMap();
    const tileSources = tileSourcesOf(constructedStyle());
    // Non-vacuity: with no tile source, the check below would examine nothing and pass.
    expect(tileSources.length).toBeGreaterThan(0);
    expect(tileSources.flatMap(notSelfHostedPmtiles)).toEqual([]);
  });

  // Wrong if any URL in the style, the glyph endpoint and any sprite included, pointed at Mapbox
  // (mapbox:// or mapbox.com) or at one of Google's hosts.
  it("FE-INV-024: no URL in that style names Mapbox or Google, its glyph endpoint included", async () => {
    await mountCityMap();
    const urls = styleUrls(constructedStyle());
    expect(urls.length).toBeGreaterThan(0);
    expect(urls.filter(({ url }) => namesForbiddenHost(url))).toEqual([]);
  });

  // Wrong if a source, a tile template or a sprite resolved off the app's origin, or if CityMap
  // gave maplibre a transformRequest, which could send any of them elsewhere at fetch time.
  it("FE-INV-024: apart from its glyph endpoint, every URL in that style resolves to the app's own origin", async () => {
    await mountCityMap();
    expect(Object.keys(constructedOptions())).not.toContain("transformRequest");
    const urls = styleUrls(constructedStyle());
    expect(urls.length).toBeGreaterThan(0);
    expect(offOrigin(urls).filter(({ field }) => field !== "glyphs")).toEqual([]);
  });

  // Wrong if a symbol layer were added while the glyph endpoint is off-origin: maplibre would then
  // fetch protomaps.github.io, which production's CSP (connect-src 'self', nginx.conf) refuses.
  // Self-hosting the glyphs, or dropping the unused `glyphs` key, makes this hold trivially.
  it("FE-INV-024: while its glyph endpoint is off the app's origin, the style has no symbol layer, so maplibre never requests it", async () => {
    await mountCityMap();
    const style = constructedStyle();
    const offOriginFields = offOrigin(styleUrls(style)).map(({ field }) => field);
    expect(offOriginFields.includes("glyphs") ? symbolLayers(style) : []).toEqual([]);
  });
});
