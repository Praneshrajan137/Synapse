import type { SloResponse, SloTier } from "@domain/operations";
import { cn } from "@lib/cn";
import { burnSeverityWord, deriveBurnSeverity } from "./logic";

const TIER_ORDER = ["tier_1", "tier_2", "tier_3", "tier_4"] as const;
const TIER_LABEL: Record<string, string> = {
  tier_1: "Tier 1",
  tier_2: "Tier 2",
  tier_3: "Tier 3",
  tier_4: "Tier 4",
};

// The page threshold (fast burn ≥14.4x) is full-scale on the gauge.
const FULL_SCALE = 14.4;

const SEVERITY_TEXT: Record<string, string> = {
  ok: "text-signal-success",
  warning: "text-signal-warning",
  critical: "text-signal-danger",
  unknown: "text-ink-subtle",
};
const SEVERITY_BAR: Record<string, string> = {
  ok: "bg-signal-success",
  warning: "bg-signal-warning",
  critical: "bg-signal-danger",
  unknown: "bg-border",
};

function fmtBurn(v: number | null): string {
  return v === null ? "—" : `${v.toFixed(1)}×`;
}

export function BurnGauge({
  tier,
  data,
  sourceUnknown = false,
}: {
  tier: string;
  data: SloTier;
  sourceUnknown?: boolean;
}) {
  const fast = data.windows.fast.burn_rate;
  const slow = data.windows.slow.burn_rate;
  // Never trust the reported severity blind: a null window or an unreachable
  // source collapses to "unknown", never a healthy bar or a fabricated 0
  // (FE-INV-042, Req 10.9).
  const sev = deriveBurnSeverity({ fast, slow, reported: data.severity, sourceUnknown });
  const word = burnSeverityWord(sev);
  // Drain the track entirely when the burn is unknown so we never paint a
  // partial bar off a number we don't actually have.
  const pct = sev === "unknown" || fast === null ? 0 : Math.min(1, Math.max(0, fast / FULL_SCALE));

  return (
    <div className="syn-card px-4 py-3">
      <div className="flex items-baseline justify-between">
        <span className="text-2xs uppercase tracking-[0.14em] text-ink-subtle">
          {TIER_LABEL[tier] ?? tier}
        </span>
        <span className={cn("text-2xs font-medium uppercase tracking-wide", SEVERITY_TEXT[sev])}>
          {word}
        </span>
      </div>
      <div className="mt-1 text-2xs text-ink-subtle">
        ≤ {data.latency_target_s}s · {(data.objective * 100).toFixed(1)}% objective
      </div>
      {/* Track + fill. A null (unknown) burn renders a drained track, never a
          full healthy bar (FE-INV-042). */}
      <div
        className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface"
        role="img"
        aria-label={`${TIER_LABEL[tier] ?? tier} ${word}; fast burn ${fmtBurn(fast)}, slow burn ${fmtBurn(slow)}`}
      >
        <div
          className={cn("h-full rounded-full transition-[width] duration-fast", SEVERITY_BAR[sev])}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-2xs tabular-nums text-ink-muted">
        <span>1h {fmtBurn(fast)}</span>
        <span>6h {fmtBurn(slow)}</span>
      </div>
    </div>
  );
}

interface SloBurnBoardProps {
  readonly data: SloResponse | undefined;
  readonly isError: boolean;
}

export function SloBurnBoard({ data, isError }: SloBurnBoardProps) {
  // No reachable Prometheus → honest "burn unknown" tiles, never silent green.
  const unknownTier = (): SloTier => ({
    objective: 0,
    latency_target_s: 0,
    windows: {
      fast: { window: "1h", error_rate: null, burn_rate: null },
      slow: { window: "6h", error_rate: null, burn_rate: null },
    },
    budget_remaining_30d: null,
    severity: "unknown",
  });

  const tiers = data?.tiers ?? {};
  const sourceUnknown = isError || data?.source === "unknown";

  return (
    <section className="space-y-2" aria-label="SLO burn by tier">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">SLO burn</h2>
        <span className="text-2xs text-ink-subtle">
          {sourceUnknown ? "source: unknown" : "multi-window (1h / 6h)"}
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {TIER_ORDER.map((tier) => (
          <BurnGauge
            key={tier}
            tier={tier}
            data={tiers[tier] ?? unknownTier()}
            sourceUnknown={sourceUnknown}
          />
        ))}
      </div>
    </section>
  );
}
