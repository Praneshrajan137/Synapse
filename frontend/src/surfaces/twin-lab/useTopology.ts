import { useSynapseApi } from "@hooks/use-synapse-api";
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

// WS-4 §4d: migrated from raw fetch to the typed client. The schema
// validation happens inside api.getTopology — drift between FE and BE
// surfaces here as a SchemaViolationError, not a silent type coercion.
export function useTopology() {
  const city = useCityStore((s) => s.city);
  const api = useSynapseApi();
  return useQuery<TopologyResponse>({
    queryKey: ["topology", city],
    queryFn: async () => (await api.getTopology(city)) as TopologyResponse,
    staleTime: 60_000,
  });
}
