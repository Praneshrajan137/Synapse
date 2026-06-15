import type { CalibrationResponse } from "@domain/operations";
import type { City } from "@domain/primitives";
import { useQuery } from "@tanstack/react-query";
import { useSynapseApi } from "./use-synapse-api";

export interface UseCalibrationParams {
  readonly windowHours?: number;
  readonly includeSynthetic?: boolean;
  readonly city?: City;
}

/**
 * System confidence calibration (ADR-046) from the scored outcomes — the
 * reliability curve + Brier. Calibration moves slowly; 60s cadence. The city
 * + include_synthetic + window are part of the cache key so toggling them
 * refetches cleanly (FE-INV-016).
 */
export function useCalibration(params: UseCalibrationParams = {}) {
  const api = useSynapseApi();
  const windowHours = params.windowHours ?? 168;
  const includeSynthetic = params.includeSynthetic ?? false;
  return useQuery<CalibrationResponse>({
    queryKey: ["system-calibration", windowHours, includeSynthetic, params.city ?? null],
    queryFn: () =>
      api.getCalibration({
        window_hours: windowHours,
        include_synthetic: includeSynthetic,
        ...(params.city ? { city: params.city } : {}),
      }),
    refetchInterval: 60_000,
    staleTime: 45_000,
    retry: false,
  });
}
