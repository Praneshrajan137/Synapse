#!/usr/bin/env node
// SYNAPSE Console -- the entry document's eager set, listed and judged (FE-INV-025).
//
// FE-INV-025: the heavy viz libraries are async-only chunks. After `pnpm build` this reads
// dist/index.html and lists every asset the document loads before the app can render: each
// `<script src>`, each `<link rel="modulepreload">`, `rel="preload"` and `rel="stylesheet"`,
// plus every JS chunk those reach through a STATIC import in the built code. The imports are
// followed rather than trusting the preload links alone, so a build that stopped emitting
// `modulepreload` could not hide an eager chunk. Each row shows raw and gzip bytes (zlib's
// default level, the one Vite's own build report uses), then the totals.
//
// Exits 1, naming the file and what pulls it in, when an eagerly loaded JS asset starts with
// a forbidden prefix (`deck-`, `map-`, `graph-`): those chunks may load behind a lazy
// boundary, never on the entry's critical path. Exits 1 too when there is nothing to judge --
// no dist/index.html, no module script, an asset the document names that is not in dist/, or
// a forbidden prefix that names no emitted chunk -- because an empty listing is not a pass
// (I-7).
//
// `viz-` and `visx-` are listed with their sizes but NOT forbidden, because no build has yet
// shown "/" free of them. The last build read -- a local one of 2026-08-01, not a CI run --
// loaded both eagerly: the entry imported `clsx` from `viz-*.js`, and Vite's preload helper
// and three tslib helpers from `deck-*.js` (Rollup puts a manual chunk's static dependencies
// into that chunk), while the then-eager Cockpit and Decision Detail rendered ParetoFrontier,
// hence visx. vite.config.ts's `runtime` chunk now claims those shared modules and both
// surfaces are route-split, so neither chunk is EXPECTED on the entry any more -- an
// inference from the code, not a measurement. Forbid a prefix only after a CI run's table
// shows that chunk absent.
//
// Not a byte budget: the sizes are printed for the reader and compared with nothing.
// Node stdlib only; ASCII output.

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, posix, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

/** Chunk-name prefixes that must never be on the entry's critical path (FE-INV-025). */
const FORBIDDEN_EAGER_PREFIXES = ["deck-", "map-", "graph-"];
/** Printed beside the verdict so a reader sees the decision, not only the rule. */
const LISTED_NOT_FORBIDDEN = ["viz-", "visx-"];

const distDir = resolve(dirname(fileURLToPath(import.meta.url)), "..", "dist");
const indexPath = resolve(distDir, "index.html");

/**
 * A static `import ... from "./x.js"`, `import "./x.js"` or `export ... from "./x.js"` in
 * built code. A dynamic `import("./x.js")` never matches (a parenthesis follows `import`),
 * and neither does a chunk name inside a string, such as Vite's `__vite__mapDeps` list.
 */
const STATIC_IMPORT =
  /(?:^|[;}\s/])(?:import\s*(?:[\w$]+\s*,?\s*)?(?:\{[^}]*\}|\*\s*as\s+[\w$]+)?\s*(?:from\s*)?|export\s*(?:\{[^}]*\}|\*(?:\s*as\s+[\w$]+)?)\s*from\s*)["'](\.{1,2}\/[^"']+\.m?js)["']/g;

if (!existsSync(indexPath)) {
  console.error(
    `FAIL: ${indexPath} does not exist. Run \`pnpm build\` first: with no document there is ` +
      "nothing to judge, and nothing is not a pass.",
  );
  process.exit(1);
}

const html = readFileSync(indexPath, "utf8").replace(/<!--[\s\S]*?-->/g, "");

/** dist-relative path -> { distPath, via, isJs, raw, gzip, code } */
const assets = new Map();
/** Reasons the verdict cannot be a pass. */
const problems = [];
/** Matches in built code that name no file; printed, never judged (see `record`). */
const notes = [];

