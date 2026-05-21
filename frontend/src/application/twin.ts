import { useUIStore } from "@/app/store/uiStore";
import type { ShockParams, ShockScenario } from "@/domain/twin";
import { api } from "@/infrastructure/api/client";
import { useMutation, useQuery } from "@tanstack/react-query";

/** Digital Twin use-cases — topology and the Monte Carlo what-if. */

export function useTwinTopology() {
  const city = useUIStore((s) => s.city);
  return useQuery({
    queryKey: ["twin", "topology", city],
    queryFn: () => api.twinTopology(city),
  });
}

export function useWhatIf() {
  return useMutation({
    mutationFn: ({
      scenario,
      params,
    }: {
      scenario: ShockScenario;
      params: ShockParams;
    }) => api.twinWhatIf(scenario, params),
  });
}
