/**
 * SYNAPSE Atlas Console — `POST /simulate` mutation.
 *
 * INV-TW-004: ≤ 10 s for n=1000. We let the user kick off via a button
 * (no auto-fire on form change — too expensive). The mutation
 * canonicalises the body (I-13) so any KV-cache prefix in the
 * orchestrator stays valid across replays.
 */
import { useMutation } from "@tanstack/react-query";

import { synapseFetcher } from "@shared/api/fetcher";

import { type SimulateRequest, type WhatIfResult, WhatIfResultSchema } from "../model/scenario";

export interface UseSimulateResult {
  readonly run: (input: SimulateRequest) => void;
  readonly result: WhatIfResult | null;
  readonly isRunning: boolean;
  readonly isError: boolean;
  readonly error: unknown;
  readonly reset: () => void;
}

export function useSimulate(): UseSimulateResult {
  const m = useMutation({
    mutationFn: async (input: SimulateRequest) => {
      const raw = await synapseFetcher<unknown>({
        url: "/simulate",
        method: "POST",
        data: input,
      });
      return WhatIfResultSchema.parse(raw);
    },
  });
  return {
    run: (input) => void m.mutate(input),
    result: m.data ?? null,
    isRunning: m.isPending,
    isError: m.isError,
    error: m.error,
    reset: () => m.reset(),
  };
}
