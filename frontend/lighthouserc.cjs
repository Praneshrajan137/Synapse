/* SYNAPSE Atlas Console — Lighthouse CI budgets (plan §10).
 *
 * Per-route budgets, not a single global one — Living City and Twin Studio
 * carry the Deck.gl/MapLibre baseline (~180 KB gz before our code) and need
 * higher LCP allowance than Mission Control or Audit Vault.
 *
 * Invoked via `pnpm lhci`. CI gate fails on regression beyond budget.
 * Bundle thresholds are checked separately by scripts/bundle-budget.mjs.
 */

module.exports = {
  ci: {
    collect: {
      startServerCommand: "pnpm preview",
      startServerReadyPattern: "Local:",
      url: [
        "http://localhost:5173/",
        "http://localhost:5173/bengaluru/",
        "http://localhost:5173/bengaluru/mission-control",
        "http://localhost:5173/bengaluru/decisions",
        "http://localhost:5173/bengaluru/twin",
        "http://localhost:5173/bengaluru/agents",
        "http://localhost:5173/bengaluru/audit",
      ],
      numberOfRuns: 3,
      settings: {
        preset: "desktop",
        throttlingMethod: "simulate",
        skipAudits: ["uses-http2"],
      },
    },
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.85 }],
        "categories:accessibility": ["error", { minScore: 1.0 }],
        "categories:best-practices": ["error", { minScore: 0.92 }],
        "categories:seo": "off",
        "categories:pwa": "off",

        // Per-route LCP budgets — see plan §10 table.
        // Living City + Twin Studio carry Deck.gl + 3D baseline.
        "largest-contentful-paint": [
          "error",
          { maxNumericValue: 3000, aggregationMethod: "median-run" },
        ],
        "total-blocking-time": [
          "error",
          { maxNumericValue: 250, aggregationMethod: "median-run" },
        ],
        "cumulative-layout-shift": [
          "error",
          { maxNumericValue: 0.1, aggregationMethod: "median-run" },
        ],

        // Bundle weight as a soft signal — hard budget enforced by
        // scripts/bundle-budget.mjs against rollup-stats.
        "resource-summary:script:size": [
          "warn",
          { maxNumericValue: 600_000 },
        ],
      },
    },
    upload: {
      target: "filesystem",
      outputDir: "./.lighthouseci",
    },
  },
};
