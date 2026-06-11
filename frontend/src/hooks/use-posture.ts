import { useQuery } from "@tanstack/react-query";
import type { SystemPosture } from "@transport/synapse-api";
import { useSynapseApi } from "./use-synapse-api";

/**
 * System degradation posture (ADR-044 D4): brownout level per city + every
 * circuit breaker's state, polled from `GET /api/v1/system/posture`.
 *
 * 15s cadence — posture changes on the order of seconds-to-minutes and the
 * orchestrator read is an in-process registry snapshot, so polling is the
 * honest transport (pushing would need a new Kafka topic; the set is frozen).
 *
 * Consumers treat a fetch error as "posture unknown" — the DegradedBanner
 * renders unknown on the degraded side, never silently green (FE-INV-035).
 */
export function usePosture() {
  const api = useSynapseApi();
  return useQuery<SystemPosture>({
    queryKey: ["system-posture"],
    queryFn: () => api.getSystemPosture(),
    refetchInterval: 15_000,
    staleTime: 10_000,
    retry: 2,
  });
}
