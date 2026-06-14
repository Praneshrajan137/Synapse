import { useEscalationStore } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

// Temporal catch-up (Sprint 18). An operator who looks away (another tab, a
// meeting) returns with no idea what changed — the firehose is an ephemeral
// ring buffer. On refocus after a real absence we summarise what arrived while
// they were gone, using the monotonic per-channel seq counters (robust to ring
// eviction) and escalation receipt timestamps. Dismissible; never nags for a
// blink-away.

const MIN_AWAY_MS = 30_000;

interface Digest {
  readonly awayMs: number;
  readonly escalations: number;
  readonly disruptions: number;
}

export function CatchUpBanner() {
  const [digest, setDigest] = useState<Digest | null>(null);
  const hiddenAt = useRef<number | null>(null);
  const seqSnapshot = useRef<Record<string, number>>({});

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) {
        hiddenAt.current = Date.now();
        seqSnapshot.current = { ...useFirehoseStore.getState().lastSeq };
        return;
      }
      const since = hiddenAt.current;
      hiddenAt.current = null;
      if (since === null) return;
      const awayMs = Date.now() - since;
      if (awayMs < MIN_AWAY_MS) return;

      const lastSeq = useFirehoseStore.getState().lastSeq;
      const snap = seqSnapshot.current;
      const delta = (ch: string) => Math.max(0, (lastSeq[ch] ?? 0) - (snap[ch] ?? 0));
      const escalations = useEscalationStore
        .getState()
        .entries.filter((e) => e.received_at >= since).length;
      const disruptions = delta("disruption");

      if (escalations === 0 && disruptions === 0) return;
      setDigest({ awayMs, escalations, disruptions });
    };

    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  if (!digest) return null;

  const mins = Math.max(1, Math.round(digest.awayMs / 60_000));
  const parts = [
    digest.escalations > 0
      ? `${digest.escalations} new escalation${digest.escalations === 1 ? "" : "s"}`
      : "",
    digest.disruptions > 0
      ? `${digest.disruptions} disruption${digest.disruptions === 1 ? "" : "s"}`
      : "",
  ].filter(Boolean);

  return (
    <output className="flex flex-wrap items-center gap-x-3 gap-y-1 bg-surface-raised px-6 py-2 text-xs">
      <span className="font-semibold text-ink">While you were away ({mins}m)</span>
      <span className="text-ink-muted">{parts.join(" · ")}</span>
      {digest.escalations > 0 && (
        <Link
          to="/cockpit"
          className="font-medium text-accent hover:underline focus-visible:shadow-focus focus-visible:outline-none"
          onClick={() => setDigest(null)}
        >
          Review →
        </Link>
      )}
      <button
        type="button"
        onClick={() => setDigest(null)}
        className="ml-auto rounded px-1.5 text-ink-subtle hover:text-ink focus-visible:shadow-focus focus-visible:outline-none"
        aria-label="Dismiss catch-up"
      >
        ✕
      </button>
    </output>
  );
}
