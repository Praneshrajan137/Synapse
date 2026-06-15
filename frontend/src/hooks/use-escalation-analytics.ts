import type { EscalationAnalytics } from "@domain/operations";
import type { City } from "@domain/primitives";
import { useQuery } from "@tanstack/react-query";
import { useSynapseApi } from "./use-synapse-api";

export interface UseEscalationAnalyticsParams {
  readonly windowHours?: number;
  readonly city?: City;
}

/**
 * Escalation pressure + resolution analytics (ADR-047), polled from
 * GET /api/v1/escalations/analytics. 30s cadence.
 */
export function useEscalationAnalytics(params: UseEscalationAnalyticsParams = {}) {
  const api = useSynapseApi();
  const windowHours = params.windowHours ?? 24;
  return useQuery<EscalationAnalytics>({
    queryKey: ["escalation-analytics", windowHours, params.city ?? null],
    queryFn: () =>
      api.getEscalationAnalytics({
        window_hours: windowHours,
        ...(params.city ? { city: params.city } : {}),
      }),
    refetchInterval: 30_000,
    staleTime: 20_000,
    retry: false,
  });
}
