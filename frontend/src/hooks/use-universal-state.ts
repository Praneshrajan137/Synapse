import { type UniversalState, resolveUniversalState } from "@lib/universal-state";
import { useOnlineStatus } from "./use-online-status";
import { usePosture } from "./use-posture";

/**
 * Derive the single degraded/offline-aware boolean the universal-state resolver
 * needs from the shared system posture (ADR-044 D4). A posture-fetch failure is
 * treated as degraded ("posture unknown"), never silently healthy (FE-INV-035),
 * mirroring the DegradedBanner's honesty rule.
 */
export function useDegradedPosture(): boolean {
  const posture = usePosture();
  if (posture.isError) return true; // posture unknown → surface as degraded
  return posture.data?.degraded === true;
}

export interface UseUniversalStateInput {
  /** Request in flight with no data to show yet. */
  readonly isLoading: boolean;
  /** Request failed — "failed to load", distinct from "no data yet". */
  readonly isError: boolean;
  /** Count of items the surface would render; 0 means the empty state. */
  readonly itemCount: number;
  /**
   * Explicit offline override. When omitted the hook uses the browser's
   * online/offline status (Req 10.7).
   */
  readonly isOffline?: boolean;
  /**
   * Explicit degraded override. When omitted the hook derives it from the
   * shared system posture (brownout / open breaker / posture unknown).
   */
  readonly isDegraded?: boolean;
}

/**
 * The single hook every data-bearing Surface consumes to classify its render
 * condition. It threads a React Query-style result (`isLoading`/`isError` plus
 * a derived `itemCount`) together with the shared offline and degraded signals
 * through the pure `resolveUniversalState` resolver, guaranteeing every surface
 * classifies loading/empty/error/degraded/offline/populated identically and
 * never confuses "no data yet" (empty) with "failed to load" (error)
 * (Req 10.1, 10.7, 10.8).
 *
 * Offline and degraded default to the shared browser/posture signals but can be
 * overridden by surfaces that already own a more precise signal (e.g. a
 * real-time surface passing its socket state).
 */
export function useUniversalState(input: UseUniversalStateInput): UniversalState {
  const online = useOnlineStatus();
  const degraded = useDegradedPosture();
  return resolveUniversalState({
    isLoading: input.isLoading,
    isError: input.isError,
    itemCount: input.itemCount,
    isOffline: input.isOffline ?? online,
    isDegraded: input.isDegraded ?? degraded,
  });
}
