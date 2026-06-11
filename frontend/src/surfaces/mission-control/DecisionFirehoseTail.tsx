import { ConfidenceChip, SyntheticBadge, TierBadge } from "@ds/compounds";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";
import { useTranslation } from "react-i18next";

/**
 * Live tail of the `decision` channel. Last 12 rows; click navigates to
 * Decision Theater detail (`/decisions/:id`) in P3.
 *
 * ADR-044 honesty: a degraded decision (any input proposal on a fallback
 * path) carries the drained warning marker; a traffic-generator decision
 * carries the SyntheticBadge — demo pulses never masquerade as commerce.
 */
export function DecisionFirehoseTail() {
  const { t } = useTranslation("common");
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
            {d.degraded && (
              <span
                className="text-state-degraded"
                role="img"
                aria-label={t("provenance.degraded")}
                title={t("provenance.degraded")}
              >
                ▲
              </span>
            )}
            {d.is_synthetic && <SyntheticBadge />}
            {d.escalated && <span className="text-confidence-warn">esc.</span>}
            <span className="ml-auto text-ink-subtle">{fmt.relativeTime(d.timestamp)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
