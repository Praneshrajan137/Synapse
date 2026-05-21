import { cn } from "@lib/cn";
import type { WsState } from "@transport/ws-multiplex";

interface ConnectionPillProps {
  readonly state: WsState;
  readonly label?: string;
}

const PRESET: Record<WsState, { tone: string; text: string; pulse: boolean }> = {
  idle: { tone: "bg-ink-subtle/15 text-ink-muted", text: "Idle", pulse: false },
  connecting: {
    tone: "bg-signal-warning/15 text-signal-warning",
    text: "Connecting",
    pulse: true,
  },
  open: { tone: "bg-signal-success/15 text-signal-success", text: "Live", pulse: false },
  closing: {
    tone: "bg-signal-warning/15 text-signal-warning",
    text: "Closing",
    pulse: true,
  },
  closed: { tone: "bg-signal-danger/15 text-signal-danger", text: "Offline", pulse: true },
};

export function ConnectionPill({ state, label }: ConnectionPillProps) {
  const cfg = PRESET[state];
  return (
    <span
      role="status"
      aria-live="polite"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-2xs font-medium",
        cfg.tone,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          cfg.pulse && "animate-pulse-confidence",
        )}
        style={{ background: "currentColor" }}
      />
      {label ?? cfg.text}
    </span>
  );
}
