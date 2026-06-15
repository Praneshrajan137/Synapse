import type { SloResponse } from "@domain/operations";
import { useQuery } from "@tanstack/react-query";
import { useSynapseApi } from "./use-synapse-api";

/**
 * Per-tier multi-window SLO burn (ADR-047), polled from GET /api/v1/system/slo.
 *
 * 30s cadence. The http-client already does Full-Jitter retries (FE-INV-006);
 * react-query retry is off so the surface reaches the honest `source: "unknown"`
 * state promptly instead of spinning (mirrors usePosture).
 */
export function useSlo() {
  const api = useSynapseApi();
  return useQuery<SloResponse>({
    queryKey: ["system-slo"],
    queryFn: () => api.getSlo(),
    refetchInterval: 30_000,
    staleTime: 20_000,
    retry: false,
  });
}
