// PMTiles protocol registration for MapLibre GL (FE-INV-020).
// One-time call from the app shell; idempotent.

import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";

let registered = false;

export function registerPMTilesProtocol(): void {
  if (registered) return;
  const protocol = new Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  registered = true;
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
    // below is the v1.2.0 Obsidian dist hex for the named token (ADR-045);
    // lib/__tests__/chromatics.test.ts pins them against dist so drift is a
    // failing test, not a review hope. Water is the DEEP VOID — darker than
    // land, so the coastline reads as depth on the cold-void canvas.
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#06080f" }, // chromatic-allow ← color.surface.canvas dark
      },
      {
        id: "land",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "earth",
        paint: { "fill-color": "#0e121a" }, // chromatic-allow ← color.surface.panel dark
      },
      {
        id: "water",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "water",
        paint: { "fill-color": "#020307" }, // chromatic-allow ← color.text.inverse dark (the deep void)
      },
      {
        id: "roads",
        type: "line",
        source: "synapse_tiles",
        "source-layer": "roads",
        paint: {
          "line-color": "#343840", // chromatic-allow ← color.border.subtle dark
          "line-width": 0.5,
        },
      },
      {
        id: "buildings",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "buildings",
        paint: { "fill-color": "#181c24", "fill-opacity": 0.4 }, // chromatic-allow ← color.surface.raised dark
      },
    ],
  } as unknown as maplibregl.StyleSpecification;
}
