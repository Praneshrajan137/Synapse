import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

// SYNAPSE Atlas Console — Vitest config.
//
// Inherits from vite.config.ts so path aliases stay in sync with build.
// jsdom for DOM, c8/v8 coverage with thresholds (plan §10).
//
// Convention: tests sit alongside source. Property-tests use the
// "prop:" prefix in test names so `pnpm test:property` can grep them.
// Contract-tests (MSW + OpenAPI byte-equality) use "contract:" prefix.
export default mergeConfig(
  viteConfig({ command: "serve", mode: "test" }),
  defineConfig({
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/shared/test/setup.ts"],
      include: [
        "src/**/*.{test,spec}.{ts,tsx}",
        "src/**/__tests__/**/*.{ts,tsx}",
      ],
      exclude: [
        "node_modules",
        "dist",
        "playwright-report",
        "test-results",
        "src/shared/api/__generated__/**",
        "src/routeTree.gen.ts",
      ],
      coverage: {
        provider: "v8",
        reporter: ["text", "html", "lcov", "json-summary"],
        reportsDirectory: "./coverage",
        include: ["src/**/*.{ts,tsx}"],
        exclude: [
          "src/**/*.{test,spec,stories}.{ts,tsx}",
          "src/**/__tests__/**",
          "src/shared/api/__generated__/**",
          "src/shared/schemas/__generated__/**",
          "src/routeTree.gen.ts",
          "src/main.tsx",
          "src/main.jsx",
          "src/vite-env.d.ts",
        ],
        thresholds: {
          // Plan §8: ≥85% lines / 80% branches per surface.
          // Hardened bar (vs backend's 80%) because frontend logic is more local.
          lines: 85,
          functions: 85,
          branches: 80,
          statements: 85,
          autoUpdate: false,
        },
      },
      // Determinism — pin fast-check seeds via env or per-test setup.
      // CI sets VITEST_SEED to ensure reproducibility.
      sequence: { shuffle: false },
      restoreMocks: true,
      clearMocks: true,
    },
  }),
);
