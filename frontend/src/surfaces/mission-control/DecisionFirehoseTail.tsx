import { ConfidenceChip, InitiatorBadge, TierBadge } from "@ds/compounds";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

/**
 * Live tail of the `decision` channel. Last 12 rows; clicking a row opens the
 * Council Theater reconstruction (`/council/:id`) — watch how that decision was
 * deliberated. The analyst detail stays reachable from there and from
 * Decision Theater.
 *
 * ADR-044 honesty: a degraded decision (any input proposal on a fallback
 * path) carries the drained warning marker. ADR-053: the InitiatorBadge marks
 * an autonomously self-initiated decision (the SensorLoop acting on its own)
 * and a demo pulse — operator-injected decisions stay unbadged (the common
 * case), so the badge draws the eye to what is NOT a human's doing.
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
          <li key={d.decision_id} className="animate-arrive">
            <Link
              to={`/council/${d.decision_id}`}
              aria-label={`Watch deliberation for decision ${fmt.shortId(d.decision_id)}`}
              className="flex items-center gap-3 px-3 py-2 text-xs transition-colors duration-fast hover:bg-surface-raised/60 focus-visible:outline-none focus-visible:shadow-focus"
            >
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
              {d.initiator !== "operator" && <InitiatorBadge initiator={d.initiator} />}
              {d.escalated && <span className="text-confidence-warn">esc.</span>}
              <span className="ml-auto text-ink-subtle">{fmt.relativeTime(d.timestamp)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
