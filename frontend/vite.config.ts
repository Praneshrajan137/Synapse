import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// SYNAPSE Frontend — Vite config (TypeScript)
// ADR-012 pins React + Vite SPA. We extend, not replace.
// Dev proxy preserves the existing dev workflow: /api -> orchestrator (8085),
// /ws -> orchestrator (8085 WS). Production traffic is fronted by nginx
// (infrastructure/nginx/nginx.conf), so this proxy is dev-only.

/** The e2e-only harness entry (AD-12). Never referenced outside `e2e` mode. */
const E2E_HARNESS_ENTRY = "/spec/effectiveness/e2e-entry.ts";

/**
 * Effectiveness_Harness Rollup input split (AD-12).
 *
 * In `e2e` mode only, this injects a module script for the harness entry into
 * `index.html` BEFORE the html is parsed for inputs (`order: "pre"`), so Rollup
 * treats it as a second entry and emits it as its own chunk. The production
 * build never runs this hook, so `spec/effectiveness/harness.ts` is not in the
 * production module graph at all and `window.__atlasHarness` cannot reach
 * `dist/` — which is what `scripts/audit/workflow_shape_truth.py`'s
 * production-bundle assertion checks.
 *
 * The e2e build also writes to `dist-e2e/`, never `dist/`, so a harness build
 * left on a developer's machine cannot make that assertion fail.
 */
function e2eHarnessEntry(): Plugin {
  return {
    name: "synapse:e2e-harness-entry",
    enforce: "pre",
    transformIndexHtml: {
      order: "pre",
      handler: () => [
        {
          tag: "script",
          attrs: { type: "module", src: E2E_HARNESS_ENTRY },
          injectTo: "head-prepend" as const,
        },
      ],
    },
  };
}

/**
 * Vendor chunks by npm package (FE-INV-014, FE-INV-025). Every heavy viz library has
 * its own named chunk, and `deck`, `map` and `graph` must never be on the entry's
 * critical path: scripts/check-entry-preloads.mjs lists the eager set after each build
 * and fails on those prefixes.
 *
 * Rollup also puts a manual chunk's static dependencies into that chunk unless another
 * manual chunk has claimed them -- in both forms of `manualChunks` (rollup 4.60.4,
 * `addStaticDependenciesToManualChunk`). So a small module that the entry AND a heavy
 * library both import belongs to whichever chunk reaches it first, and the entry then
 * imports it FROM that chunk, which makes the whole chunk eager. A local build of
 * 2026-08-01 measured exactly this: the entry statically imported Vite's preload helper
 * and three tslib helpers from `deck-*.js`, and `clsx` from `viz-*.js`.
 * `runtime` claims those modules first, so they load with the entry in a few kilobytes
 * and the heavy chunks load only behind their lazy boundaries.
 *
 * This is the function form because it assigns by package path: it claims every installed
 * copy of a package (the lockfile carries more than one tslib), where the object form
 * resolves each name to a single module from the project root, and it can name the preload
 * helper by its virtual id.
 */
const VENDOR_CHUNKS: Readonly<Record<string, readonly string[]>> = {
  "react-vendor": ["react", "react-dom", "react-router-dom"],
  query: ["@tanstack/react-query"],
  deck: ["@deck.gl/core", "@deck.gl/layers", "@deck.gl/aggregation-layers", "@deck.gl/react"],
  // maplibre-gl v6's tile worker is not in this chunk: basemap.ts imports it with
  // `?worker&url`, which Vite bundles on its own as assets/maplibre-gl-worker-[hash].js
  // (tests/e2e/map-worker.spec.ts).
  map: ["maplibre-gl"],
  viz: ["recharts"],
  visx: ["@visx/axis", "@visx/group", "@visx/scale", "@visx/shape"],
  graph: ["sigma", "graphology", "graphology-layout-forceatlas2", "graphology-communities-louvain"],
  zod: ["zod"],
  runtime: ["clsx", "tslib"],
};

