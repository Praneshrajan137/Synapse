import { ConfidenceChip, TierBadge } from "@ds/compounds";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";

/**
 * Live tail of the `decision` channel. Last 12 rows; click navigates to
 * Decision Theater detail (`/decisions/:id`) in P3.
 */
export function DecisionFirehoseTail() {
  const decisions = useFirehoseStore((s) => s.decisions.items.slice(-12).reverse());

  return (
    <section aria-label="Decision firehose" className="syn-card overflow-hidden">
      <header className="border-b border-border px-3 py-2 text-2xs uppercase tracking-wide text-ink-muted">
        Live decisions
      </header>
      <ul className="divide-y divide-border">
        {decisions.length === 0 && (
          <li className="px-3 py-6 text-center text-xs text-ink-muted">
            Waiting for the firehose…
          </li>
        )}
        {decisions.map((d) => (
          <li key={d.decision_id} className="flex items-center gap-3 px-3 py-2 text-xs">
            <span className="font-mono text-ink-muted">{fmt.shortId(d.decision_id)}</span>
            <TierBadge tier={d.tier} />
            <ConfidenceChip value={d.confidence} />
            {d.escalated_to_human && <span className="text-confidence-warn">esc.</span>}
            <span className="ml-auto text-ink-subtle">{fmt.relativeTime(d.timestamp)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
