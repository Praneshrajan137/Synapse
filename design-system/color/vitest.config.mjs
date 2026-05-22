import { defineConfig } from "vitest/config";

// SYNAPSE Chromatic System — test runner.
// All 7 repo testing layers (SDD, Fuzz, Contract, Metamorphic, DbC, Oracle,
// Mutation) execute here against the token domain model. See
// color-system.spec.yml for the invariants under test.
export default defineConfig({
  test: {
    include: ["tests/**/*.test.mjs"],
    environment: "node",
    reporters: ["default"],
    coverage: {
      provider: "v8",
      include: ["build/**/*.mjs"],
      thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
    },
  },
});
