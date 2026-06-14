import { useAttention } from "@hooks/use-attention";
import { cn } from "@lib/cn";
import type { AttentionItem, AttentionSeverity } from "@state/attention.store";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

// The Attention Spine's single, always-visible head (Sprint 18). Collapsed it
// is one chip in the Shell header: "All clear" when nothing needs the operator,
// or the top-ranked alarm with a count. Expanded it lists every signal, ranked,
// with deep-links and acknowledge for informational items. This makes the
// human-in-the-loop signal the loudest thing on EVERY surface — fixing the old
// inversion where a pending escalation was a number on one page.

const SEVERITY_TONE: Record<AttentionSeverity, string> = {
  critical: "bg-signal-danger/15 text-signal-danger",
  high: "bg-signal-danger/15 text-signal-danger",
  medium: "bg-signal-warning/15 text-signal-warning",
  low: "bg-signal-info/15 text-signal-info",
};

const KIND_GLYPH: Record<AttentionItem["kind"], string> = {
  escalation: "▲",
  connection: "○",
  degradation: "◆",
  disruption: "✦",
  divergence: "≈",
};

export function AttentionBeacon() {
  const { items, top, actionableCount, acknowledge } = useAttention();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const go = (item: AttentionItem) => {
    setOpen(false);
    navigate(item.route);
  };

  // Calm "all clear" — the Reassure job. Always present so its absence is
  // itself a signal (the chip never silently disappears).
  if (!top) {
    return (
      <output
        aria-live="polite"
        className="inline-flex items-center gap-1.5 rounded-sm bg-signal-success/12 px-2 py-1 text-2xs font-medium text-signal-success"
      >
        <span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: "currentColor" }}
        />
        All clear
      </output>
    );
  }

  const urgent = top.severity === "critical" || top.severity === "high";
  const summary =
    actionableCount > 0
      ? `${actionableCount} need${actionableCount === 1 ? "s" : ""} you`
      : top.title;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-live="assertive"
        aria-label={`${items.length} item${items.length === 1 ? "" : "s"} need attention. ${top.title}: ${top.detail}`}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-2xs font-semibold",
          "focus-visible:shadow-focus focus-visible:outline-none",
          SEVERITY_TONE[top.severity],
        )}
      >
        <span
          aria-hidden
          className={cn("h-1.5 w-1.5 rounded-full", urgent && "animate-pulse-confidence")}
          style={{ background: "currentColor" }}
        />
        <span>{summary}</span>
        {items.length > 1 && (
          <span className="rounded-full bg-ink/10 px-1 tabular-nums">{items.length}</span>
        )}
        <span aria-hidden className="opacity-70">
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open && (
        <>
          {/* click-away backdrop */}
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div
            role="menu"
            aria-label="Attention items"
            className="syn-card-raised absolute right-0 z-50 mt-1 w-80 space-y-1 p-2"
          >
            {items.map((item) => (
              <div
                key={item.key}
                className="flex items-start gap-2 rounded-md p-2 hover:bg-overlay/60"
              >
                <span
                  aria-hidden
                  className={cn(
                    "mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-2xs",
                    SEVERITY_TONE[item.severity],
                  )}
                >
                  {KIND_GLYPH[item.kind]}
                </span>
                <button
                  type="button"
                  onClick={() => go(item)}
                  className="min-w-0 flex-1 text-left focus-visible:shadow-focus focus-visible:outline-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-xs font-semibold text-ink">{item.title}</span>
                    {item.count > 1 && (
                      <span className="shrink-0 font-mono text-2xs tabular-nums text-ink-subtle">
                        ×{item.count}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-2xs text-ink-muted">{item.detail}</p>
                </button>
                {!item.actionable && (
                  <button
                    type="button"
                    onClick={() => acknowledge(item.key)}
                    className="shrink-0 rounded px-1.5 py-0.5 text-2xs text-ink-subtle hover:bg-overlay hover:text-ink focus-visible:shadow-focus focus-visible:outline-none"
                    aria-label={`Acknowledge ${item.title}`}
                  >
                    Ack
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
