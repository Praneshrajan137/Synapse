import { Badge } from "@ds/primitives";
import { useFirehoseStore } from "@state/firehose.store";

/**
 * Surfaces the most-recent disruption alert from the firehose. Banner is
 * dismissed automatically when the underlying ring buffer cycles past it.
 */
export function DisruptionBanner() {
  const latest = useFirehoseStore((s) => s.disruptions.items[s.disruptions.items.length - 1]);
  if (!latest) return null;
  return (
    <div role="alert" className="syn-card-raised border-l-4 border-confidence-risk px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="danger">Disruption</Badge>
        <span className="text-sm font-semibold text-ink">
          {latest.disruption_type ?? "supply-chain anomaly"}
        </span>
        <Badge tone="warning">Level {latest.alert_level}/10</Badge>
        <span className="text-xs text-ink-muted">
          {latest.affected_nodes.length} affected node
          {latest.affected_nodes.length === 1 ? "" : "s"}
        </span>
      </div>
      <p className="mt-1 line-clamp-2 text-xs text-ink-muted">{latest.reasoning_chain}</p>
    </div>
  );
}
