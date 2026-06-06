import type { TwinState } from "@domain/twin-state";
import { DivergenceTrace } from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useFirehose } from "@hooks/use-firehose";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { useFirehoseStore } from "@state/firehose.store";
import { useMutation } from "@tanstack/react-query";
import { Suspense, lazy, useMemo, useState } from "react";
import { toast } from "sonner";
import { DivergenceMeter } from "./DivergenceMeter";
import { ScenarioBuilder, type ScenarioRequest } from "./ScenarioBuilder";
import { useTopology } from "./useTopology";

// Phase 6b: lazy-load the WebGL (Sigma) supply graph so it stays out of the
// entry bundle (FE-INV-014 / FE-INV-025).
const SupplyNetworkGraph = lazy(() =>
  import("./SupplyNetworkGraph").then((m) => ({ default: m.SupplyNetworkGraph })),
);

/**
 * Twin Lab — P3 elevation (SENSORIUM "The Projection"). Live KL divergence +
 * its drift trace, the WebGL supply network, and what-if scenarios against the
 * digital twin's /simulate endpoint.
 */
export function TwinLab() {
  const api = useSynapseApi();
  const topology = useTopology();
  const [result, setResult] = useState<TwinState | null>(null);

  // Subscribe to the live twin channel so the divergence trace shows drift over
  // time, not just the latest scenario's snapshot (I-12).
  useFirehose({ topics: ["twin"] });
  const twinHistory = useFirehoseStore((s) => s.twin.items);
  const divergenceSeries = useMemo(() => {
    const s = twinHistory.map((t) => t.kl_divergence);
    if (result) s.push(result.kl_divergence);
    return s;
  }, [twinHistory, result]);

  const sim = useMutation({
    mutationFn: (req: ScenarioRequest) => api.simulate(req),
    onSuccess: (data) => {
      setResult(data);
      toast.success(`Scenario complete — KL=${data.kl_divergence.toFixed(3)}`);
    },
    onError: (err: Error) => {
      toast.error(`Simulation failed: ${err.message}`);
    },
  });

  const klValue = result?.kl_divergence ?? 0;

  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-0.5">
          <h1 className="text-2xl font-semibold text-ink">Twin Lab</h1>
          <p className="text-sm text-ink-muted">
            Run what-if scenarios against the digital twin (I-12). KL divergence vs the live
            distribution is tracked per run and over time.
          </p>
        </div>
        {result?.sync_status && (
          <Badge tone={result.sync_status === "synced" ? "success" : "warning"}>
            {result.sync_status}
          </Badge>
        )}
      </header>

      <div className="grid gap-4 lg:grid-cols-[1fr_minmax(0,2fr)]">
        <DivergenceMeter value={klValue} />
        {divergenceSeries.length > 0 && (
          <DivergenceTrace series={divergenceSeries} className="syn-card p-3" />
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Suspense
          fallback={
            <div className="syn-card flex h-[420px] items-center justify-center text-sm text-ink-muted">
              Loading supply network…
            </div>
          }
        >
          <SupplyNetworkGraph
            nodes={topology.data?.nodes ?? []}
            edges={topology.data?.edges ?? []}
          />
        </Suspense>
        <ScenarioBuilder pending={sim.isPending} onRun={(req) => sim.mutate(req)} />
      </div>

      {result && (
        <section className="syn-card-raised space-y-2 p-4">
          <h2 className="text-sm font-semibold text-ink">Latest scenario</h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs md:grid-cols-4">
            <div>
              <dt className="text-ink-muted">Snapshot</dt>
              <dd className="font-mono text-ink">{result.snapshot_id.slice(0, 12)}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">KL</dt>
              <dd className="font-mono text-ink">{result.kl_divergence.toFixed(4)}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Sync</dt>
              <dd className="font-mono text-ink">{result.sync_status}</dd>
            </div>
            {result.simulation_metrics?.avg_delivery_time_min !== undefined && (
              <div>
                <dt className="text-ink-muted">Avg delivery</dt>
                <dd className="font-mono text-ink">
                  {result.simulation_metrics.avg_delivery_time_min.toFixed(1)}m
                </dd>
              </div>
            )}
            {result.simulation_metrics?.fill_rate !== undefined && (
              <div>
                <dt className="text-ink-muted">Fill rate</dt>
                <dd className="font-mono text-ink">
                  {(result.simulation_metrics.fill_rate * 100).toFixed(1)}%
                </dd>
              </div>
            )}
            {result.node_counts?.dark_stores !== undefined && (
              <div>
                <dt className="text-ink-muted">Stores</dt>
                <dd className="font-mono text-ink">{result.node_counts.dark_stores}</dd>
              </div>
            )}
          </dl>
        </section>
      )}
    </section>
  );
}
