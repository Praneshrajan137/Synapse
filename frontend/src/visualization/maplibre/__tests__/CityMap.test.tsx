import { render } from "@testing-library/react";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { beforeEach, describe, expect, it, vi } from "vitest";

// What maplibre-gl was asked to do, in order. jsdom has no WebGL2, so the
// library is a recorder: the claim is the order and count of the process-wide
// set-up calls relative to map construction, not anything a map renders.
interface MapLibreLog {
  readonly calls: string[];
  readonly workerUrls: string[];
  readonly protocols: string[];
}

const maplibre = vi.hoisted((): MapLibreLog => ({ calls: [], workerUrls: [], protocols: [] }));

vi.mock("maplibre-gl", () => {
  class MockMap {
    constructor() {
      maplibre.calls.push("Map");
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
    setWorkerUrl: (url: string): void => {
      maplibre.calls.push("setWorkerUrl");
      maplibre.workerUrls.push(url);
    },
    addProtocol: (name: string, handler: unknown): void => {
      maplibre.calls.push("addProtocol");
      maplibre.protocols.push(`${name}:${typeof handler}`);
    },
  };
});
// The deck.gl overlay needs a WebGL2 context jsdom cannot give it.
vi.mock("@deck.gl/react", () => ({ DeckGL: (): null => null }));

// maplibre-gl v6 cannot find its own worker inside a bundle: without the URL
// Vite emitted, the map mounts and no vector tile is ever decoded.
describe("CityMap", () => {
  beforeEach(() => {
    maplibre.calls.length = 0;
    maplibre.workerUrls.length = 0;
    maplibre.protocols.length = 0;
  });

  it("sets the bundled worker URL and pmtiles protocol once, before the first map", async () => {
    // A fresh module graph: the set-up runs once per page, and this claim is
    // about the first map that page builds.
    vi.resetModules();
    const { CityMap } = await import("../CityMap");

    const first = render(<CityMap />);
    first.unmount();
    render(<CityMap />);

    // Two maps were built; the set-up ran once, ahead of both.
    expect(maplibre.calls).toEqual(["setWorkerUrl", "addProtocol", "Map", "Map"]);
    // The URL is the one Vite's worker pipeline produced for maplibre's worker entry.
    expect(maplibre.workerUrls).toEqual([workerUrl]);
    expect(workerUrl).toMatch(/maplibre-gl-worker/);
    expect(maplibre.protocols).toEqual(["pmtiles:function"]);
  });
});
