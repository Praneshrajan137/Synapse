import { useUIStore } from "@/app/store/uiStore";
import { type OverrideRequest, api } from "@/infrastructure/api/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

/**
 * Decision use-cases — React Query hooks bridging UI and the gateway.
 * City scope is read from the UI store so every surface stays in sync.
 */

export function useRecentDecisions(limit = 40) {
  const city = useUIStore((s) => s.city);
  return useQuery({
    queryKey: ["decisions", "recent", city, limit],
    queryFn: () => api.recentDecisions(limit, city),
    refetchInterval: 8_000,
  });
}

export function useDecision(id: string | undefined) {
  return useQuery({
    queryKey: ["decision", id],
    queryFn: () => api.decision(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useEscalations() {
  const city = useUIStore((s) => s.city);
  return useQuery({
    queryKey: ["escalations", city],
    queryFn: () => api.escalations(city),
    refetchInterval: 10_000,
  });
}

export function useSubmitOverride() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      decisionId,
      request,
    }: { decisionId: string; request: OverrideRequest }) =>
      api.submitOverride(decisionId, request),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["escalations"] });
      void queryClient.invalidateQueries({ queryKey: ["decisions"] });
    },
  });
}
