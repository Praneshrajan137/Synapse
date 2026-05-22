// ============================================================================
// SYNAPSE Chromatic System — raw-colour-literal detector (INV-CLR-009)
//
// "Every hue earned" — colour reaches a component only through a token.
// This module flags raw hex / rgb() / hsl() literals in source. Used by:
//   - the no-raw-hex pre-commit hook + CI job (CLI mode below)
//   - tests/invariants.test.mjs (imports findHexLiterals against fixtures)
// ============================================================================
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HEX = /#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3}(?:[0-9a-fA-F]{2})?)?\b/g;
const FUNC = /\b(?:rgba?|hsla?)\s*\(/g;
const ALLOW = /chromatic-allow/;

/** Find raw colour literals in a source string. Returns [{ line, match }]. */
export function findHexLiterals(source) {
  const findings = [];
  source.split(/\r?\n/).forEach((line, i) => {
    if (ALLOW.test(line)) return;
    for (const re of [HEX, FUNC]) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(line)) !== null) {
        findings.push({ line: i + 1, match: m[0] });
      }
    }
  });
  return findings;
}

const SCAN_EXT = new Set([".js", ".jsx", ".ts", ".tsx"]);
const SKIP_DIR = new Set(["node_modules", "dist", ".git", "coverage"]);

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (!SKIP_DIR.has(entry)) walk(full, out);
    } else if (SCAN_EXT.has(extname(entry)) && !entry.endsWith(".generated.ts")) {
      out.push(full);
    }
  }
  return out;
}

/** Scan a directory tree; returns [{ file, line, match }]. */
export function scanDir(dir) {
  const violations = [];
  for (const file of walk(dir)) {
    for (const f of findHexLiterals(readFileSync(file, "utf8"))) {
      violations.push({ file, ...f });
    }
  }
  return violations;
}

// CLI: node scripts/lint-hex.mjs <dir> [<dir> ...]
const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  const dirs = process.argv.slice(2);
  if (dirs.length === 0) {
    process.stderr.write("usage: lint-hex.mjs <dir> [<dir> ...]\n");
    process.exit(2);
  }
  let total = 0;
  for (const dir of dirs) {
    for (const v of scanDir(dir)) {
      total += 1;
      process.stdout.write(`INV-CLR-009  ${v.file}:${v.line}  raw colour literal "${v.match}"\n`);
    }
  }
  if (total > 0) {
    process.stdout.write(`\nFAIL: ${total} raw colour literal(s) — use a chromatic token (var(--color-*)).\n`);
    process.exit(1);
  }
  process.stdout.write("OK: no raw colour literals.\n");
}
