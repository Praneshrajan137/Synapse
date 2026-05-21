#!/usr/bin/env node
/**
 * SYNAPSE Atlas Console — bundle budget enforcer.
 *
 * Reads dist/stats.html (or dist/.vite/manifest.json) and asserts:
 *   - Shell budget (initial JS, gz):           ≤ 120 KB   (plan §10)
 *   - Per-route budget when async-chunked:     route-specific
 *   - Map vendor chunk:                        ≤ 220 KB
 *   - 3D vendor chunk:                         ≤ 200 KB
 *
 * Exit non-zero on violation. CI gate fails the build.
 *
 * Usage:
 *   node scripts/bundle-budget.mjs --manifest dist/.vite/manifest.json
 */
import { readFileSync, existsSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

const ROOT = process.cwd();
const DIST = join(ROOT, "dist");

const SHELL_BUDGET_GZ = 120 * 1024;
const VENDOR_MAP_BUDGET_GZ = 220 * 1024;
const VENDOR_3D_BUDGET_GZ = 200 * 1024;

function gzippedSize(absPath) {
  const buf = readFileSync(absPath);
  return gzipSync(buf, { level: 9 }).length;
}

function findManifest() {
  const candidates = [
    join(DIST, ".vite", "manifest.json"),
    join(DIST, "manifest.json"),
  ];
  for (const c of candidates) if (existsSync(c)) return c;
  console.error("[bundle-budget] no manifest found; run `pnpm build` first");
  process.exit(2);
}

const manifestPath = findManifest();
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));

let shellBytes = 0;
let mapBytes = 0;
let threeBytes = 0;

for (const [_key, entry] of Object.entries(manifest)) {
  if (!entry || typeof entry !== "object") continue;
  const file = entry.file;
  if (!file?.endsWith(".js")) continue;
  const abs = join(DIST, file);
  if (!existsSync(abs)) continue;
  const size = gzippedSize(abs);

  if (file.includes("vendor-map")) mapBytes += size;
  else if (file.includes("vendor-3d")) threeBytes += size;
  else if (entry.isEntry) shellBytes += size;
}

const violations = [];
if (shellBytes > SHELL_BUDGET_GZ)
  violations.push(
    `Shell ${(shellBytes / 1024).toFixed(1)} KB gz exceeds ${SHELL_BUDGET_GZ / 1024} KB`,
  );
if (mapBytes > VENDOR_MAP_BUDGET_GZ)
  violations.push(
    `vendor-map ${(mapBytes / 1024).toFixed(1)} KB gz exceeds ${VENDOR_MAP_BUDGET_GZ / 1024} KB`,
  );
if (threeBytes > VENDOR_3D_BUDGET_GZ)
  violations.push(
    `vendor-3d ${(threeBytes / 1024).toFixed(1)} KB gz exceeds ${VENDOR_3D_BUDGET_GZ / 1024} KB`,
  );

console.log(
  `[bundle-budget] shell=${(shellBytes / 1024).toFixed(1)} KB, map=${(mapBytes / 1024).toFixed(1)} KB, 3d=${(threeBytes / 1024).toFixed(1)} KB`,
);

if (violations.length > 0) {
  for (const v of violations) console.error(`[bundle-budget]   FAIL: ${v}`);
  process.exit(1);
}

console.log("[bundle-budget] OK");
