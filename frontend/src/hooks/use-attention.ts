import { type AttentionItem, rankAttention, useAttentionAck } from "@state/attention.store";
import { useEscalationStore } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import { useMemo } from "react";
import { usePosture } from "./use-posture";

export interface UseAttentionResult {
  /** Ranked, deduped attention items — most important first. */
  readonly items: ReadonlyArray<AttentionItem>;
  /** The single most important item, if any. */
  readonly top: AttentionItem | undefined;
  /** Count of items that require a human decision (escalations). */
  readonly actionableCount: number;
  acknowledge(key: string): void;
}

/**
 * The attention spine (Sprint 18). Aggregates every operator-facing signal —
 * pending escalations, system posture (brownout/breakers), disruptions, twin
 * divergence, and a dropped live feed — into one ranked list. Reads the
 * existing stores + the shared posture query, so it adds no new transport and
 * no second socket. Consumed by the Shell's AttentionBeacon.
 */
export function useAttention(): UseAttentionResult {
  const escalations = useEscalationStore((s) => s.entries);
  const disruptions = useFirehoseStore((s) => s.disruptions.items);
  const twin = useFirehoseStore((s) => s.twin.items);
  const connection = useFirehoseStore((s) => s.connection);
  const acknowledged = useAttentionAck((s) => s.acknowledged);
  const acknowledge = useAttentionAck((s) => s.acknowledge);
  const posture = usePosture();

  const items = useMemo(
    () =>
      rankAttention({
        escalations,
        posture: posture.data,
        postureError: posture.isError,
        disruptions,
        twin,
        connection,
        acknowledged,
      }),
    [escalations, posture.data, posture.isError, disruptions, twin, connection, acknowledged],
  );

  return {
    items,
    top: items[0],
    actionableCount: items.filter((i) => i.actionable).reduce((acc, i) => acc + i.count, 0),
    acknowledge,
  };
}
