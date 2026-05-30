import { type ChromaticTheme, confidenceColor, confidenceZone } from "@lib/chromatics";
import { cn } from "@lib/cn";
import type { Tier } from "@lib/confidence";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo } from "react";

/**
 * Pulse — the Cortex's ambient heartbeat. The firehose rendered as *weather*,
 * not a feed (SENSORIUM P2: two clocks).
 *
 * The system decides ≥80 % of cases in <100 ms; no human can or should read
 * that stream item-by-item. So the Pulse encodes the *aggregate* pre-
 * attentively:
 *   • BEAT cadence  — the live decision rate (calm by construction; never
 *     strobes — it is bounded to a restful range).
 *   • COLOUR TEMP   — the rolling aggregate confidence, on the gate-anchored
 *     OKLCH diverging scale with VSUP suppression: a confident system glows a
 *     cool, saturated teal; a doubtful one drains toward a warm, desaturated
 *     red exactly at the I-5 gate (P5 — confidence rendered, not labelled).
 *   • RING TEXTURE  — the tier mix (Tier-1 reflex vs the rare heavy Tier-4
 *     deliberation), as a segmented arc.
 *
 * Quiet by default (P3): at rest the halo is faint and the breath is slow.
 * Colour is rationed — it intensifies only as confidence and load demand
 * attention.
 *
 * Accessibility: a single `role="img"` with a full-sentence label; the rate,
 * confidence %, and zone word are ALSO rendered as text (colour is never the
 * sole channel — INV-CLR-011). `prefers-reduced-motion` removes the breath
 * entirely and the static ring + numerals carry all the information (FE-P6).
 */

const TIER_ORDER: readonly Tier[] = ["tier_1", "tier_2", "tier_3", "tier_4"];
const TIER_STROKE: Record<Tier, string> = {
  tier_1: "stroke-tier-1",
  tier_2: "stroke-tier-2",
  tier_3: "stroke-tier-3",
  tier_4: "stroke-tier-4",
};

const ZONE_WORD = {
  low: "needs review",
  escalation: "on the gate",
  autonomous: "autonomous",
} as const;

const RING_RADIUS = 44;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

/**
 * Map a decision rate (per minute) to a calm beat period in ms. Bounded so the
 * Pulse is restful at idle and never strobes under load: 0/min → 2600 ms,
 * ramping linearly to 120/min → 900 ms, then held.
 */
export function beatPeriodMs(ratePerMin: number): number {
  if (!Number.isFinite(ratePerMin) || ratePerMin <= 0) return 2600;
  const clamped = Math.min(ratePerMin, 120);
  return Math.round(2600 - (clamped / 120) * (2600 - 900));
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return value < 0 ? 0 : value > 1 ? 1 : value;
}

export interface PulseProps {
  /** Live decision rate, decisions per minute. */
  readonly rate: number;
  /** Rolling aggregate confidence in [0,1], or null when no decisions yet. */
  readonly confidence: number | null;
  /** Count of recent decisions per tier — drives the ring texture. */
  readonly tierMix?: Partial<Record<Tier, number>> | undefined;
  /** Theme for the OKLCH scale. Defaults to dark (ops-centre default). */
  readonly theme?: ChromaticTheme | undefined;
  readonly className?: string | undefined;
}

