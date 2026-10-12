// MapLibre GL set-up for the self-hosted basemap (FE-INV-020, FE-INV-024): the
// tile worker's URL and the PMTiles protocol, registered once per page before
// the first Map is constructed. Idempotent.

import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";

let prepared = false;

/**
 * Process-wide MapLibre set-up; call it before constructing a Map.
 *
 * maplibre-gl v6 is ESM-only and, inside a bundler's module graph, cannot find
 * its own worker, so a bundled app must call `setWorkerUrl` once before the
 * first Map exists (v5 to v6 migration guide). `?worker&url` is the Vite form
 * maplibre's installation guide prescribes: Vite bundles the worker entry, and
 * anything it imports, into one hashed asset
 * (`assets/maplibre-gl-worker-[hash].js`) and returns that asset's URL.
 *
 * Without it nothing fails loudly: the map, its controls and the deck.gl
 * overlay all mount, but no vector tile is ever decoded, because the worker
 * that decodes them never starts. `tests/e2e/map-worker.spec.ts` observes it.
 */
export function prepareMapLibre(): void {
  if (prepared) return;
  maplibregl.setWorkerUrl(workerUrl);
  const protocol = new Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  prepared = true;
}

/** Self-hosted Protomaps style — dark theme tuned for SYNAPSE canvas. */
export function buildBasemapStyle(tilesUrl: string): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      synapse_tiles: {
        type: "vector",
        url: `pmtiles://${tilesUrl}`,
      },
    },
    glyphs: "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
    // chromatic-allow: the MapLibre style spec requires literal colour values
    // in its paint JSON — it cannot read CSS custom properties. Each value
    // below is the v2.0.0 cool blue-graphite dist hex for the named token
    // (ADR-048); lib/__tests__/chromatics.test.ts pins them against dist so
    // drift is a failing test, not a review hope. Water is the DEEP VOID —
    // darker than land, so the coastline reads as depth on the cool canvas.
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#05090e" }, // chromatic-allow ← color.surface.canvas dark
      },
      {
        id: "land",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "earth",
        paint: { "fill-color": "#0c1218" }, // chromatic-allow ← color.surface.panel dark
      },
      {
        id: "water",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "water",
        paint: { "fill-color": "#020407" }, // chromatic-allow ← color.text.inverse dark (the deep void)
      },
      {
        id: "roads",
        type: "line",
        source: "synapse_tiles",
        "source-layer": "roads",
        paint: {
          "line-color": "#34383d", // chromatic-allow ← color.border.subtle dark
          "line-width": 0.5,
        },
      },
      {
        id: "buildings",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "buildings",
        paint: { "fill-color": "#171c23", "fill-opacity": 0.4 }, // chromatic-allow ← color.surface.raised dark
      },
    ],
  } as unknown as maplibregl.StyleSpecification;
}
