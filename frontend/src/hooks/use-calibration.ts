import type { CalibrationResponse } from "@domain/operations";
import type { City } from "@domain/primitives";
import { metricQueryKey } from "@lib/query-keys";
import { useCityStore } from "@state/city.store";
import { useQuery } from "@tanstack/react-query";
import { useSynapseApi } from "./use-synapse-api";

export interface UseCalibrationParams {
  readonly windowHours?: number;
  readonly includeSynthetic?: boolean;
  readonly city?: City;
}

/**
 * System confidence calibration (ADR-047) from the scored outcomes — the
 * reliability curve + Brier. Calibration moves slowly; 60s cadence. The city
 * + include_synthetic + window are part of the cache key so toggling them
 * refetches cleanly (FE-INV-016).
 */
export function useCalibration(params: UseCalibrationParams = {}) {
  const api = useSynapseApi();
  const activeCity = useCityStore((s) => s.city);
  const city = params.city ?? activeCity;
  const windowHours = params.windowHours ?? 168;
  const includeSynthetic = params.includeSynthetic ?? false;
  return useQuery<CalibrationResponse>({
    queryKey: metricQueryKey("system-calibration", city, { windowHours, includeSynthetic }),
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
