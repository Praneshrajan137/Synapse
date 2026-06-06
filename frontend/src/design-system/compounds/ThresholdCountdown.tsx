import { cn } from "@lib/cn";
import { useEffect, useState } from "react";

/**
 * ThresholdCountdown — the spine of an escalation (SENSORIUM "The Threshold").
 *
 * A confidence-gated escalation runs against a bounded HITL window
 * (orchestrator/hitl/escalation.py — 300 s by default) after which the
 * orchestrator's timeout policy engages. Making that clock visible is the
 * antidote to BOTH failure modes of trust calibration: it tells the operator
 * the machine is not waiting forever (so don't agonise), and that there IS a
 * defined fallback (so don't panic). The operator always knows the cost of
 * NOT acting.
 *
 * Honest by design (P7): the frontend cannot know which timeout action the
 * server is configured for, so the fallback line names the policy as a default,
 * not a certainty.
 *
 * Accessibility: `role="timer"` with a label that carries the remaining time
 * AND the fallback in words (colour is never the sole channel — INV-CLR-011).
 * The bar's smooth drain is suppressed under prefers-reduced-motion via the
 * motion tokens (the per-second numeric tick still updates).
 */

export type TimeoutFallback = "defer" | "execute_tier1" | "execute_last_known_good";

const FALLBACK_PHRASE: Record<TimeoutFallback, string> = {
  defer: "defers — no action is taken",
  execute_tier1: "executes the Tier-1 safe action",
  execute_last_known_good: "executes the last known-good action",
};

export type CountdownUrgency = "calm" | "warn" | "danger";

/** Urgency band from the fraction of the window remaining (0..1). */
export function countdownUrgency(fraction: number): CountdownUrgency {
  if (fraction < 0.2) return "danger";
  if (fraction < 0.5) return "warn";
  return "calm";
}

/** Format remaining milliseconds as m:ss (clamped at 0:00). */
export function formatClock(ms: number): string {
  const totalSec = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const BAR_TONE: Record<CountdownUrgency, string> = {
  calm: "bg-signal-info",
  warn: "bg-signal-warning",
  danger: "bg-signal-danger",
};
const TEXT_TONE: Record<CountdownUrgency, string> = {
  calm: "text-ink",
  warn: "text-signal-warning",
  danger: "text-signal-danger",
};

export interface ThresholdCountdownProps {
  /** When the escalation's HITL window started (epoch ms). */
  readonly startedAtMs: number;
  /** Window length in seconds. Defaults to the orchestrator's 300 s. */
  readonly windowSeconds?: number | undefined;
  /** Configured timeout policy (named as a default — see component doc). */
  readonly fallback?: TimeoutFallback | undefined;
  readonly onExpire?: (() => void) | undefined;
  /** Injectable clock for deterministic tests. */
  readonly now?: number | undefined;
  readonly className?: string | undefined;
}

export function ThresholdCountdown({
  startedAtMs,
  windowSeconds = 300,
  fallback = "defer",
  onExpire,
  now,
  className,
}: ThresholdCountdownProps) {
  const controlled = now !== undefined;
  const [tick, setTick] = useState(() => now ?? Date.now());

  useEffect(() => {
    if (controlled) return;
    const id = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, [controlled]);

  const current = controlled ? now : tick;
  const windowMs = windowSeconds * 1000;
  const elapsed = Math.max(0, current - startedAtMs);
  const remaining = Math.max(0, windowMs - elapsed);
  const fraction = windowMs <= 0 ? 0 : remaining / windowMs;
  const expired = remaining <= 0;
  const urgency = expired ? "danger" : countdownUrgency(fraction);

  // Fire onExpire exactly once when the window elapses.
  const [fired, setFired] = useState(false);
  useEffect(() => {
    if (expired && !fired) {
      setFired(true);
      onExpire?.();
    }
  }, [expired, fired, onExpire]);

  const fallbackPhrase = FALLBACK_PHRASE[fallback];
  const label = expired
    ? `Decision window elapsed — orchestrator timeout policy engaged (default: ${fallbackPhrase}).`
    : `${formatClock(remaining)} left to decide. At zero, the orchestrator timeout policy engages (default: ${fallbackPhrase}).`;

  return (
    <div className={cn("space-y-1.5", className)} role="timer" aria-label={label} aria-live="off">
      <div className="flex items-baseline justify-between gap-2">
        <span className={cn("font-mono text-2xl font-semibold tabular-nums", TEXT_TONE[urgency])}>
          {expired ? "0:00" : formatClock(remaining)}
        </span>
        <span className="text-2xs uppercase tracking-wider text-ink-subtle">
          {expired ? "window elapsed" : "to decide"}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface" aria-hidden="true">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-medium ease-standard",
            BAR_TONE[urgency],
          )}
          style={{ width: `${Math.round(fraction * 100)}%` }}
        />
      </div>
      <p className="text-2xs text-ink-muted">
        {expired ? (
          <>
            Timeout policy engaged — default <span className="text-ink">{fallbackPhrase}</span>.
          </>
        ) : (
          <>
            If no one acts, the orchestrator timeout policy engages (default{" "}
            <span className="text-ink">{fallbackPhrase}</span>).
          </>
        )}
      </p>
    </div>
  );
}
