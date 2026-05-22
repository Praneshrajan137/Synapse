// ============================================================================
// SYNAPSE Chromatic — contrast + CVD audit report.
//
// Prints the full WCAG/APCA audit and agent-distinctness matrix to stdout,
// and writes dist/contrast-report.html — a swatch sheet rendered in normal
// vision plus deuteranopia / protanopia / tritanopia simulation for human
// review (the part automation cannot fully certify).
// ============================================================================
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { formatHex } from "culori";
import { wcag, apca } from "../build/contrast.mjs";
import { deltaEOK, simulateCvd, CVD_TYPES } from "../build/cvd.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TOKENS = JSON.parse(readFileSync(join(ROOT, "dist", "tokens.json"), "utf8")).tokens;
const px = (p, th) => ({ mode: "oklch", ...TOKENS[p][th].oklch });
const AGENTS = [
  "demand-prophet", "routing-navigator", "inventory-sentinel", "freshness-guardian",
  "pricing-oracle", "disruption-shield", "supplier-trust", "sustainability-agent",
];

let out = "SYNAPSE Chromatic System — contrast + CVD audit\n";
out += "=".repeat(64) + "\n";

for (const theme of ["dark", "light"]) {
  out += `\n[${theme}] text on surface — WCAG ratio / APCA Lc\n`;
  for (const s of ["canvas", "panel", "raised", "overlay"]) {
    for (const t of ["primary", "secondary", "tertiary"]) {
      const bg = px(`color.surface.${s}`, theme);
      const fg = px(`color.text.${t}`, theme);
      out += `  ${t.padEnd(10)} on ${s.padEnd(8)}  WCAG ${wcag(fg, bg).toFixed(2).padStart(6)}   APCA ${Math.abs(apca(fg, bg)).toFixed(1).padStart(6)}\n`;
    }
  }
}

for (const theme of ["dark", "light"]) {
  const cols = AGENTS.map((a) => px(`color.agent.${a}`, theme));
  let min = Infinity;
  for (let i = 0; i < 8; i++) for (let j = i + 1; j < 8; j++) min = Math.min(min, deltaEOK(cols[i], cols[j]));
  out += `\n[${theme}] agent palette — min pairwise deltaEOK\n  normal       ${min.toFixed(4)}\n`;
  for (const cvd of CVD_TYPES) {
    let m = Infinity;
    for (let i = 0; i < 8; i++)
      for (let j = i + 1; j < 8; j++)
        m = Math.min(m, deltaEOK(simulateCvd(cols[i], cvd), simulateCvd(cols[j], cvd)));
    out += `  ${cvd.padEnd(13)}${m.toFixed(4)}\n`;
  }
}
process.stdout.write(out);

// --- HTML swatch sheet ------------------------------------------------------
const swatch = (label, oklch) => {
  const base = formatHex({ mode: "oklch", ...oklch });
  const cells = [["normal", base]];
  for (const cvd of CVD_TYPES) {
    cells.push([cvd, formatHex(simulateCvd({ mode: "oklch", ...oklch }, cvd))]);
  }
  const chips = cells
    .map(([n, hex]) => `<div class="chip"><span style="background:${hex}"></span><code>${n}</code></div>`)
    .join("");
  return `<tr><th>${label}</th><td><div class="row">${chips}</div></td></tr>`;
};

const section = (title, paths, theme) =>
  `<h2>${title} <small>(${theme})</small></h2><table>` +
  paths.map((p) => swatch(p.replace("color.", ""), TOKENS[p][theme].oklch)).join("") +
  "</table>";

const agentPaths = AGENTS.map((a) => `color.agent.${a}`);
const statePaths = ["success", "warning", "danger", "info", "neutral"].map((s) => `color.state.${s}`);
const tierPaths = [1, 2, 3, 4].map((n) => `color.tier.${n}`);
const confPaths = ["low", "escalation", "autonomous", "peak"].map((k) => `color.confidence.${k}`);

const html = `<!doctype html>
<meta charset="utf-8"><title>SYNAPSE Chromatic — CVD swatch sheet</title>
<style>
 body{font:14px system-ui;background:#0b0f14;color:#e9edf2;margin:24px}
 h1{font-size:18px} h2{font-size:14px;margin-top:28px;text-transform:uppercase;letter-spacing:.06em}
 small{opacity:.6;text-transform:none}
 table{border-collapse:collapse;width:100%} th{text-align:left;padding:6px 12px 6px 0;font-weight:600;white-space:nowrap}
 td{padding:4px 0} .row{display:flex;gap:14px;flex-wrap:wrap}
 .chip{display:flex;flex-direction:column;align-items:center;gap:4px}
 .chip span{width:72px;height:40px;border-radius:6px;display:block;outline:1px solid #ffffff22}
 code{font-size:10px;opacity:.65}
</style>
<h1>SYNAPSE Chromatic System — colour-vision-deficiency review sheet</h1>
<p>Each colour is shown in normal vision and under deuteranopia / protanopia /
tritanopia simulation. The 8 agents and 5 state colours must stay tellable
apart in every column. Colour is never the sole channel (INV-CLR-011).</p>
${section("Agents", agentPaths, "dark")}
${section("State", statePaths, "dark")}
${section("Decision tiers", tierPaths, "dark")}
${section("Confidence stops", confPaths, "dark")}
${section("Agents", agentPaths, "light")}
`;
writeFileSync(join(ROOT, "dist", "contrast-report.html"), html, "utf8");
process.stdout.write("\nwrote dist/contrast-report.html (CVD swatch sheet)\n");
