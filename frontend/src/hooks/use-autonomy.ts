import type { AutonomyResponse } from "@domain/autonomy";
import { useCityStore } from "@state/city.store";
import { useQuery } from "@tanstack/react-query";
import { useSynapseApi } from "./use-synapse-api";

/**
 * The Autonomy Spine read (ADR-053): the twin's live per-city world_state
 * joined with the SensorLoop's self-initiation counters, from
 * `GET /api/v1/system/autonomy`.
 *
 * 10s cadence — the world advances on a background clock and reorder-point
 * breaches happen on the order of seconds; a poll against an in-process
 * snapshot is the honest transport (world state is NOT on a frozen Kafka topic,
 * same reasoning as usePosture).
 *
 * Consumers treat a fetch error / 503 as "autonomy unknown" (the loop is not
 * observable right now), distinct from a `degraded=true` partial read. Neither
 * is ever rendered as a healthy, fully-autonomous system.
 */
export function useAutonomy() {
  const api = useSynapseApi();
  const city = useCityStore((s) => s.city);
  return useQuery<AutonomyResponse>({
    queryKey: ["system-autonomy", city],
    queryFn: () => api.getAutonomy({ city }),
    refetchInterval: 10_000,
    staleTime: 8_000,
    // The http-client already runs Full-Jitter attempts (FE-INV-006); the 10s
    // refetch IS the retry loop. Don't delay the honest "unknown" state.
    retry: false,
  });
}
