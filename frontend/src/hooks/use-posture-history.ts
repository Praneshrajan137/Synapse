import { useEffect, useReducer, useRef } from "react";
import { usePosture } from "./use-posture";

export interface PostureSample {
  readonly ts: number;
  readonly degraded: boolean;
  readonly brownout: Record<string, string>;
  readonly breakers: Record<string, string>;
  /** false = the posture fetch failed → "posture unknown" (degraded side). */
  readonly known: boolean;
}

/**
 * A bounded, append-only history of posture samples (ADR-046) built on top of
 * the existing ~15s posture poll. Posture is polled, not pushed (frozen Kafka
 * set), so the trajectory is reconstructed client-side from each poll.
 *
 * A failed poll appends a `known: false` sample (degraded side) — the timeline
 * never silently reads healthy when the truth is unknown (FE-INV-035/042).
 * The buffer starts when the surface mounts; it is intentionally ephemeral.
 */
export function usePostureHistory(capacity = 40) {
  const posture = usePosture();
  const ref = useRef<PostureSample[]>([]);
  const lastStamp = useRef(0);
  const [, force] = useReducer((c: number) => c + 1, 0);

  const stamp = Math.max(posture.dataUpdatedAt ?? 0, posture.errorUpdatedAt ?? 0);

  useEffect(() => {
    if (stamp === 0 || stamp === lastStamp.current) return;
    lastStamp.current = stamp;
    const sample: PostureSample =
      posture.isError || !posture.data
        ? { ts: stamp, degraded: true, brownout: {}, breakers: {}, known: false }
        : {
            ts: stamp,
            degraded: posture.data.degraded,
            brownout: posture.data.brownout,
            breakers: posture.data.breakers,
            known: true,
          };
    ref.current = [...ref.current, sample].slice(-capacity);
    force();
  }, [stamp, posture.isError, posture.data, capacity]);

  return { posture, history: ref.current };
}
