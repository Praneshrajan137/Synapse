import type { AutonomyResponse, SensorStatus } from "@domain/autonomy";
import type { WorldState } from "@domain/world-state";

/**
 * Pure derivation of the Autonomy Spine display state (ADR-053) from the
 * `GET /api/v1/system/autonomy` read. Kept pure + exhaustive so the honesty
 * invariants (FE-INV-045..048) are unit-testable without React:
 *
 *   - a fetch error / 503 is "unknown" (the loop is not observable), NEVER
 *     rendered as a healthy autonomous system;
 *   - a world with clock_advancing=false is "stalled" (degraded), NEVER live;
 *   - a null world is "unreachable" (degraded), NEVER a fabricated snapshot;
 *   - every world is flagged synthetic (it is a simulation).
 */

export interface WorldVital {
  readonly city: string;
  readonly kind: "live" | "stalled" | "unreachable";
  readonly synthetic: boolean;
  readonly fillRate: number | null;
  readonly spoilageRate: number | null;
  readonly pendingOrders: number | null;
  readonly demandRate: number | null;
  readonly restocks: number | null;
  readonly simTimeMin: number | null;
  readonly skuCount: number | null;
}

export type AutonomyView =
  | { readonly kind: "loading" }
  | { readonly kind: "unknown" }
  | {
      readonly kind: "ready";
      readonly sensorRunning: boolean;
      readonly sensorReachable: boolean;
      readonly decisionsTriggered: number | null;
      readonly polls: number | null;
      readonly worlds: ReadonlyArray<WorldVital>;
      readonly degraded: boolean;
      readonly stalledCities: ReadonlyArray<string>;
    };

function deriveWorldVital(city: string, world: WorldState | null): WorldVital {
  if (world === null) {
    return {
      city,
      kind: "unreachable",
      synthetic: true,
      fillRate: null,
      spoilageRate: null,
      pendingOrders: null,
      demandRate: null,
      restocks: null,
      simTimeMin: null,
      skuCount: null,
    };
  }
  return {
    city,
    // clock_advancing=false ⇒ the sim clock stalled = degraded (I-7).
    kind: world.clock_advancing ? "live" : "stalled",
    synthetic: world.is_synthetic,
    fillRate: world.fill_rate,
    spoilageRate: world.spoilage_rate,
    pendingOrders: world.pending_orders,
    demandRate: world.demand_rate,
    restocks: world.restocks_triggered,
    simTimeMin: world.sim_time_min,
    skuCount: Object.keys(world.inventory ?? {}).length,
  };
}

export function deriveAutonomyView(input: {
  readonly data: AutonomyResponse | undefined;
  readonly isError: boolean;
  readonly isPending: boolean;
}): AutonomyView {
  if (input.isError) return { kind: "unknown" };
  if (input.isPending || input.data === undefined) return { kind: "loading" };

  const { data } = input;
  const sensor: SensorStatus | null = data.sensor;
  const worlds = Object.entries(data.worlds)
    .map(([city, world]) => deriveWorldVital(city, world))
    .sort((a, b) => a.city.localeCompare(b.city));
  const stalledCities = worlds
    .filter((w) => w.kind === "stalled" || w.kind === "unreachable")
    .map((w) => w.city);

  return {
    kind: "ready",
    sensorRunning: sensor?.running ?? false,
    sensorReachable: sensor !== null,
    decisionsTriggered: sensor?.decisions_triggered ?? null,
    polls: sensor?.polls ?? null,
    worlds,
    degraded: data.degraded,
    stalledCities,
  };
}