export function Pulse({ rate, confidence, tierMix, theme = "dark", className }: PulseProps) {
  const reduced = useReducedMotion() ?? false;

  const hasSignal = confidence !== null && Number.isFinite(confidence);
  const conf = hasSignal ? clamp01(confidence as number) : 0;
  const zone = hasSignal ? confidenceZone(conf) : null;
  const period = beatPeriodMs(rate);

  // The pulse colour: gate-anchored diverging scale + VSUP. When there is no
  // signal we stay on the quiet neutral base — never a fake confident glow.
  const pulseColor = hasSignal
    ? confidenceColor(conf, { theme, vsup: true })
    : "var(--syn-neutral-mix)";
  const haloColor = `color-mix(in oklab, ${pulseColor} 22%, transparent)`;

  const arcs = useMemo(() => {
    const counts = TIER_ORDER.map((t) => Math.max(0, tierMix?.[t] ?? 0));
    const total = counts.reduce((a, b) => a + b, 0);
    if (total === 0) return null;
    let offset = 0;
    const out: { tier: Tier; len: number; offset: number }[] = [];
    TIER_ORDER.forEach((tier, i) => {
      const len = ((counts[i] ?? 0) / total) * RING_CIRCUMFERENCE;
      if (len > 0) out.push({ tier, len, offset });
      offset += len;
    });
    return out;
  }, [tierMix]);

  const ratePretty = Math.round(Number.isFinite(rate) ? Math.max(0, rate) : 0);
  const pct = hasSignal ? Math.round(conf * 100) : null;
  const zoneWord = zone ? ZONE_WORD[zone] : null;
  const ariaLabel =
    hasSignal && zoneWord
      ? `System pulse: ${ratePretty} decisions per minute, aggregate confidence ${pct} percent — ${zoneWord}.`
      : `System pulse: ${ratePretty} decisions per minute, no confidence signal yet.`;

  return (
    <figure
      className={cn("relative isolate flex aspect-square w-full max-w-[260px] flex-col", className)}
      role="img"
      aria-label={ariaLabel}
    >
      {/* Breathing halo — the systole. Faint at rest; intensifies with confidence. */}
      <motion.div
        aria-hidden="true"
        className="absolute left-1/2 top-1/2 -z-10 size-[62%] -translate-x-1/2 -translate-y-1/2 rounded-full blur-xl"
        style={{ background: haloColor }}
        initial={false}
        animate={
          reduced ? { scale: 1, opacity: 0.6 } : { scale: [1, 1.08, 1], opacity: [0.5, 0.85, 0.5] }
        }
        transition={
          reduced
            ? { duration: 0 }
            : { duration: period / 1000, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }
        }
      />

      {/* Tier-mix ring (texture) + confidence arc (the live colour). */}
      <svg
        className="size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        {/* Quiet base ring — always present so the dial reads even at idle. */}
        <circle
          cx={50}
          cy={50}
          r={RING_RADIUS}
          fill="none"
          className="stroke-border"
          strokeOpacity={0.5}
          strokeWidth={2}
        />
        {/* Tier-mix arcs. Absent → the base ring alone communicates "idle". */}
        {arcs?.map((a) => (
          <circle
            key={a.tier}
            cx={50}
            cy={50}
            r={RING_RADIUS}
            fill="none"
            className={TIER_STROKE[a.tier]}
            strokeWidth={3}
            strokeDasharray={`${a.len} ${RING_CIRCUMFERENCE - a.len}`}
            strokeDashoffset={-a.offset}
            strokeLinecap="butt"
            transform="rotate(-90 50 50)"
          />
        ))}
        {/* Inner confidence disc — the colour temperature of the whole system. */}
        <circle cx={50} cy={50} r={30} fill={haloColor} />
        <circle
          cx={50}
          cy={50}
          r={30}
          fill="none"
          stroke={pulseColor}
          strokeOpacity={hasSignal ? 0.9 : 0.4}
          strokeWidth={1.5}
        />
      </svg>

      {/* Center readout — colour is never the sole channel (INV-CLR-011). */}
      <figcaption className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="font-mono text-3xl font-semibold tabular-nums leading-none text-ink">
          {ratePretty}
        </span>
        <span className="mt-0.5 text-2xs uppercase tracking-wider text-ink-subtle">dec / min</span>
        <span className="mt-2 inline-flex items-center gap-1.5 text-xs">
          <span
            className="size-2 rounded-full"
            style={{ background: pulseColor }}
            aria-hidden="true"
          />
          <span className="font-mono tabular-nums text-ink">{pct !== null ? `${pct}%` : "—"}</span>
          <span className="text-ink-muted">{zone ? ZONE_WORD[zone] : "no signal"}</span>
        </span>
      </figcaption>
    </figure>
  );
}
