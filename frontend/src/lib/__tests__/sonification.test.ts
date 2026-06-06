import {
  PulseSonifier,
  confidenceToFrequency,
  rateToIntervalMs,
  sonificationSupported,
} from "@lib/sonification";
import { describe, expect, it } from "vitest";

describe("confidenceToFrequency", () => {
  it("maps [0,1] to a calm low–mid pitch range", () => {
    expect(confidenceToFrequency(0)).toBe(200);
    expect(confidenceToFrequency(1)).toBe(600);
    expect(confidenceToFrequency(0.5)).toBe(400);
  });

  it("clamps out-of-range / non-finite input", () => {
    expect(confidenceToFrequency(-1)).toBe(200);
    expect(confidenceToFrequency(2)).toBe(600);
    expect(confidenceToFrequency(Number.NaN)).toBe(200);
  });
});

describe("rateToIntervalMs", () => {
  it("shares the visual Pulse cadence (calm at idle, bounded under load)", () => {
    expect(rateToIntervalMs(0)).toBe(2600);
    expect(rateToIntervalMs(120)).toBe(900);
  });
});

describe("PulseSonifier (guarded; jsdom has no Web Audio)", () => {
  it("reports unsupported in jsdom and start/stop are safe no-ops", () => {
    expect(sonificationSupported()).toBe(false);
    const s = new PulseSonifier();
    expect(() => {
      s.update({ rate: 30, confidence: 0.8 });
      s.start();
      s.stop();
    }).not.toThrow();
    expect(s.isRunning).toBe(false); // never started without an AudioContext
  });
});
