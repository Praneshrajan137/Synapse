import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { visualizer } from "rollup-plugin-visualizer";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

/**
 * SYNAPSE — Synaptic Calm Interface build configuration.
 *
 * Backend proxy targets the orchestrator inference server (port 8085).
 * Heavy visualization libraries are split into their own chunks so they
 * are only fetched when the operator enters a surface that needs them
 * (Twin / Bridge map) — see performance budgets in the plan, section 10.
 *
 * The Vitest `test` block lives here (not a separate vitest.config.ts)
 * so the React plugin types resolve against a single Vite instance.
 *
 * Coverage thresholds are intentionally NOT enforced during the
 * strangler-fig migration: the legacy JSX surfaces have no tests yet and
 * a global gate would block every PR. Phase 10 (hardening) raises the
 * gate to the 80% minimum mandated by the repo testing rules.
 */
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    visualizer({
      filename: "dist/bundle-stats.html",
      gzipSize: true,
      brotliSize: true,
    }),
    // PWA — offline-capable HITL console. The service worker is
    // registered manually (main.tsx) only when MSW is not the gateway,
    // so the two service workers never contend for the same scope.
    VitePWA({
      injectRegister: false,
      registerType: "autoUpdate",
      manifest: {
        name: "SYNAPSE — Synaptic Calm",
        short_name: "SYNAPSE",
        description: "An operating theater for autonomous supply-chain decisions.",
        theme_color: "#05070D",
        background_color: "#05070D",
        display: "standalone",
        icons: [
          { src: "/synapse-mark.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,woff2}"],
        navigateFallbackDenylist: [/^\/api/, /^\/ws/, /^\/health/],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "src"),
    },
  },
  server: {
    port: 3001,
    proxy: {
      "/api": "http://localhost:8085",
      "/ws": { target: "ws://localhost:8085", ws: true },
      "/health": "http://localhost:8085",
    },
  },
  build: {
    target: "es2022",
    sourcemap: true,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          // React core + routing + data layer — stable, cacheable.
          "react-vendor": [
            "react",
            "react-dom",
            "react-router-dom",
            "@tanstack/react-query",
          ],
          // OpenTelemetry — only loaded when tracing is enabled.
          telemetry: [
            "@opentelemetry/sdk-trace-web",
            "@opentelemetry/exporter-trace-otlp-http",
            "@opentelemetry/instrumentation-fetch",
            "@opentelemetry/instrumentation-document-load",
          ],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "dist", "tests/e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      reportsDirectory: "./coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.stories.tsx",
        "src/**/*.{test,spec}.{ts,tsx}",
        "src/test/**",
        "src/**/*.d.ts",
        "src/mocks/**",
      ],
    },
  },
});
