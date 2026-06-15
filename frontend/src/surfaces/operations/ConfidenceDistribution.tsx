import type { City } from "@domain/primitives";
import { OutcomeBand } from "@ds/compounds";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { cn } from "@lib/cn";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { confidenceSamples } from "./logic";

/**
 * Confidence distribution (ADR-046) — wires the previously-unused OutcomeBand
 * quantile dotplot to a real signal: the confidence of recent decisions, with
 * the I-5 HITL gate (0.70) as the threshold. "N of 20 recent decisions sit
 * below the escalation gate" is something an operator can act on.
 *
 * Real vs. synthetic is segmented (FE-INV-044): the synthetic toggle never
 * silently mixes demo pulses into the trust read.
 */
const HITL_GATE = 0.7;

export function ConfidenceDistribution({ city }: { city: City }) {
  const api = useSynapseApi();
  const [includeSynthetic, setIncludeSynthetic] = useState(false);

  const q = useQuery({
    queryKey: ["recent-for-confidence", city],
    queryFn: () => api.listRecentDecisions({ limit: 200, city }),
    refetchInterval: 30_000,
    retry: false,
  });

  const rows = q.data?.decisions ?? [];
  const samples = confidenceSamples(rows, includeSynthetic);
  const syntheticCount = rows.filter((r) => r.is_synthetic).length;

  return (
    <section className="syn-card space-y-3 p-4" aria-label="Confidence distribution">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Confidence distribution</h2>
        <button
          type="button"
          onClick={() => setIncludeSynthetic((s) => !s)}
          aria-pressed={includeSynthetic}
          className={cn(
            "rounded-md border px-2 py-1 text-2xs font-medium transition-colors duration-fast",
            "focus-visible:outline-none focus-visible:shadow-focus",
            includeSynthetic
              ? "border-state-synthetic/50 text-state-synthetic"
              : "border-border text-ink-muted hover:text-ink",
          )}
        >
          {includeSynthetic ? "Including synthetic" : "Real only"}
        </button>
      </div>

      <OutcomeBand
        samples={samples}
        threshold={HITL_GATE}
        thresholdIsCeiling={false}
        label="Recent decision confidence"
        width={520}
        height={130}
      />

      <p className="text-2xs text-ink-subtle">
        {samples.length} decisions · gate {HITL_GATE} · {syntheticCount} synthetic in window
        {!includeSynthetic && syntheticCount > 0 && " (excluded)"}
      </p>
    </section>
  );
}
