/**
 * Synaptic Calm — sound engine.
 *
 * Eight short cues, fully synthesized with the Web Audio API — no sample
 * files (plan tenet T-12: zero cost, tiny bundle). Every cue has a
 * visual analog elsewhere in the UI so deaf operators lose nothing;
 * sound is opt-in and off by default.
 */

import { useUIStore } from "@/app/store/uiStore";
import { useCallback } from "react";

export type SoundCue =
  | "a2a" // agent proposal arrives
  | "phase" // orchestrator phase transition
  | "escalation" // HITL escalation incoming
  | "confirm" // operator action accepted
  | "anomaly" // disruption alert
  | "drift"; // digital-twin KL divergence

interface ToneSpec {
  freq: number;
  type: OscillatorType;
  startMs: number;
  durationMs: number;
  /** Peak gain, 0..1, before the master gain. */
  gain: number;
  /** Linear frequency glide target, if any. */
  glideToFreq?: number;
}

/** Cue → layered tone specs. Tuned quiet and brief (plan section 3.5). */
const CUES: Record<SoundCue, ToneSpec[]> = {
  a2a: [{ freq: 800, type: "triangle", startMs: 0, durationMs: 12, gain: 0.05 }],
  phase: [
    { freq: 520, type: "sine", startMs: 0, durationMs: 80, gain: 0.07, glideToFreq: 700 },
  ],
  escalation: [
    { freq: 660, type: "sine", startMs: 0, durationMs: 200, gain: 0.12 },
    { freq: 550, type: "sine", startMs: 200, durationMs: 200, gain: 0.12 },
    { freq: 440, type: "sine", startMs: 400, durationMs: 240, gain: 0.12 },
  ],
  confirm: [{ freq: 1200, type: "sine", startMs: 0, durationMs: 40, gain: 0.08 }],
  anomaly: [
    { freq: 180, type: "sawtooth", startMs: 0, durationMs: 200, gain: 0.09 },
    { freq: 184, type: "sawtooth", startMs: 0, durationMs: 200, gain: 0.09 },
  ],
  drift: [
    { freq: 330, type: "sine", startMs: 0, durationMs: 320, gain: 0.06 },
    { freq: 392, type: "sine", startMs: 60, durationMs: 320, gain: 0.06 },
  ],
};

class SoundEngine {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;

  /** Lazily create the AudioContext (must follow a user gesture). */
  private ensureContext(): AudioContext | null {
    if (typeof window === "undefined") return null;
    const Ctor =
      window.AudioContext ??
      (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    if (!this.ctx) {
      this.ctx = new Ctor();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0.8;
      this.master.connect(this.ctx.destination);
    }
    if (this.ctx.state === "suspended") {
      void this.ctx.resume();
    }
    return this.ctx;
  }

  play(cue: SoundCue): void {
    const ctx = this.ensureContext();
    if (!ctx || !this.master) return;

    const now = ctx.currentTime;
    for (const spec of CUES[cue]) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const start = now + spec.startMs / 1000;
      const end = start + spec.durationMs / 1000;

      osc.type = spec.type;
      osc.frequency.setValueAtTime(spec.freq, start);
      if (spec.glideToFreq !== undefined) {
        osc.frequency.linearRampToValueAtTime(spec.glideToFreq, end);
      }

      // Fast attack, smooth exponential release — no clicks.
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(spec.gain, start + 0.006);
      gain.gain.exponentialRampToValueAtTime(0.0001, end);

      osc.connect(gain);
      gain.connect(this.master);
      osc.start(start);
      osc.stop(end + 0.02);
    }
  }
}

let engine: SoundEngine | null = null;

function getSoundEngine(): SoundEngine {
  if (!engine) engine = new SoundEngine();
  return engine;
}

/**
 * Hook returning a `play` function gated by the operator's sound
 * preference. Calling it when sound is disabled is a safe no-op.
 */
export function useSound(): { play: (cue: SoundCue) => void; enabled: boolean } {
  const enabled = useUIStore((s) => s.soundEnabled);
  const play = useCallback(
    (cue: SoundCue) => {
      if (!enabled) return;
      getSoundEngine().play(cue);
    },
    [enabled],
  );
  return { play, enabled };
}
