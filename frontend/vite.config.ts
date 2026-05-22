import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// SYNAPSE Frontend — Vite config (TypeScript)
// ADR-012 pins React + Vite SPA. We extend, not replace.
// Dev proxy preserves the existing dev workflow: /api -> orchestrator (8085),
// /ws -> orchestrator (8085 WS). Production traffic is fronted by nginx
// (infrastructure/nginx/nginx.conf), so this proxy is dev-only.

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const orchestratorTarget = env.VITE_ORCHESTRATOR_URL ?? "http://localhost:8085";
  const orchestratorWs = orchestratorTarget.replace(/^http/, "ws");

  return {
    plugins: [react()],
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
            "deck": ["@deck.gl/core", "@deck.gl/layers", "@deck.gl/react"],
            "map": ["maplibre-gl"],
            "viz": ["recharts", "three", "d3-force-3d", "react-force-graph-3d"],
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
