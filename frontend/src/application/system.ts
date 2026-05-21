import { api } from "@/infrastructure/api/client";
import { useQuery } from "@tanstack/react-query";

/** System / observability use-cases — KPIs and tier distribution. */

export function useKpis() {
  return useQuery({
    queryKey: ["kpis"],
    queryFn: api.kpis,
    refetchInterval: 30_000,
  });
}

export function useTierDistribution() {
  return useQuery({
    queryKey: ["tier-distribution"],
    queryFn: api.tierDistribution,
    refetchInterval: 10_000,
  });
}
