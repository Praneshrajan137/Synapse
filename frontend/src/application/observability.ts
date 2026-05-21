import { api } from "@/infrastructure/api/client";
import { useQuery } from "@tanstack/react-query";

/** Observability use-cases — agent detail (Inspector) and topics (Streams). */

export function useAgentDetail(name: string | undefined) {
  return useQuery({
    queryKey: ["agent", "detail", name],
    queryFn: () => api.agentDetail(name ?? ""),
    enabled: Boolean(name),
  });
}

export function useTopics() {
  return useQuery({
    queryKey: ["topics"],
    queryFn: api.topics,
    refetchInterval: 10_000,
  });
}
