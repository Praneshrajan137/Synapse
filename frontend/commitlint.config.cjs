/* SYNAPSE Atlas Console — commitlint conventional config.
 *
 * Aligns with the existing repo commit style (e.g. "fix(ci): green ruff …").
 * The `synapse` scope is reserved for repo-wide concerns; surfaces use their
 * own scopes (living-city, mission-control, decision-trace, twin-studio,
 * agent-floor, audit-vault).
 */
module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "scope-enum": [
      2,
      "always",
      [
        "synapse",
        "frontend",
        "living-city",
        "mission-control",
        "decision-trace",
        "twin-studio",
        "agent-floor",
        "audit-vault",
        "shared",
        "ci",
        "docs",
        "deps",
      ],
    ],
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "refactor",
        "perf",
        "test",
        "docs",
        "chore",
        "build",
        "ci",
        "revert",
        "elevate",
      ],
    ],
    "subject-case": [2, "never", ["upper-case", "pascal-case", "start-case"]],
  },
};
