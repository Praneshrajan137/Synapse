import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
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
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      reportsDirectory: "./coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.stories.tsx",
        "src/**/*.test.{ts,tsx}",
        "src/test/**",
        "src/**/index.ts",
        "src/transport/openapi.gen.ts",
      ],
      thresholds: {
        statements: 60,
        branches: 60,
        functions: 60,
        lines: 60,
      },
    },
  },
});
