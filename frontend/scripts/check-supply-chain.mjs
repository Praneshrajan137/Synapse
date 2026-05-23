#!/usr/bin/env node
// SYNAPSE Console — pnpm-lock.yaml supply-chain hygiene.
//
// Validates two invariants on the pnpm lockfile:
//   1. Every package resolution uses HTTPS.
//   2. Every package resolves to registry.npmjs.org (no GitHub tarballs,
//      no private mirrors, no http:// transports).
//
// Replacement for `lockfile-lint` — that tool's pnpm parser was never
// shipped (v4 and v5 both reject pnpm-lock.yaml with "available options are
// npm,yarn"). This script is pnpm-native and zero-dependency.
//
// Invariant: I-1 ($0 cost, allowlist of OSS licenses, no paid SaaS).

import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const lockfilePath = resolve(process.cwd(), "pnpm-lock.yaml");

if (!existsSync(lockfilePath)) {
  console.error(`pnpm-lock.yaml not found at ${lockfilePath}`);
  process.exit(2);
}

const text = readFileSync(lockfilePath, "utf8");

const allowedHosts = new Set(["registry.npmjs.org"]);
const violations = [];

// pnpm v9 lockfile uses `resolution: { integrity: '...', tarball: '...' }`
// for git/tarball sources, and the implicit npm registry for the rest
// (registered via the lockfile's settings.autoInstallPeers, etc.).
// We grep both explicit and tarball URLs.
const urlRe = /(?:tarball|resolved):\s*["']?(https?:\/\/[^"'\s]+)/g;
let match;
let urlCount = 0;
while ((match = urlRe.exec(text)) !== null) {
  urlCount += 1;
  const url = match[1];
  let host;
  try {
    host = new URL(url).host;
  } catch {
    violations.push(`malformed URL: ${url}`);
    continue;
  }
  if (!url.startsWith("https://")) {
    violations.push(`non-HTTPS resolution: ${url}`);
  } else if (!allowedHosts.has(host)) {
    violations.push(`disallowed registry host (${host}): ${url}`);
  }
}

// Also check the implicit registry declared in the lockfile header.
// pnpm-lock.yaml uses `settings:` block or per-importer registry overrides.
const registryRe = /^\s*registry:\s*(\S+)\s*$/gm;
while ((match = registryRe.exec(text)) !== null) {
  const url = match[1];
  let host;
  try {
    host = new URL(url).host;
  } catch {
    violations.push(`malformed registry URL: ${url}`);
    continue;
  }
  if (!url.startsWith("https://")) {
    violations.push(`non-HTTPS registry: ${url}`);
  } else if (!allowedHosts.has(host)) {
    violations.push(`disallowed registry host (${host}): ${url}`);
  }
}

if (violations.length > 0) {
  console.error(`✗ supply-chain violations in pnpm-lock.yaml (${violations.length}):`);
  for (const v of violations) console.error(`  - ${v}`);
  process.exit(1);
}

console.log(
  `✓ pnpm-lock.yaml supply-chain check passed (${urlCount} explicit URLs, ` +
    `all HTTPS via registry.npmjs.org)`,
);
