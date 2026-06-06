import { beatPeriodMs } from "@ds/compounds/Pulse";

/**
 * Ambient sonification of the Cortex pulse (SENSORIUM §5.4 — stretch).
 *
 * A control room you can HEAR lets the operator look away. A barely-audible
 * tick whose pitch tracks aggregate confidence and whose rhythm tracks the
 * decision cadence (the visual Pulse, sonified). Strictly opt-in and OFF by
 * default; silence is the healthy state, and starting requires a user gesture
 * (Web Audio autoplay policy + courtesy). It must NEVER be required to operate
 * the system — full parity with the visual + textual channels.
 *
 * The pitch/cadence MAPPINGS are pure and unit-tested; the audio engine is a
 * thin, guarded wrapper that no-ops where Web Audio is unavailable (SSR, jsdom).
 */

/** Confidence in [0,1] → pitch in Hz (a calm low–mid range, ~200–600 Hz). */
export function confidenceToFrequency(confidence: number): number {
  const c = Number.isFinite(confidence) ? Math.min(1, Math.max(0, confidence)) : 0;
  return Math.round(200 + c * 400);
}

/** Decision rate (per minute) → beat interval (ms). Shares the Pulse cadence. */
export function rateToIntervalMs(ratePerMin: number): number {
  return beatPeriodMs(ratePerMin);
}

export interface PulseSignal {
  readonly rate: number;
  readonly confidence: number;
}

type AudioCtor = typeof AudioContext;

function getAudioCtor(): AudioCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { AudioContext?: AudioCtor; webkitAudioContext?: AudioCtor };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

/** True when the runtime can actually produce audio (not jsdom/SSR). */
export function sonificationSupported(): boolean {
  return getAudioCtor() !== null;
}

/**
 * Minimal pulse sonifier. `start()` must be called from a user gesture.
 * `update()` retunes pitch + cadence live. `stop()` is idempotent and releases
 * the audio context.
 */
export class PulseSonifier {
  private ctx: AudioContext | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = false;
  private frequency = 300;
  private intervalMs = 2400;

  get isRunning(): boolean {
    return this.running;
  }

  start(): void {
    if (this.running) return;
    const Ctor = getAudioCtor();
    if (!Ctor) return; // no-op where Web Audio is unavailable
    this.ctx = new Ctor();
    this.running = true;
    this.scheduleNext();
  }

  update(signal: PulseSignal): void {
    this.frequency = confidenceToFrequency(signal.confidence);
    this.intervalMs = rateToIntervalMs(signal.rate);
  }

  stop(): void {
    this.running = false;
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.ctx) {
      void this.ctx.close().catch(() => undefined);
      this.ctx = null;
    }
  }

  private scheduleNext(): void {
    if (!this.running || !this.ctx) return;
    this.tick();
    this.timer = setTimeout(() => this.scheduleNext(), this.intervalMs);
  }

  private tick(): void {
    const ctx = this.ctx;
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = this.frequency;
    // A short, gentle envelope — a soft "tick", peak gain intentionally low.
    const now = ctx.currentTime;
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.06, now + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.18);
    osc.connect(gain).connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.2);
  }
}
