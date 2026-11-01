import type { TwinState } from "@domain/twin-state";
import {
  DataPathNotice,
  DivergenceTrace,
  PageHeader,
  SpatialErrorBoundary,
  UniversalStateView,
} from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useFirehose } from "@hooks/use-firehose";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { useUniversalState } from "@hooks/use-universal-state";
import { useFirehoseStore } from "@state/firehose.store";
import { useMutation } from "@tanstack/react-query";
import { TimeoutError } from "@transport/errors";
import { Suspense, lazy, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { AutonomyPanel } from "../autonomy/AutonomyPanel";
import { surfaceDataPath } from "../data-paths";
import { DivergenceMeter } from "./DivergenceMeter";
import { NodeInspector } from "./NodeInspector";
import { ScenarioBuilder, type ScenarioRequest } from "./ScenarioBuilder";
import { SimulationProgress } from "./SimulationProgress";
import { SupplyNetworkTable } from "./SupplyNetworkTable";
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
  const { t } = useTranslation("common");
  const api = useSynapseApi();
  const topology = useTopology();
  const [result, setResult] = useState<TwinState | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

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
      // A hung run is rejected by the transport's typed timeout (Req 7.6); make
      // that explicit rather than showing a generic "simulation failed".
      if (err instanceof TimeoutError) {
        toast.error("Simulation timed out — the run exceeded the 120s SLA and was rejected.");
        return;
      }
      toast.error(`Simulation failed: ${err.message}`);
    },
  });

  // R3.5. This was `result?.kl_divergence ?? 0`: before any scenario had run the
  // meter drew 0.000 in the OK band, which on a KL gauge is the strongest
  // fidelity claim the surface can make - a fabricated one. `null` now means
  // "not measured" all the way to the render.
  const klValue = result?.kl_divergence ?? null;
  const klPath = surfaceDataPath("twin-lab.divergence", {
    degraded: sim.isError ? true : klValue === null ? null : false,
    // The twin's world is whatever the active WorldSource declares; the
    // /simulate response carries no provenance block, so the console cannot
    // claim either way and says so rather than implying live commerce.
    synthetic: null,
  });

  // The supply-network topology is the spatial surface's data spine: a failed
  // or offline load must render a distinct, non-blank state with retry rather
  // than an empty canvas (Req 7.5, 10.1, 10.7, 10.8).
  const topologyState = useUniversalState({
    isLoading: topology.isLoading,
    isError: topology.isError,
    itemCount: topology.data?.nodes?.length ?? 0,
  });

  return (
    <section className="space-y-5">
      <PageHeader
        title="Twin Lab"
        subtitle="Run what-if scenarios against the digital twin (I-12). KL divergence vs the live distribution is tracked per run and over time."
        status={
          result?.sync_status ? (
            <Badge tone={result.sync_status === "synced" ? "success" : "warning"}>
              {result.sync_status}
            </Badge>
          ) : undefined
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_minmax(0,2fr)]">
        <div className="space-y-1.5">
          <DivergenceMeter value={klValue} />
          <DataPathNotice state={klPath} />
        </div>
        {divergenceSeries.length > 0 && (
          <DivergenceTrace series={divergenceSeries} className="syn-card p-3" />
        )}
      </div>

      {/* ADR-053: the autonomous loop lives with the twin — the world it
          perceives and acts on is the twin's standing WorldRuntime. */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-ink">{t("autonomy.title")}</h2>
        <AutonomyPanel />
      </section>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div>
          {/* Spatial canvas: the boundary catches a failed chunk/render (error +
              retry, never a blank canvas — Req 7.5); Suspense covers loading;
              UniversalStateView covers the topology data states (13.2). */}
          <SpatialErrorBoundary label="supply network" height={420}>
            <Suspense
              fallback={
                <div
                  className="syn-card syn-skeleton flex h-[420px] items-center justify-center text-sm text-ink-muted"
                  aria-busy="true"
                >
                  Loading supply network…
                </div>
              }
            >
              <UniversalStateView
                state={topologyState}
                onRetry={() => void topology.refetch()}
                className="h-[420px]"
                labels={{
                  loadingTitle: "Loading supply network…",
                  emptyTitle: "No topology for this city yet",
                  emptyDetail: "The supply network graph will render once nodes are available.",
                  errorTitle: "Supply network unavailable",
                  errorDetail:
                    "Could not load the topology. This is a load failure, not an empty network — retry.",
                  offlineDetail: "You're offline — reconnect to load the supply network.",
                }}
              >
                <SupplyNetworkGraph
                  nodes={topology.data?.nodes ?? []}
                  edges={topology.data?.edges ?? []}
                  selectedId={selectedNodeId}
                  onSelectNode={setSelectedNodeId}
                />
              </UniversalStateView>
            </Suspense>
          </SpatialErrorBoundary>

          {/* Non-spatial equivalent — keyboard/SR-reachable node table (Req 7.4).
              Outside the boundary so it survives a viz failure and shares the
              NodeInspector via the same selection state. */}
          <SupplyNetworkTable
            nodes={topology.data?.nodes ?? []}
            edges={topology.data?.edges ?? []}
            selectedId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
          />
        </div>
        <div className="space-y-4">
          <ScenarioBuilder pending={sim.isPending} onRun={(req) => sim.mutate(req)} />
          <SimulationProgress pending={sim.isPending} />
          <NodeInspector
            selectedId={selectedNodeId}
            nodes={topology.data?.nodes ?? []}
            edges={topology.data?.edges ?? []}
            onClose={() => setSelectedNodeId(null)}
          />
        </div>
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
