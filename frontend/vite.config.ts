import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { TanStackRouterVite } from "@tanstack/router-vite-plugin";
import checker from "vite-plugin-checker";
import path from "node:path";

import { agentSpecsPlugin } from "./plugins/vite-plugin-agent-specs";

// SYNAPSE Atlas Console — Vite config
// - ADR-012 binds React + Vite + Deck.gl + MapLibre + Recharts. Kept.
// - ADR-025 amends with TS, TanStack Router, vertical-slice surfaces.
// - Dev proxy preserves the existing /api → :8085 and /ws → :8085 contract.
//   Backend gap B1 (SSE bridge at /api/v1/stream/{topic}) flows through /api.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env["VITE_API_TARGET"] ?? "http://localhost:8085";
  const wsTarget = env["VITE_WS_TARGET"] ?? "ws://localhost:8085";

  return {
    plugins: [
      // Spec.yaml ingestion (ADR-014/SDD). Emits `virtual:atlas/agent-specs`
      // consumed by the Agent Floor surface (plan §5.5). Adding a new agent
      // is one folder + one YAML, no UI code change.
      agentSpecsPlugin(),
      // TanStack Router file-based routing. Generated route tree lives at
      // src/routeTree.gen.ts and is gitignored. See ADR-025 §Routing.
      TanStackRouterVite({
        routesDirectory: "src/surfaces",
        generatedRouteTree: "src/routeTree.gen.ts",
        routeFileIgnorePattern: "(components|hooks|api|model|stories|e2e|bdd|__tests__)",
        quoteStyle: "double",
      }),
      react(),
      // In-process typecheck during dev — fail fast if a slice imports a stale
      // generated type from src/shared/api or src/shared/schemas.
      checker({
        typescript: { tsconfigPath: "tsconfig.app.json" },
        overlay: { initialIsOpen: false },
      }),
    ],
    resolve: {
      alias: {
        "@app": path.resolve(__dirname, "src/app"),
        "@surfaces": path.resolve(__dirname, "src/surfaces"),
        "@shared": path.resolve(__dirname, "src/shared"),
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 3001,
      strictPort: true,
      // Existing contract from the v0.4.0 console; preserved verbatim so the
      // five legacy JSX pages continue to function during S1 migration.
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
        "/ws": { target: wsTarget, ws: true, changeOrigin: true },
      },
    },
    preview: {
      port: 5173,
      strictPort: true,
    },
    build: {
      target: "es2022",
      sourcemap: true,
      cssCodeSplit: true,
      rollupOptions: {
        output: {
          manualChunks: {
            // Per-route code splitting for Deck.gl + MapLibre baseline. The
            // shell budget is 120 KB gz; Living City + Twin Studio carry the
            // map / 3D chunks asynchronously (plan §10).
            "vendor-map": ["maplibre-gl", "@deck.gl/core", "@deck.gl/layers", "@deck.gl/react"],
            "vendor-3d": ["three", "react-force-graph-3d", "d3-force-3d"],
            "vendor-charts": ["recharts"],
          },
        },
      },
    },
    optimizeDeps: {
      include: ["react", "react-dom", "@tanstack/react-query", "@tanstack/react-router"],
    },
    // Worker config kept lean; TanStack Router and Deck.gl don't need workers
    // in our profile but reserved for the future Visx force-graph layer.
    worker: { format: "es" },
  };
});
