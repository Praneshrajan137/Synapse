// ============================================================================
// SYNAPSE Chromatic — SDD test scaffolder.
//
// Spec-first workflow (ADR-014 / ADR-025): write the spec, scaffold RED tests,
// fill them in, go GREEN. Mirrors scripts/generate_tests_from_spec.py. For any
// invariant not yet referenced by a test, this writes an `it.todo` stub to
// tests/spec-stubs.test.mjs so coverage starts RED. No-op when all are covered.
// ============================================================================
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const spec = readFileSync(join(ROOT, "color-system.spec.yml"), "utf8");

const invariants = [...spec.matchAll(/id:[ \t]*"(INV-CLR-\d+)"\s*\n\s*description:[ \t]*"([^"]+)"/g)].map(
  (m) => ({ id: m[1], description: m[2] }),
);

const testDir = join(ROOT, "tests");
const covered = new Set();
for (const f of readdirSync(testDir).filter((x) => x.endsWith(".test.mjs") && x !== "spec-stubs.test.mjs")) {
  const txt = readFileSync(join(testDir, f), "utf8");
  for (const inv of invariants) if (txt.includes(inv.id)) covered.add(inv.id);
}

const uncovered = invariants.filter((inv) => !covered.has(inv.id));

if (uncovered.length === 0) {
  process.stdout.write(`OK: all ${invariants.length} invariants already have tests — nothing to scaffold.\n`);
} else {
  const body = uncovered
    .map((inv) => `  it.todo(${JSON.stringify(`${inv.id} — ${inv.description}`)});`)
    .join("\n");
  const file = `// GENERATED RED stubs — implement each in a real test file, then delete.
import { describe, it } from "vitest";

describe("SYNAPSE Chromatic — unimplemented spec invariants", () => {
${body}
});
`;
  writeFileSync(join(testDir, "spec-stubs.test.mjs"), file, "utf8");
  process.stdout.write(`Scaffolded ${uncovered.length} RED stub(s) -> tests/spec-stubs.test.mjs\n`);
}
