import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { AGENT_NAMES, agentColor, confidenceColor, signal, tierColor } from "./colors";

const HEX = /^#[0-9a-f]{6}$/i;

describe("color tokens", () => {
  it("defines a hue for all eight canonical agents", () => {
    expect(AGENT_NAMES).toHaveLength(8);
    for (const name of AGENT_NAMES) {
      expect(agentColor[name]).toMatch(HEX);
    }
  });

  it("gives every agent a visually distinct hue", () => {
    const hues = Object.values(agentColor);
    expect(new Set(hues).size).toBe(hues.length);
  });

  it("maps confidence to escalating signal colors", () => {
    expect(confidenceColor(0.95)).toBe(signal.ok);
    expect(confidenceColor(0.72)).toBe(signal.live);
    expect(confidenceColor(0.5)).toBe(signal.warn);
    expect(confidenceColor(0.2)).toBe(signal.stop);
  });

  it("treats the HITL band boundaries inclusively (tenet T-4)", () => {
    expect(confidenceColor(0.9)).toBe(signal.ok);
    expect(confidenceColor(0.65)).toBe(signal.live);
    expect(confidenceColor(0.4)).toBe(signal.warn);
  });

  it("has a distinct accent per decision tier", () => {
    const colors = Object.values(tierColor);
    expect(new Set(colors).size).toBe(colors.length);
  });

  it("does not drift from the CSS @theme source of truth", () => {
    const css = readFileSync(
      resolve(import.meta.dirname, "../../styles/globals.css"),
      "utf8",
    ).toLowerCase();
    for (const hex of Object.values(agentColor)) {
      expect(css).toContain(hex.toLowerCase());
    }
    for (const hex of Object.values(signal)) {
      expect(css).toContain(hex.toLowerCase());
    }
  });
});
