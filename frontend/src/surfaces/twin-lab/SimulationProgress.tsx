import { TWIN_SIMULATE_TIMEOUT_MS } from "@transport/synapse-api";
import { useEffect, useState } from "react";

interface SimulationProgressProps {
  readonly pending: boolean;
}

const SLA_SECONDS = Math.round(TWIN_SIMULATE_TIMEOUT_MS / 1000);

/**
 * Progress affordance for a long-running Monte Carlo run (Req 7.6).
 *
 * While a /simulate request is in flight this renders an indeterminate progress
 * bar plus a live elapsed-time readout in an assertive-free polite live region,
 * so an operator sees the run is working (not hung) and knows the ≤120s Tier-4
 * SLA ceiling after which the FE rejects the run with a typed timeout. Motion is
 * incidental; the elapsed seconds carry the same information as text.
 */
export function SimulationProgress({ pending }: SimulationProgressProps) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!pending) {
      setElapsedMs(0);
      return;
    }
    const start = Date.now();
    setElapsedMs(0);
    const id = setInterval(() => setElapsedMs(Date.now() - start), 250);
    return () => clearInterval(id);
  }, [pending]);

  if (!pending) return null;

  const elapsedSeconds = Math.floor(elapsedMs / 1000);
  const pct = Math.min(100, Math.round((elapsedMs / TWIN_SIMULATE_TIMEOUT_MS) * 100));

  return (
    <output
      className="syn-card block space-y-2 p-3"
      aria-live="polite"
      data-testid="simulation-progress"
    >
      <div className="flex items-center justify-between text-2xs text-ink-muted">
        <span>Running Monte Carlo…</span>
        <span className="font-mono tabular-nums text-ink">
          {elapsedSeconds}s / {SLA_SECONDS}s SLA
        </span>
      </div>
      {/* biome-ignore lint/a11y/useFocusableInteractive: a progressbar is a live status indicator, not a focus target */}
      <div
        className="h-1.5 overflow-hidden rounded-full bg-surface-sunken"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={SLA_SECONDS}
        aria-valuenow={elapsedSeconds}
        aria-label="Simulation elapsed time toward the SLA ceiling"
      >
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-fast"
          style={{ width: `${pct}%` }}
        />
      </div>
    </output>
  );
}
