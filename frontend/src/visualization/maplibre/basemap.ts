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
    glyphs:
      "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#020617" },
      },
      {
        id: "land",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "earth",
        paint: { "fill-color": "#0f172a" },
      },
      {
        id: "water",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "water",
        paint: { "fill-color": "#1e293b" },
      },
      {
        id: "roads",
        type: "line",
        source: "synapse_tiles",
        "source-layer": "roads",
        paint: {
          "line-color": "#334155",
          "line-width": 0.5,
        },
      },
      {
        id: "buildings",
        type: "fill",
        source: "synapse_tiles",
        "source-layer": "buildings",
        paint: { "fill-color": "#1f2937", "fill-opacity": 0.4 },
      },
    ],
  } as unknown as maplibregl.StyleSpecification;
}
