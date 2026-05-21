/**
 * SYNAPSE Atlas Console — single Decision deep-fetch (B2).
 *
 * Lazy-loaded when the drawer opens. The server returns the full
 * `audit_consensus` row; we Zod-parse to fail loudly on schema drift.
 */
import { useQuery } from "@tanstack/react-query";

import { ApiError, synapseFetcher } from "@shared/api/fetcher";

import { type ConsensusDecision, ConsensusDecisionSchema } from "../model/decision";

export interface UseDecisionResult {
  readonly decision: ConsensusDecision | null;
  readonly isLoading: boolean;
  readonly isError: boolean;
  readonly notFound: boolean;
  readonly error: unknown;
}

export function useDecision(decisionId: string | null): UseDecisionResult {
  const enabled = Boolean(decisionId);

  const query = useQuery({
    enabled,
    queryKey: ["decision", decisionId],
    queryFn: async ({ signal }) => {
      if (!decisionId) throw new Error("disabled");
      const raw = await synapseFetcher<unknown>({
        url: `/api/v1/decisions/${encodeURIComponent(decisionId)}`,
        method: "GET",
        signal,
      });
      return ConsensusDecisionSchema.parse(raw);
    },
    staleTime: 30_000,
    retry: (failureCount, error) => {
      // Never retry 404 / 400 — they're definitive.
      if (error instanceof ApiError && (error.status === 404 || error.status === 400)) {
        return false;
      }
      return failureCount < 2;
    },
  });

  const notFound = query.error instanceof ApiError && query.error.status === 404;

  return {
    decision: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    notFound,
    error: query.error,
  };
}
