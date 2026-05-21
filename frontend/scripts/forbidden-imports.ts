/**
 * Forbidden-imports CI gate.
 *
 * Enforces invariant I-1 (zero cost) and tenet T-12 on the frontend:
 * no paid-API SDKs, no paid map vendors, no third-party telemetry /
 * session-replay services. The Python CI already blocks these strings
 * server-side; this is the browser-side mirror.
 *
 * Exits non-zero on any violation. Wired into `npm run verify` and CI.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

/** Module specifiers that must never be imported. */
const FORBIDDEN: readonly string[] = [
  "openai",
  "anthropic",
  "@anthropic-ai/sdk",
  "cohere",
  "cohere-ai",
  "replicate",
  "mapbox-gl", // paid vendor — SYNAPSE uses maplibre-gl (free)
  "@mapbox/mapbox-gl-draw",
  "@sentry/react",
  "@sentry/browser",
  "@datadog/browser-rum",
  "logrocket",
  "@fullstory/browser",
];

const SRC_DIR = join(import.meta.dirname, "..", "src");
const SCANNED_EXT = new Set([".ts", ".tsx", ".js", ".jsx"]);
const IMPORT_RE = /(?:import|export)[^'"]*?from\s*['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)/g;

interface Violation {
  readonly file: string;
  readonly line: number;
  readonly specifier: string;
}

function listFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...listFiles(full));
    } else if (SCANNED_EXT.has(extname(full))) {
      out.push(full);
    }
  }
  return out;
}

function isForbidden(specifier: string): boolean {
  return FORBIDDEN.some(
    (banned) => specifier === banned || specifier.startsWith(`${banned}/`),
  );
}

function scan(): Violation[] {
  const violations: Violation[] = [];
  for (const file of listFiles(SRC_DIR)) {
    const source = readFileSync(file, "utf8");
    const lines = source.split("\n");
    lines.forEach((text, index) => {
      IMPORT_RE.lastIndex = 0;
      let match: RegExpExecArray | null = IMPORT_RE.exec(text);
      while (match !== null) {
        const specifier = match[1] ?? match[2];
        if (specifier && isForbidden(specifier)) {
          violations.push({
            file: relative(process.cwd(), file),
            line: index + 1,
            specifier,
          });
        }
        match = IMPORT_RE.exec(text);
      }
    });
  }
  return violations;
}

const violations = scan();

if (violations.length > 0) {
  console.error("\n  I-1 VIOLATION — forbidden imports detected:\n");
  for (const v of violations) {
    console.error(`  ${v.file}:${v.line}  imports "${v.specifier}"`);
  }
  console.error(
    `\n  ${violations.length} violation(s). SYNAPSE is zero-cost: no paid APIs.\n`,
  );
  process.exit(1);
}

console.info("  forbidden-imports: clean — no paid-API imports found.");
