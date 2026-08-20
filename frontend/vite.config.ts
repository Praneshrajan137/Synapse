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
          manualChunks: {
            "react-vendor": ["react", "react-dom", "react-router-dom"],
            "query": ["@tanstack/react-query"],
            // FE-INV-025: every heavy viz lib is split into its own chunk so it
            // never lands in the entry bundle (index-*.js). @deck.gl/aggregation-
            // layers (HeatmapLayer) must be listed explicitly — without it the
            // heatmap layer spills into the entry chunk via the eager
            // MissionControl → LivingMap → deck-gl/layers import.
            "deck": [
              "@deck.gl/core",
              "@deck.gl/layers",
              "@deck.gl/aggregation-layers",
              "@deck.gl/react",
            ],
            "map": ["maplibre-gl"],
            "viz": ["recharts"],
            // visx feeds ParetoFrontier, which the eager decision/cockpit routes
            // import — split it out so it stays clear of the entry bundle.
            "visx": [
              "@visx/axis",
              "@visx/group",
              "@visx/scale",
              "@visx/shape",
            ],
            "graph": [
              "sigma",
              "graphology",
              "graphology-layout-forceatlas2",
              "graphology-communities-louvain",
            ],
            "zod": ["zod"],
          },
        },
      },
    },
    optimizeDeps: {
      include: ["react", "react-dom", "react-router-dom", "@tanstack/react-query", "zod"],
    },
  };
});
