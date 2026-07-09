/**
 * Effectiveness_Harness — Spatial_Visualization scenario (FE-WS-2, Req 10).
 *
 * The two Spatial_Visualizations are the deck.gl/MapLibre living map (Mission
 * Control) and the sigma/graphology supply-network graph (Twin Lab). Req 10
 * verifies them in a REAL browser: WebGL init (smoke), chromatic-token encoding
 * against the *resolved* token values (not jsdom), an error-with-retry state on
 * WebGL init failure (never a blank canvas), and a keyboard/SR-reachable
 * non-spatial equivalent plus the loading state while loading.
 *
 * This descriptor is the transport-free single source of truth the spatial
 * `*.spec.ts` real-browser check drives against (design "I. surfaces/spec —
 * spatial WebGL / chromatic checks (Req 10)"). It declares:
 *
 *   - `seed` + `seedSchemaIds` so the harness serves BYTE-IDENTICAL, contract-
 *     accurate geospatial and network-graph fixtures on every run (Req 10.5,
 *     1.3, 2.2) — the fixtures themselves are generated from the bound
 *     Domain_Schemas by the shared fixture factory, not hand-authored here.
 *   - `surfaces` — where each Spatial_Visualization renders, the role=img
 *     canvas label it exposes, and the always-in-DOM non-spatial equivalent
 *     (a `<details>` disclosure) that carries the same data to keyboard and
 *     screen-reader users (Req 10.4).
 *   - `chromaticEncodings` — the Chromatic_Tokens the map's WebGL layers
 *     mirror, each pinned to the deck.gl rgb255 the layer uses so the real-
 *     browser check can assert the encoding equals the *resolved* CSS custom
 *     property value the rest of the Console renders with (Req 10.2). These
 *     mirror `visualization/deck-gl/palette.ts`, itself pinned against the
 *     token dist by `lib/__tests__/chromatics.test.ts`.
 *
 * As with the JTBD and Resilience scenarios, descriptors are validated at
 * module load so a malformed or unbound spatial scenario fails fast rather than
 * surfacing as an opaque E2E failure.
 */

import { hasSchema, type SchemaId } from "../schema-registry";

/** The class of Spatial_Visualization a surface renders. */
export type SpatialKind = "geospatial" | "network-graph";

/**
 * A single Spatial_Visualization the Req 10 check drives against: where it
 * renders, the role=img canvas label it exposes for the WebGL smoke check, and
 * the summary text of its always-in-DOM non-spatial equivalent (Req 10.4).
 */
export interface SpatialSurfaceCheck {
  /** The class of Spatial_Visualization. */
  readonly kind: SpatialKind;
  /** Primary-Surface id (mirrors `@app/primary-surfaces`). */
  readonly surfaceId: string;
  /** react-router path of that Surface. */
  readonly surfacePath: string;
  /**
   * A regex source (JS `RegExp` syntax) matching the `aria-label` of the
   * role=img spatial canvas — the accessible handle the smoke check locates the
   * WebGL surface by without depending on the app's internal DOM structure.
   */
  readonly canvasLabelPattern: string;
  /**
   * The visible summary text of the non-spatial equivalent `<details>`
   * disclosure — always in the DOM, keyboard-operable, SR-reachable (Req 10.4).
   */
  readonly nonSpatialSummaryPattern: string;
}

/**
 * A Chromatic_Token the spatial WebGL layers mirror. `cssVar` is resolved in
 * the real browser (`getComputedStyle`) and asserted equal to `rgb255` — the
 * exact tuple the deck.gl layer paints with — so the Spatial_Visualization
 * provably encodes with the SAME token value as the rest of the Console
 * (Req 10.2). `rgb255` mirrors `visualization/deck-gl/palette.ts`.
 */
export interface ChromaticEncodingBinding {
  /** The `--syn-*` custom property the token is delivered through. */
  readonly cssVar: string;
  /** The rgb255 triplet the WebGL layer paints with (deck.gl palette mirror). */
  readonly rgb255: readonly [number, number, number];
  /** What this token encodes on the map, in plain language. */
  readonly encodes: string;
}

/** A named, reproducible Spatial_Visualization correctness scenario (Req 10). */
export interface SpatialScenario {
  /** Stable id used by the E2E spec and reports. */
  readonly id: string;
  /** Deterministic seed fixing the geo/graph fixtures (Req 10.5, 1.3). */
  readonly seed: number;
  /** Short human title for reports. */
  readonly title: string;
  /** One-sentence description of what the scenario proves. */
  readonly narrative: string;
  /**
   * The Domain_Schema ids whose fixtures the harness seeds — the geospatial
   * (route/demand) and network-graph (topology) shapes the two spatial surfaces
   * consume. Every id must resolve in the shared schema registry (asserted at
   * module load), binding the scenario to contract-accurate fixtures (Req 2.2).
   */
  readonly seedSchemaIds: readonly SchemaId[];
  /** The Spatial_Visualizations this scenario verifies (map + supply graph). */
  readonly surfaces: readonly SpatialSurfaceCheck[];
  /** The Chromatic_Tokens the map's WebGL layers mirror (Req 10.2). */
  readonly chromaticEncodings: readonly ChromaticEncodingBinding[];
}

/**
 * The spatial-visualization correctness scenario (Req 10).
 *
 * Seeds deterministic geospatial fixtures (route plans + demand forecasts the
 * living map plots) and a deterministic network-graph fixture (the supply
 * topology the sigma graph lays out), then drives the two spatial surfaces
 * through the WebGL smoke, chromatic-encoding, error-with-retry, and
 * non-spatial-equivalent checks.
 */
