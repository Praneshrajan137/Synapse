/**
 * Dependency license audit.
 *
 * Enforces the repo dependency rule: never add a GPL-3.0 or AGPL-3.0
 * dependency. Allowed: MIT, Apache-2.0, BSD-2/3-Clause, ISC, MPL-2.0,
 * PSF, 0BSD, Unlicense, CC0.
 *
 * Walks installed top-level packages in node_modules and inspects their
 * `license` field. Fails on a denied license; warns on an unrecognized
 * one so a human can classify it.
 */

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ALLOWED = new Set([
  "MIT",
  "MIT-0",
  "Apache-2.0",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "ISC",
  "MPL-2.0",
  "0BSD",
  "Unlicense",
  "CC0-1.0",
  "Python-2.0",
  "BlueOak-1.0.0",
]);

const DENIED = new Set(["GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later", "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later"]);

const MODULES = join(import.meta.dirname, "..", "node_modules");

interface Pkg {
  name?: string;
  version?: string;
  license?: string | { type?: string };
  licenses?: Array<{ type?: string }>;
}

function licenseOf(pkg: Pkg): string {
  if (typeof pkg.license === "string") return pkg.license;
  if (pkg.license && typeof pkg.license === "object") return pkg.license.type ?? "UNKNOWN";
  if (pkg.licenses?.[0]?.type) return pkg.licenses[0].type ?? "UNKNOWN";
  return "UNKNOWN";
}

function packageDirs(): string[] {
  if (!existsSync(MODULES)) {
    console.warn("  license-audit: node_modules not found — run `npm install` first.");
    process.exit(0);
  }
  const dirs: string[] = [];
  for (const entry of readdirSync(MODULES)) {
    const full = join(MODULES, entry);
    if (!statSync(full).isDirectory()) continue;
    if (entry.startsWith("@")) {
      for (const scoped of readdirSync(full)) {
        dirs.push(join(full, scoped));
      }
    } else if (entry !== ".bin" && entry !== ".cache" && entry !== ".tmp") {
      dirs.push(full);
    }
  }
  return dirs;
}

let denied = 0;
let unknown = 0;

for (const dir of packageDirs()) {
  const manifest = join(dir, "package.json");
  if (!existsSync(manifest)) continue;
  let pkg: Pkg;
  try {
    pkg = JSON.parse(readFileSync(manifest, "utf8")) as Pkg;
  } catch {
    continue;
  }
  const license = licenseOf(pkg);
  const id = `${pkg.name ?? "?"}@${pkg.version ?? "?"}`;
  if (DENIED.has(license)) {
    console.error(`  DENIED  ${id} — ${license}`);
    denied += 1;
  } else if (!ALLOWED.has(license) && license !== "UNKNOWN") {
    console.warn(`  REVIEW  ${id} — ${license} (not on allow-list)`);
    unknown += 1;
  } else if (license === "UNKNOWN") {
    unknown += 1;
  }
}

if (denied > 0) {
  console.error(`\n  license-audit: ${denied} denied (GPL/AGPL) dependency(ies).\n`);
  process.exit(1);
}

console.info(
  `  license-audit: no GPL/AGPL dependencies. ${unknown} package(s) need manual review.`,
);
