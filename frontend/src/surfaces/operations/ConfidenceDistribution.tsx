import type { City } from "@domain/primitives";
import { DataPathNotice, OutcomeBand } from "@ds/compounds";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { cn } from "@lib/cn";
import { metricQueryKey } from "@lib/query-keys";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { surfaceDataPath } from "../data-paths";
import { NO_VALUE_MARKER, confidenceSamples } from "./logic";

/**
 * Confidence distribution (ADR-047) — wires the previously-unused OutcomeBand
 * quantile dotplot to a real signal: the confidence of recent decisions, with
 * the I-5 HITL gate (0.70) as the threshold. "N of 20 recent decisions sit
 * below the escalation gate" is something an operator can act on.
 *
 * Real vs. synthetic is segmented (FE-INV-044): the synthetic toggle never
 * silently mixes demo pulses into the trust read.
 *
 * R3.5: `q.data?.decisions ?? []` used to draw an EMPTY dotplot captioned
 * "0 decisions" when the read failed - a load failure rendered as a measured
 * distribution of nothing. The panel now declares its data-path state and the
 * caption distinguishes "the read answered with no rows" from "the read did not
 * answer". R4.3: when the operator opts synthetic decisions back in, the
 * distribution becomes a synthetic-sourced aggregate and is labelled as one.
 */
const HITL_GATE = 0.7;

export function ConfidenceDistribution({ city }: { city: City }) {
  const api = useSynapseApi();
  const [includeSynthetic, setIncludeSynthetic] = useState(false);

  const q = useQuery({
    queryKey: metricQueryKey("recent-for-confidence", city, { includeSynthetic }),
    queryFn: () => api.listRecentDecisions({ limit: 200, city }),
    refetchInterval: 30_000,
    retry: false,
  });

  const known = q.data !== undefined;
  const rows = q.data?.decisions ?? [];
  const samples = confidenceSamples(rows, includeSynthetic);
  const syntheticCount = rows.filter((r) => r.is_synthetic).length;

  const dataPath = surfaceDataPath("operations.confidence-distribution", {
    degraded: q.isError ? true : known ? false : null,
    // Synthetic rows only enter the plotted samples when the toggle admits them.
    synthetic: known ? includeSynthetic && syntheticCount > 0 : null,
  });

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

      <DataPathNotice state={dataPath} />

      {known ? (
        <OutcomeBand
          samples={samples}
          threshold={HITL_GATE}
          thresholdIsCeiling={false}
          label="Recent decision confidence"
          width={520}
          height={130}
        />
      ) : (
        // An unanswered read has no distribution. Drawing the band on an empty
        // sample set would present a load failure as a measured distribution.
        <p className="py-8 text-center text-xs text-state-degraded">
          <span aria-hidden>▲ </span>
          No distribution — the recent-decisions read did not answer.
        </p>
      )}

      <p className="text-2xs text-ink-subtle">
        {known ? samples.length : NO_VALUE_MARKER} decisions · gate {HITL_GATE} ·{" "}
        {known ? syntheticCount : NO_VALUE_MARKER} synthetic in window
        {known && !includeSynthetic && syntheticCount > 0 && " (excluded)"}
      </p>
    </section>
  );
}
