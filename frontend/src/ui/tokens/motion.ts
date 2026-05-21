/**
 * Synaptic Calm — motion tokens.
 *
 * All motion in this interface is spring physics, never eased duration
 * tweens (plan section 3.4). Springs feel alive; eases feel scripted.
 *
 * These presets are consumed by `motion` (Framer) `transition` props and
 * by hand-rolled requestAnimationFrame loops in the canvas viz.
 */

export interface Spring {
  readonly type: "spring";
  readonly stiffness: number;
  readonly damping: number;
}

/** Immediate confirmations — button press, toggle, toast. */
export const springSnap: Spring = {
  type: "spring",
  stiffness: 600,
  damping: 40,
};

/** The default. Most layout and component motion. */
export const springBase: Spring = {
  type: "spring",
  stiffness: 240,
  damping: 28,
};

/** Ambient, large-surface motion — panel reflow, surface transitions. */
export const springSoft: Spring = {
  type: "spring",
  stiffness: 120,
  damping: 24,
};

/** Sustained, slow motion — confidence breathing, idle pulses. */
export const springBreath: Spring = {
  type: "spring",
  stiffness: 40,
  damping: 18,
};

export const spring = {
  snap: springSnap,
  base: springBase,
  soft: springSoft,
  breath: springBreath,
} as const;

export type SpringName = keyof typeof spring;

/**
 * Named motion primitives — used by token, never redefined per component.
 * Durations are in milliseconds. See plan section 3.4 for the catalog.
 */
export const motionPrimitive = {
  /** Radial expand on A2A event arrival. */
  synapsePulse: {
    durationMs: 200,
    scaleFrom: 0,
    scaleTo: 2.4,
    opacityFrom: 1,
    opacityTo: 0,
  },
  /** Gradient line traversing a phase change. */
  phaseSweep: { durationMs: 640 },
  /** Animated dashed stroke on A2A debate edges. */
  flowLine: { dashLength: 6, speedPxPerSec: 48 },
  /** Confidence gauge breathing modulation. */
  confidenceBreath: { amplitudePct: 2, frequencyHz: 0.5 },
  /** Generative-UI fragment reveal. */
  reveal: { scaleFrom: 0.96, staggerMs: 40 },
  /** Non-focused panel hush. */
  hush: { desaturatePct: 8, opacityDeltaPct: 4 },
} as const;

/**
 * Resolve whether motion should run at all. Components should call this
 * (or use the matching media query) before animating; reduced-motion is
 * a hard contract, not a suggestion.
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