/** Vite's dynamic-import preload helper: a virtual module (vite 5.4 importAnalysisBuild). */
const VITE_PRELOAD_HELPER = "\0vite/preload-helper.js";

const CHUNK_OF_PACKAGE: ReadonlyMap<string, string> = new Map(
  Object.entries(VENDOR_CHUNKS).flatMap(([chunk, packages]) =>
    packages.map((name) => [name, chunk] as const),
  ),
);

/** The npm package a resolved module id lives in; undefined for app code and virtual modules. */
function packageOf(id: string): string | undefined {
  const marker = "/node_modules/";
  const at = id.lastIndexOf(marker);
  if (at < 0) return undefined;
  const [first, second] = id.slice(at + marker.length).split("/");
  if (first === undefined || first === "") return undefined;
  return first.startsWith("@") && second !== undefined ? `${first}/${second}` : first;
}

/**
 * `output.manualChunks`: the named chunk a module belongs to, or undefined for Rollup to place.
 * Stylesheets are never assigned: a package's CSS stays with the module that imports it, as
 * it did under the object form (maplibre-gl.css belongs to the lazy CityMap chunk).
 */
function vendorChunkOf(id: string): string | undefined {
  if (id === VITE_PRELOAD_HELPER) return "runtime";
  if (/\.css(?:$|\?)/.test(id)) return undefined;
  const name = packageOf(id);
  return name === undefined ? undefined : CHUNK_OF_PACKAGE.get(name);
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const orchestratorTarget = env.VITE_ORCHESTRATOR_URL ?? "http://localhost:8085";
  const orchestratorWs = orchestratorTarget.replace(/^http/, "ws");
  // `e2e` is the harness build mode (`pnpm build:e2e` / `pnpm preview:e2e`).
  const isE2eHarness = mode === "e2e";

  return {
    plugins: [react(), ...(isE2eHarness ? [e2eHarnessEntry()] : [])],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
        "@app": path.resolve(__dirname, "./src/app"),
        "@surfaces": path.resolve(__dirname, "./src/surfaces"),
        "@domain": path.resolve(__dirname, "./src/domain"),
        "@transport": path.resolve(__dirname, "./src/transport"),
        "@ds": path.resolve(__dirname, "./src/design-system"),
        "@viz": path.resolve(__dirname, "./src/visualization"),
        "@state": path.resolve(__dirname, "./src/state"),
        "@hooks": path.resolve(__dirname, "./src/hooks"),
        "@lib": path.resolve(__dirname, "./src/lib"),
        "@i18n": path.resolve(__dirname, "./src/i18n"),
        "@test": path.resolve(__dirname, "./src/test"),
      },
    },
    server: {
      port: 3001,
      strictPort: true,
      proxy: {
        "/api": { target: orchestratorTarget, changeOrigin: true },
        "/ws": { target: orchestratorWs, ws: true, changeOrigin: true },
      },
    },
    preview: {
      port: 3001,
      strictPort: true,
    },
    build: {
      // AD-12: the harness build is a SEPARATE output tree. `dist/` stays the
      // shipped bundle the production-bundle assertion scans.
      outDir: isE2eHarness ? "dist-e2e" : "dist",
      target: "es2022",
      sourcemap: true,
      cssCodeSplit: true,
      reportCompressedSize: true,
      chunkSizeWarningLimit: 200,
      rollupOptions: {
        output: {
          // Nothing eager imports deck.gl, MapLibre or sigma: the living map's canvas is one
          // lazy module (surfaces/mission-control/LivingMapCanvas) and every surface except
          // Mission Control is route-split, so those chunks load behind lazy boundaries. The
          // @deck.gl packages stay one named chunk so deck.gl is cached as a unit.
          manualChunks: vendorChunkOf,
        },
      },
    },
    optimizeDeps: {
      include: ["react", "react-dom", "react-router-dom", "@tanstack/react-query", "zod"],
    },
  };
});