// 0. Each forbidden prefix must name a chunk this build emitted. A renamed `manualChunks`
// key, or a library that left the graph, would otherwise leave the verdict below judging
// nothing while still printing PASS -- an empty selection is not a pass (G5, I-7).
const assetsDir = resolve(distDir, "assets");
const emittedJs =
  statSync(assetsDir, { throwIfNoEntry: false })?.isDirectory() === true
    ? readdirSync(assetsDir).filter((name) => /\.m?js$/.test(name))
    : [];
for (const prefix of FORBIDDEN_EAGER_PREFIXES) {
  if (!emittedJs.some((name) => name.startsWith(prefix))) {
    problems.push(
      `dist/assets holds no "${prefix}*.js" chunk, so the "${prefix}" rule judges nothing: ` +
        "vite.config.ts no longer names that chunk, or its library left the build",
    );
  }
}

/** The attributes of one start tag: names lower-cased, a bare attribute mapped to "". */
function attributesOf(tag) {
  const attributes = new Map();
  const body = tag.replace(/^<[a-zA-Z][\w-]*/, "").replace(/\/?>$/, "");
  const attribute = /([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  for (const match of body.matchAll(attribute)) {
    attributes.set(match[1].toLowerCase(), match[2] ?? match[3] ?? match[4] ?? "");
  }
  return attributes;
}

/**
 * The dist-relative path a reference names, or null when it cannot name a file in dist/:
 * another origin, a malformed escape, or a path that climbs out of dist/.
 */
function distPathOf(reference, importer) {
  const bare = reference.split(/[?#]/, 1)[0] ?? "";
  if (/^[a-z][a-z\d+.-]*:/i.test(bare) || bare.startsWith("//")) return null;
  let decoded;
  try {
    decoded = decodeURIComponent(bare);
  } catch {
    return null;
  }
  const joined =
    importer === undefined
      ? posix.normalize(decoded.replace(/^\.?\/+/, ""))
      : posix.normalize(posix.join(posix.dirname(importer), decoded));
  if (
    joined === "" ||
    joined === "." ||
    joined === ".." ||
    joined.startsWith("../") ||
    posix.isAbsolute(joined)
  ) {
    return null;
  }
  return joined;
}

/**
 * Record one eagerly loaded asset and return it, or return null when it was already
 * recorded (its new route in is still added) or cannot be measured.
 *
 * A reference written in index.html that names no file is a PROBLEM: the document would
 * fetch something that is not there, and its size is unknown. A match found by scanning
 * built code that names no file is only a NOTE: Vite never emits a static import of a chunk
 * it did not write, so such a match is the scan misreading a string, not an eager asset.
 */
function record(reference, via, isJs, importer) {
  const unmeasurable = importer === undefined ? problems : notes;
  const distPath = distPathOf(reference, importer);
  if (distPath === null) {
    unmeasurable.push(`${via}: "${reference}" does not name a file inside dist/`);
    return null;
  }
  const known = assets.get(distPath);
  if (known !== undefined) {
    known.via.add(via);
    return null;
  }
  const file = resolve(distDir, ...distPath.split("/"));
  if (statSync(file, { throwIfNoEntry: false })?.isFile() !== true) {
    unmeasurable.push(`${via}: "${reference}" names ${distPath}, which is not a file in dist/`);
    return null;
  }
  const bytes = readFileSync(file);
  const asset = {
    distPath,
    via: new Set([via]),
    isJs,
    raw: bytes.length,
    gzip: gzipSync(bytes).length,
    code: isJs ? bytes.toString("utf8") : null,
  };
  assets.set(distPath, asset);
  return asset;
}

// 1. What the document itself names.
let moduleScripts = 0;
for (const [tag, name] of html.matchAll(/<(script|link)\b[^>]*>/gi)) {
  const attributes = attributesOf(tag);
  if (name.toLowerCase() === "script") {
    const src = attributes.get("src");
    if (src === undefined) continue; // an inline script fetches nothing
    const isModule = (attributes.get("type") ?? "").toLowerCase() === "module";
    if (isModule) moduleScripts += 1;
    record(src, isModule ? "module script" : "classic script", true);
    continue;
  }
  const href = attributes.get("href");
  if (href === undefined) continue;
  const rel = (attributes.get("rel") ?? "").toLowerCase().split(/\s+/);
  if (rel.includes("modulepreload")) {
    record(href, "modulepreload", true);
  } else if (rel.includes("preload")) {
    const as = (attributes.get("as") ?? "").toLowerCase();
    record(href, `preload as=${as === "" ? "(none)" : as}`, as === "script");
  } else if (rel.includes("stylesheet")) {
    record(href, "stylesheet", false);
  }
}
if (moduleScripts === 0) {
  problems.push(
    'dist/index.html names zero <script type="module" src>: the entry is missing, so nothing ' +
      "was judged",
  );
}

// 2. Every chunk those reach through a static import, transitively.
const pending = [...assets.values()].filter((asset) => asset.isJs);
while (pending.length > 0) {
  const importer = pending.shift();
  if (importer === undefined || importer.code === null) continue;
  for (const [, specifier] of importer.code.matchAll(STATIC_IMPORT)) {
    const via = `static import from ${importer.distPath}`;
    const added = record(specifier, via, true, importer.distPath);
    if (added !== null) pending.push(added);
  }
}

// 3. The table, the totals, the verdict.
const forbiddenPrefixOf = (asset) =>
  FORBIDDEN_EAGER_PREFIXES.find((prefix) => posix.basename(asset.distPath).startsWith(prefix));
const rows = [...assets.values()];
const violations = rows.filter((asset) => asset.isJs && forbiddenPrefixOf(asset) !== undefined);
const kib = (bytes) => (bytes / 1024).toFixed(1);
const sum = (list) =>
  list.reduce((total, a) => ({ raw: total.raw + a.raw, gzip: total.gzip + a.gzip }), {
    raw: 0,
    gzip: 0,
  });
const width = Math.max("asset".length, ...rows.map((asset) => asset.distPath.length));

console.log("Eager assets of dist/index.html (FE-INV-025)");
console.log("gzip = zlib default level, as in Vite's build report; woff2 is already compressed.");
console.log(`${"raw KiB".padStart(9)} ${"gzip KiB".padStart(9)}  ${"asset".padEnd(width)}  via`);
for (const asset of rows) {
  const sizes = `${kib(asset.raw).padStart(9)} ${kib(asset.gzip).padStart(9)}`;
  console.log(`${sizes}  ${asset.distPath.padEnd(width)}  ${[...asset.via].join("; ")}`);
}
const js = rows.filter((asset) => asset.isJs);
const jsTotal = sum(js);
const allTotal = sum(rows);
console.log(
  `eager JS  : ${js.length} file(s), raw ${jsTotal.raw} B (${kib(jsTotal.raw)} KiB), ` +
    `gzip ${jsTotal.gzip} B (${kib(jsTotal.gzip)} KiB)`,
);
console.log(
  `all listed: ${rows.length} file(s), raw ${allTotal.raw} B (${kib(allTotal.raw)} KiB), ` +
    `gzip ${allTotal.gzip} B (${kib(allTotal.gzip)} KiB)`,
);
console.log(
  `forbidden eager prefixes: ${FORBIDDEN_EAGER_PREFIXES.join(", ")}; ` +
    `listed, not forbidden: ${LISTED_NOT_FORBIDDEN.join(", ")}`,
);
for (const note of notes) console.log(`note: ${note}`);

for (const problem of problems) console.error(`FAIL: ${problem}`);
for (const asset of violations) {
  console.error(
    `FAIL: ${asset.distPath} is loaded eagerly (${[...asset.via].join("; ")}), but ` +
      `"${forbiddenPrefixOf(asset)}" chunks are async-only (FE-INV-025): something on the ` +
      "entry's static import graph still pulls it in.",
  );
}
if (problems.length > 0 || violations.length > 0) {
  process.exitCode = 1;
} else {
  console.log(
    `PASS: ${js.length} eager JS file(s), none starting with ` +
      `${FORBIDDEN_EAGER_PREFIXES.join(", ")}.`,
  );
}