export const SPATIAL_VISUALIZATION: SpatialScenario = {
  id: "spatial.visualization-correctness",
  seed: 100_101,
  title: "Spatial visualization correctness in a real browser",
  narrative:
    "Seed deterministic geospatial (route/demand) and network-graph (topology) fixtures, then verify each Spatial_Visualization initializes WebGL without throwing (smoke), encodes agent/tier/confidence with the same resolved Chromatic_Token values as the rest of the Console, renders the error Universal_State with a retry affordance on WebGL init failure (never a blank canvas), and exposes a keyboard/SR-reachable non-spatial equivalent plus the loading state while loading.",
  // Geospatial: the route arcs + demand heatmap the living map plots. Network-
  // graph: the supply topology the sigma/graphology graph lays out.
  seedSchemaIds: ["RoutePlan", "DemandForecast", "TopologyResponse"],
  surfaces: [
    {
      kind: "geospatial",
      surfaceId: "mission-control",
      surfacePath: "/",
      // CityMap: <div role="img" aria-label="{city} live map">.
      canvasLabelPattern: "live map$",
      // MapDataTable: <summary>Map data as a table (…)</summary>.
      nonSpatialSummaryPattern: "^Map data as a table",
    },
    {
      kind: "network-graph",
      surfaceId: "twin-lab",
      surfacePath: "/twin",
      // SupplyNetworkGraph: <div role="img" aria-label="Supply network: …">.
      canvasLabelPattern: "^Supply network:",
      // SupplyNetworkTable: <summary>Supply network as a table (…)</summary>.
      nonSpatialSummaryPattern: "^Supply network as a table",
    },
  ],
  // Mirrors visualization/deck-gl/palette.ts (pinned against the token dist by
  // lib/__tests__/chromatics.test.ts). The living map's WebGL layers paint
  // saturated signal/confidence colour ONLY on abnormality; each tuple below is
  // the dark-theme rgb255 of the token it mirrors, so the real-browser check
  // can assert the map encodes with the SAME resolved token value the rest of
  // the Console renders with (Req 10.2).
  chromaticEncodings: [
    { cssVar: "--syn-signal-info", rgb255: [102, 180, 252], encodes: "info signal (DECK_INFO)" },
    {
      cssVar: "--syn-signal-warning",
      rgb255: [245, 116, 0],
      encodes: "congested-store warning (DECK_WARN)",
    },
    {
      cssVar: "--syn-signal-danger",
      rgb255: [235, 68, 65],
      encodes: "at-risk store / route danger (DECK_RISK)",
    },
    {
      cssVar: "--syn-confidence-risk",
      rgb255: [233, 80, 72],
      encodes: "low-confidence risk arc (DECK_RISK_SOFT, color.confidence.low)",
    },
  ],
};

/** Every registered Spatial_Visualization scenario (Req 10). */
export const SPATIAL_SCENARIOS: readonly SpatialScenario[] = [SPATIAL_VISUALIZATION];

// --- Load-time integrity checks (fail fast on a malformed/unbound scenario) ---

{
  const seenIds = new Set<string>();
  for (const s of SPATIAL_SCENARIOS) {
    if (seenIds.has(s.id)) {
      throw new Error(`Duplicate Spatial_Visualization scenario id: ${s.id}`);
    }
    seenIds.add(s.id);

    if (s.seedSchemaIds.length === 0) {
      throw new Error(`Spatial_Visualization scenario ${s.id} declares no seed schema ids`);
    }
    const unbound = s.seedSchemaIds.filter((id) => !hasSchema(id));
    if (unbound.length > 0) {
      throw new Error(
        `Spatial_Visualization scenario ${s.id} references unregistered schema id(s): ${unbound.join(", ")}`,
      );
    }

    if (s.surfaces.length === 0) {
      throw new Error(`Spatial_Visualization scenario ${s.id} declares no spatial surfaces`);
    }
    // Both classes of Spatial_Visualization (map + graph) must be covered so
    // Req 10 is not silently narrowed to a single surface.
    const kinds = new Set(s.surfaces.map((v) => v.kind));
    for (const required of ["geospatial", "network-graph"] as const) {
      if (!kinds.has(required)) {
        throw new Error(
          `Spatial_Visualization scenario ${s.id} is missing a ${required} surface`,
        );
      }
    }

    if (s.chromaticEncodings.length === 0) {
      throw new Error(
        `Spatial_Visualization scenario ${s.id} declares no chromatic encodings to verify`,
      );
    }
    for (const enc of s.chromaticEncodings) {
      if (!enc.cssVar.startsWith("--syn-")) {
        throw new Error(
          `Spatial_Visualization scenario ${s.id} encoding cssVar must be a --syn-* token: ${enc.cssVar}`,
        );
      }
      const inRange = enc.rgb255.every((c) => Number.isInteger(c) && c >= 0 && c <= 255);
      if (enc.rgb255.length !== 3 || !inRange) {
        throw new Error(
          `Spatial_Visualization scenario ${s.id} encoding ${enc.cssVar} has an invalid rgb255 tuple`,
        );
      }
    }
  }
}

/** The Spatial_Visualization scenario with the given id, or `undefined`. */
export function getSpatialScenario(id: string): SpatialScenario | undefined {
  return SPATIAL_SCENARIOS.find((s) => s.id === id);
}
