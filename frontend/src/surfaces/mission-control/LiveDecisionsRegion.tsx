import { type UniversalStateLabels, UniversalStateView } from "@ds/compounds";
import type { UseFirehoseResult } from "@hooks/use-firehose";
import { useDegradedPosture, useUniversalState } from "@hooks/use-universal-state";
import { useFirehoseStore } from "@state/firehose.store";
import { DecisionFirehoseTail } from "./DecisionFirehoseTail";

interface LiveDecisionsRegionProps {
  /** The Mission Control socket, owned by the surface (one multiplex per surface). */
  readonly firehose: UseFirehoseResult;
}

/**
 * Mission Control's decision tail as a classified, data-bearing region
 * (Req 8.1–8.6, 10.1): the live rows render ONLY while the feed is genuinely
 * live and healthy. Every other condition renders its own distinct
 * `data-universal-state` block instead of the last good rows:
 *
 *   - offline  — the browser is offline (never stale-as-live, Req 8.5);
 *   - error    — a `decision` payload was REJECTED on schema validation and no
 *                valid decision has superseded it yet (Req 8.2);
 *   - degraded — the system posture is degraded or unknown, OR the firehose
 *                socket is not open (not-live / reconnecting, Req 8.1, 8.4);
 *   - empty    — live and healthy, but no decision has arrived yet.
 *
 * Only this region is swapped, never the page: `<main>`, the KPI band (whose
 * authoritative counters ride a different data path) and the living map (which
 * has its own spatial boundary and an always-present non-spatial table,
 * Req 10.4) stay mounted. When populated the view renders its children bare, so
 * the DOM is exactly `DecisionFirehoseTail` with no added chrome.
 */
export function LiveDecisionsRegion({ firehose }: LiveDecisionsRegionProps) {
  const degradedPosture = useDegradedPosture();
  const decisionCount = useFirehoseStore((s) => s.decisions.items.length);
  // Only the channel this region renders can put it in error: a rejected
  // cognition frame is not evidence that the decision rows are wrong.
  const rejection = firehose.rejections.find((r) => r.channel === "decision");
  const state = useUniversalState({
    // A socket that is not open is not-live (degraded), never "loading": the
    // resolver ranks degraded above loading, so this region has no loading phase.
    isLoading: false,
    isError: rejection !== undefined,
    itemCount: decisionCount,
    // Passing `isDegraded` REPLACES useUniversalState's posture default, so the
    // posture signal is OR-ed in here rather than lost to the socket signal.
    isDegraded: degradedPosture || !firehose.connected,
  });
  const labels = regionLabels(firehose.connected, rejection?.reason);

  return (
    <UniversalStateView state={state} labels={labels}>
      <DecisionFirehoseTail />
    </UniversalStateView>
  );
}

function regionLabels(
  connected: boolean,
  rejectionReason: string | undefined,
): UniversalStateLabels {
  const reason = rejectionReason === undefined ? "" : ` (${rejectionReason})`;
  const labels: UniversalStateLabels = {
    emptyTitle: "Waiting for the firehose…",
    emptyDetail: "The feed is live; no decision has arrived on it yet.",
    errorTitle: "Live decision rejected",
    errorDetail: `A decision payload failed schema validation${reason} and was not shown.`,
    offlineDetail: "You're offline — live decisions resume when you reconnect.",
  };
  // A degraded posture keeps the shared default copy; a dropped socket is the
  // more specific cause, so it says so.
  if (connected) return labels;
  return {
    ...labels,
    degradedTitle: "Firehose not live",
    degradedDetail:
      "The live connection is down or reconnecting, so no decision is shown as current.",
  };
}
