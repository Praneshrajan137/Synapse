import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

// Req 19 — Retire Legacy Theme JavaScript.
// The audit is complete only when `src/theme/` contains no `.js` file
// (FE-INV-071). This guard is the mechanical enforcement of that absence:
// it recursively walks `src/theme/` and fails if any `.js`/`.jsx` file
// (e.g. the removed `agents.js` / `useTheme.js`) ever reappears in the tree.
const THEME_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

function collectJsFiles(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const abs = join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...collectJsFiles(abs));
    } else if (/\.jsx?$/.test(entry.name)) {
      found.push(abs);
    }
  }
  return found;
}

describe("src/theme legacy JavaScript retirement (FE-INV-071)", () => {
  it("contains no .js/.jsx files under src/theme/", () => {
    expect(collectJsFiles(THEME_DIR)).toEqual([]);
  });
});
