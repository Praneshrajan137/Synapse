import { usePostureHistory } from "@hooks/use-posture-history";
import { cn } from "@lib/cn";

/**
 * System trust strip (ADR-046): the posture TRAJECTORY (not just the current
 * banner) — a sample-per-poll timeline, the brownout level per city, and the
 * breaker board. A failed poll is a drained "unknown" cell, never a healthy
 * green one (FE-INV-035/042).
 */

const BREAKER_TONE: Record<string, string> = {
  closed: "text-signal-success",
  open: "text-signal-danger",
  half_open: "text-signal-warning",
};
const BROWNOUT_TONE = (level: string): string =>
  level === "NONE" || level === "" ? "text-signal-success" : "text-signal-warning";

export function SystemTrustStrip() {
  const { posture, history } = usePostureHistory();
  const current = posture.data;
  const unknown = posture.isError || !current;

  return (
    <section className="syn-card space-y-3 p-4" aria-label="System trust posture">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">System trust</h2>
        <span
          className={cn(
            "text-2xs font-medium uppercase tracking-wide",
            unknown
              ? "text-ink-subtle"
              : current.degraded
                ? "text-signal-danger"
                : "text-signal-success",
          )}
        >
          {unknown ? "posture unknown" : current.degraded ? "degraded" : "nominal"}
        </span>
      </div>

      {/* Posture timeline — one cell per poll. */}
      <div
        className="flex h-6 items-end gap-0.5"
        role="img"
        aria-label={`Posture over the last ${history.length} samples`}
      >
        {history.length === 0 ? (
          <span className="text-2xs text-ink-subtle">collecting posture samples…</span>
        ) : (
          history.map((s) => (
            <span
              key={s.ts}
              title={
                s.known ? (s.degraded ? "degraded" : "nominal") : "posture unknown (poll failed)"
              }
              className={cn(
                "h-full w-1.5 rounded-sm",
                !s.known
                  ? "bg-border"
                  : s.degraded
                    ? "bg-signal-danger/80"
                    : "bg-signal-success/70",
              )}
            />
          ))
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {/* Brownout per city */}
        <div className="space-y-1">
          <div className="text-2xs uppercase tracking-[0.14em] text-ink-subtle">Brownout</div>
          {unknown ? (
            <p className="text-xs text-ink-subtle">unknown</p>
          ) : Object.keys(current.brownout).length === 0 ? (
            <p className="text-xs text-ink-subtle">none reported</p>
          ) : (
            <ul className="space-y-0.5">
              {Object.entries(current.brownout).map(([city, level]) => (
                <li key={city} className="flex justify-between text-xs">
                  <span className="capitalize text-ink-muted">{city}</span>
                  <span className={cn("font-mono", BROWNOUT_TONE(level))}>{level || "NONE"}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Breaker board */}
        <div className="space-y-1">
          <div className="text-2xs uppercase tracking-[0.14em] text-ink-subtle">Breakers</div>
          {unknown ? (
            <p className="text-xs text-ink-subtle">unknown</p>
          ) : Object.keys(current.breakers).length === 0 ? (
            <p className="text-xs text-ink-subtle">none reported</p>
          ) : (
            <ul className="space-y-0.5">
              {Object.entries(current.breakers).map(([dep, state]) => (
                <li key={dep} className="flex justify-between text-xs">
                  <span className="text-ink-muted">{dep}</span>
                  <span
                    className={cn(
                      "font-mono lowercase",
                      BREAKER_TONE[state.toLowerCase()] ?? "text-ink-subtle",
                    )}
                  >
                    {state}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
