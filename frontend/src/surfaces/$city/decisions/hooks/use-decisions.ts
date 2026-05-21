/**
 * SYNAPSE Atlas Console — Decision Trace infinite query.
 *
 * Wraps `/api/v1/decisions/recent` with TanStack Query's
 * `useInfiniteQuery`. Cursor pagination is opaque — we just hand the
 * server its `next_cursor` back.
 *
 * Filters travel via `tier` and `escalated` query params. Free-text
 * search and the `since`/`until` window are S3 client-side filters
 * because the backend doesn't yet expose them; the server filter set
 * grows in S5.
 */
import { useInfiniteQuery } from "@tanstack/react-query";

import { synapseFetcher } from "@shared/api/fetcher";

import {
  type RecentDecisionRow,
  RecentDecisionsResponseSchema,
  type Tier,
} from "../model/decision";

export interface UseDecisionsOptions {
  readonly cityId: string;
  readonly limit?: number;
  readonly tier?: Tier | undefined;
  readonly escalated?: boolean | undefined;
  readonly enabled?: boolean;
}

export interface UseDecisionsResult {
  readonly rows: readonly RecentDecisionRow[];
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly hasNextPage: boolean;
  readonly fetchNextPage: () => void;
  readonly error: unknown;
  readonly refetch: () => Promise<unknown>;
}

export function useDecisions(options: UseDecisionsOptions): UseDecisionsResult {
  const { cityId, limit = 50, tier, escalated, enabled = true } = options;

  const query = useInfiniteQuery({
    enabled,
    queryKey: ["decisions", cityId, { limit, tier, escalated }],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }) => {
      const params: Record<string, unknown> = { limit };
      if (pageParam) params["cursor"] = pageParam;
      if (tier) params["tier"] = tier;
      if (escalated !== undefined) params["escalated"] = escalated;
      const raw = await synapseFetcher<unknown>({
        url: "/api/v1/decisions/recent",
        method: "GET",
        params,
        signal,
      });
      return RecentDecisionsResponseSchema.parse(raw);
    },
    getNextPageParam: (last) => last.next_cursor,
    staleTime: 5_000,
  });

  const rows = (query.data?.pages.flatMap((p) => p.decisions) ?? []) as readonly RecentDecisionRow[];

  return {
    rows,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    hasNextPage: Boolean(query.hasNextPage),
    fetchNextPage: () => void query.fetchNextPage(),
    error: query.error,
    refetch: () => query.refetch(),
  };
}
