// ============================================================================
// Testing layer 3 — Contract. The DTCG token files and the generated TS API
// must hold their shape so producers (build) and consumers (frontend,
// deck.gl) co-evolve safely.
// ============================================================================
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import { ROOT } from "./_load.mjs";
import * as tokensApi from "../dist/tokens.ts";

const require = createRequire(import.meta.url);

function validateNode(node, path, errors) {
  if (node === null || typeof node !== "object") {
    errors.push(`${path}: not an object`);
    return;
  }
  if (Object.prototype.hasOwnProperty.call(node, "$value")) {
    const v = node.$value;
    const ok =
      typeof v === "string" ||
      typeof v === "number" ||
      (v && typeof v === "object" && "light" in v && "dark" in v);
    if (!ok) errors.push(`${path}: invalid $value shape`);
  } else {
    for (const [k, child] of Object.entries(node)) {
      if (k.startsWith("$")) continue;
      validateNode(child, `${path}.${k}`, errors);
    }
  }
}

describe("Contract — DTCG token files", () => {
  for (const file of ["primitives", "agents", "semantic"]) {
    it(`${file}.tokens.json is structurally valid DTCG`, () => {
      const tree = JSON.parse(readFileSync(join(ROOT, "tokens", `${file}.tokens.json`), "utf8"));
      const errors = [];
      for (const [k, child] of Object.entries(tree)) {
        if (k.startsWith("$")) continue;
        validateNode(child, k, errors);
      }
      expect(errors).toEqual([]);
    });
  }
});

describe("Contract — generated tokens.ts API surface", () => {
  it("exports the documented functions and constants", () => {
    expect(typeof tokensApi.confidenceColor).toBe("function");
    expect(typeof tokensApi.confidenceZone).toBe("function");
    expect(typeof tokensApi.agentVar).toBe("function");
    expect(typeof tokensApi.agentRgb).toBe("function");
    expect(typeof tokensApi.tierRgb).toBe("function");
    expect(tokensApi.AGENTS).toHaveLength(8);
    expect(tokensApi.CONFIDENCE_GATE).toEqual({ low: 0.7, high: 0.8 });
  });

  it("agentRgb and tierRgb return [r,g,b] triplets in range", () => {
    for (const a of tokensApi.AGENTS) {
      const rgb = tokensApi.agentRgb(a, "dark");
      expect(rgb).toHaveLength(3);
      for (const ch of rgb) expect(ch).toBeGreaterThanOrEqual(0), expect(ch).toBeLessThanOrEqual(255);
    }
    expect(tokensApi.tierRgb(1, "light")).toHaveLength(3);
  });

  it("unknown agent / tier throws", () => {
    expect(() => tokensApi.agentRgb("nonexistent")).toThrow();
    expect(() => tokensApi.tierRgb(99)).toThrow();
  });
});

describe("Contract — Tailwind preset", () => {
  it("exposes theme.extend.colors bound to CSS variables", () => {
    const preset = require(join(ROOT, "dist", "tailwind-preset.cjs"));
    expect(preset.theme.extend.colors).toBeDefined();
    expect(preset.theme.extend.colors.surface.canvas).toBe("var(--color-surface-canvas)");
    expect(preset.theme.extend.colors.agent["demand-prophet"]).toBe(
      "var(--color-agent-demand-prophet)",
    );
  });
});
