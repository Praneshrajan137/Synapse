/**
 * SYNAPSE Atlas Console — Agent Floor health hook.
 *
 * Polls the API gateway's `/api/v1/agents/` (returns
 * `{agents: {<name>: status}, count}`) every 10 s and exposes a typed
 * lookup keyed by `agent_name`. The Living City + Agent Floor surfaces
 * both consume this; React Query dedupes via the shared key.
 */
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { synapseFetcher } from "@shared/api/fetcher";

const AgentStatusListSchema = z.object({
  agents: z.record(z.string(), z.string()),
  count: z.number().int().nonnegative(),
});
export type AgentStatusList = z.infer<typeof AgentStatusListSchema>;

export interface UseAgentStatusesResult {
  readonly statuses: Readonly<Record<string, string>>;
  readonly isLoading: boolean;
  readonly isError: boolean;
}

export function useAgentStatuses(): UseAgentStatusesResult {
  const query = useQuery({
    queryKey: ["agent-statuses"],
    queryFn: async ({ signal }) => {
      const raw = await synapseFetcher<unknown>({
        url: "/api/v1/agents/",
        method: "GET",
        signal,
      });
      return AgentStatusListSchema.parse(raw);
    },
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
  return {
    statuses: query.data?.agents ?? {},
    isLoading: query.isLoading,
    isError: query.isError,
  };
}

/**
 * Convert an agent_name (snake_case as in spec.yaml — "demand_prophet")
 * to the gateway's expected slug ("demand-prophet"). Centralised here
 * so a future renaming is one-file.
 */
export function specNameToSlug(name: string): string {
  return name.replace(/_/g, "-");
}
