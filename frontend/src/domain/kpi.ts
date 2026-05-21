/**
 * KPI domain — the metrics surfaced on the Bridge ribbon.
 *
 * Every KPI carries its recent series (for the sparkline) and, where the
 * producing model is probabilistic, a conformal band — uncertainty is
 * shown, not hidden (tenets T-4, T-8).
 */

export type KpiTrend = "up" | "down" | "flat";
/** Whether a rising value is good, bad, or neutral. */
export type KpiPolarity = "higher-better" | "lower-better" | "neutral";

export interface Kpi {
  readonly id: string;
  readonly label: string;
  readonly value: number;
  /** Display unit, e.g. "%", "min", "kg". */
  readonly unit: string;
  /** Fraction digits for display. */
  readonly precision: number;
  readonly series: readonly number[];
  /** Optional conformal band aligned with `series`. */
  readonly band?: {
    readonly lower: readonly number[];
    readonly upper: readonly number[];
  };
  readonly trend: KpiTrend;
  readonly polarity: KpiPolarity;
  /** 7-day model accuracy within the conformal band, if probabilistic. */
  readonly trackRecord?: number;
}

/** Tier distribution over a window — drives the Bridge TierHistogram. */
export interface TierDistribution {
  readonly tier_1: number;
  readonly tier_2: number;
  readonly tier_3: number;
  readonly tier_4: number;
}

/**
 * Whether a KPI movement is favorable, given its polarity. Used to color
 * trend indicators — green is not "up", green is "good".
 */
export function isFavorable(trend: KpiTrend, polarity: KpiPolarity): boolean | null {
  if (trend === "flat" || polarity === "neutral") return null;
  if (polarity === "higher-better") return trend === "up";
  return trend === "down";
}
