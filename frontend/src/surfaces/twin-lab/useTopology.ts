import { useCityStore } from "@state/city.store";
import { useQuery } from "@tanstack/react-query";

export interface TopologyNode {
  readonly id: string;
  readonly type: string;
  readonly lat?: number | null;
  readonly lon?: number | null;
}

export interface TopologyEdge {
  readonly src: string;
  readonly dst: string;
  readonly type: string;
  readonly weight?: number;
}

export interface TopologyResponse {
  readonly city: string;
  readonly nodes: ReadonlyArray<TopologyNode>;
  readonly edges: ReadonlyArray<TopologyEdge>;
  readonly generated_at: string;
}

export function useTopology() {
  const city = useCityStore((s) => s.city);
  return useQuery<TopologyResponse>({
    queryKey: ["topology", city],
    queryFn: async () => {
      const resp = await fetch(`/api/v1/topology?city=${city}`);
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
      return (await resp.json()) as TopologyResponse;
    },
    staleTime: 60_000,
  });
}
