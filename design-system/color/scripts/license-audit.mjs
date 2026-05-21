// ============================================================================
// SYNAPSE Chromatic — dependency licence audit (I-1).
//
// The repo forbids GPL-3.0 / AGPL-3.0 dependencies. This walks the installed
// node_modules tree and fails CI if any package declares a banned licence.
// ============================================================================
import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const NM = join(dirname(fileURLToPath(import.meta.url)), "..", "node_modules");
const BANNED = /AGPL|GPL-[23]/i; // CLAUDE.md: no GPL-3.0 / AGPL-3.0

function licenseOf(pkgJsonPath) {
  try {
    const pkg = JSON.parse(readFileSync(pkgJsonPath, "utf8"));
    if (typeof pkg.license === "string") return pkg.license;
    if (pkg.license && pkg.license.type) return pkg.license.type;
    if (Array.isArray(pkg.licenses)) return pkg.licenses.map((l) => l.type || l).join(" OR ");
    return "UNKNOWN";
  } catch {
    return "UNKNOWN";
  }
}

function* packageDirs(root) {
  if (!existsSync(root)) return;
  for (const entry of readdirSync(root)) {
    if (entry === ".bin" || entry === ".package-lock.json") continue;
    const full = join(root, entry);
    if (entry.startsWith("@")) {
      for (const scoped of readdirSync(full)) yield join(full, scoped);
    } else {
      yield full;
    }
  }
}

let audited = 0;
const violations = [];
for (const dir of packageDirs(NM)) {
  const pj = join(dir, "package.json");
  if (!existsSync(pj)) continue;
  audited += 1;
  const license = licenseOf(pj);
  if (BANNED.test(license)) violations.push(`${dir}: ${license}`);
}

if (violations.length > 0) {
  process.stdout.write(`FAIL licence audit — ${violations.length} banned dependency licence(s):\n`);
  for (const v of violations) process.stdout.write(`  - ${v}\n`);
  process.exit(1);
}
process.stdout.write(`OK licence audit (I-1): ${audited} packages, no GPL-3.0 / AGPL-3.0.\n`);
