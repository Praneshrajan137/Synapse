import { AGENT_NAMES, type AgentMetrics, type AgentName } from "@domain/agent-health";
import { ConfidenceChip, PageHeader, UniversalStateView } from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { useUniversalState } from "@hooks/use-universal-state";
import { fmt } from "@lib/formatters";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

const TONE_FOR_STATUS = (status: string): "success" | "warning" | "danger" | "neutral" => {
  if (status === "healthy") return "success";
  if (status.startsWith("http_")) return "warning";
  if (status.startsWith("unreachable")) return "danger";
  return "neutral";
};

export function AgentCouncil() {
  const api = useSynapseApi();
  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.listAgents(),
    refetchInterval: 5_000,
  });

  // The agent set is frozen (8 agents), so "populated" is the norm; the
  // universal state still distinguishes a failed health fetch (error/offline)
  // and a degraded posture from a healthy board (Req 10.1, 10.7, 10.8).
  const agentCount = agents.data?.agents ? Object.keys(agents.data.agents).length : 0;
  const state = useUniversalState({
    isLoading: agents.isLoading,
    isError: agents.isError,
    itemCount: agentCount,
  });

  return (
    <section className="space-y-4">
      <PageHeader
        title="Agent Council"
        subtitle="8 specialised agents — independent rewards (I-2). Per-agent latency percentiles and calibration coverage are sourced from Prometheus via the gateway."
      />
      <UniversalStateView
        state={state}
        onRetry={() => void agents.refetch()}
        labels={{
          emptyTitle: "No agent health yet",
          emptyDetail: "Waiting for the first agent health report from the gateway.",
          errorDetail:
            "Could not reach agent health. This is a load failure, not an empty council — retry.",
        }}
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {AGENT_NAMES.map((name) => {
          const value = agents.data?.agents?.[name] as AgentMetrics | string | undefined;
          const metrics: AgentMetrics =
            typeof value === "string" ? { status: value } : (value ?? { status: "unknown" });
          return (
            <Link
              key={name}
              to={`/agents/${name}`}
              className="syn-card-raised flex flex-col gap-2 p-4 text-left transition-colors duration-fast ease-standard hover:bg-surface"
              aria-label={`Open ${name.replace(/_/g, " ")} drill-down`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold capitalize text-ink">
                  {name.replace(/_/g, " ")}
                </span>
                <Badge tone={TONE_FOR_STATUS(metrics.status)}>{metrics.status}</Badge>
              </div>
              <dl className="grid grid-cols-3 gap-2 text-2xs text-ink-muted">
                <div>
                  <dt>p50</dt>
                  <dd className="font-mono text-ink">
                    {metrics.latency_p50_ms !== null && metrics.latency_p50_ms !== undefined
                      ? `${fmt.decimal(metrics.latency_p50_ms, 1)}ms`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt>p95</dt>
                  <dd className="font-mono text-ink">
                    {metrics.latency_p95_ms !== null && metrics.latency_p95_ms !== undefined
                      ? `${fmt.decimal(metrics.latency_p95_ms, 1)}ms`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt>dec/min</dt>
                  <dd className="font-mono text-ink">{metrics.decisions_per_min ?? "—"}</dd>
                </div>
              </dl>
              {metrics.calibration_coverage_90 !== null &&
                metrics.calibration_coverage_90 !== undefined && (
                  <div className="flex items-center justify-between text-2xs text-ink-muted">
                    <span>Calibration 90%</span>
                    <ConfidenceChip value={metrics.calibration_coverage_90} threshold={0.85} />
                  </div>
                )}
            </Link>
          );
        })}
        </div>
      </UniversalStateView>
    </section>
  );
}

export type { AgentName };
