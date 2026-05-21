// ============================================================================
// SYNAPSE Chromatic — SDD coverage gate (testing layer 1).
//
// Every INV-CLR / MR-CLR id in color-system.spec.yml must appear in a test
// file. Mirrors the repo's scripts/check_spec_coverage.py. Exit 1 on a gap.
// ============================================================================
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const spec = readFileSync(join(ROOT, "color-system.spec.yml"), "utf8");

const ids = [...spec.matchAll(/id:[ \t]*"((?:INV|MR)-CLR-\d+)"/g)].map((m) => m[1]);
const testDir = join(ROOT, "tests");
const corpus = readdirSync(testDir)
  .filter((f) => f.endsWith(".test.mjs"))
  .map((f) => readFileSync(join(testDir, f), "utf8"))
  .join("\n");

const missing = ids.filter((id) => !corpus.includes(id));

if (missing.length > 0) {
  process.stdout.write(`FAIL spec-coverage: ${missing.length} id(s) without a test:\n`);
  for (const id of missing) process.stdout.write(`  - ${id}\n`);
  process.exit(1);
}
process.stdout.write(`OK spec-coverage: all ${ids.length} spec ids have a test.\n`);
