/**
 * Synaptic Calm — spacing & density tokens.
 *
 * 8-pt base. Three density modes the operator cycles with `⌘.`
 * (plan section 3.3). Each mode is a scale of step values in px.
 */

export const densityModes = ["comfortable", "compact", "telemetric"] as const;
export type DensityMode = (typeof densityModes)[number];

/** Step scales per density mode. Index 0..4 = xs..xl. */
export const densityScale: Record<DensityMode, readonly number[]> = {
  comfortable: [8, 12, 16, 24, 32],
  compact: [4, 6, 8, 12, 16],
  telemetric: [2, 4, 6, 8, 12],
};

export const radius = {
  xs: 4,
  sm: 6,
  md: 8,
  lg: 12,
  xl: 16,
} as const;

/** Z-index ladder — keep every layered surface honest. */
export const zIndex = {
  base: 0,
  raised: 10,
  sticky: 100,
  sidebar: 200,
  statusBar: 300,
  synapticFeed: 250,
  overlay: 1000,
  commandPalette: 1100,
  escalationHailer: 1200,
  toast: 1300,
} as const;

/** Surface latency / refresh budgets in ms (plan section 10.1). */
export const refreshBudget = {
  bridgeKpi: 30_000,
  agentHealth: 30_000,
  decisionTape: 1_000,
  tierHistogram: 10_000,
} as const;
