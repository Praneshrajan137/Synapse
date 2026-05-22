import { AGENT_NAMES, type AgentMetrics, type AgentName } from "@domain/agent-health";
import { CalibrationCurve, ConfidenceChip, TierBadge } from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

function isAgentName(value: string | undefined): value is AgentName {
  return !!value && (AGENT_NAMES as readonly string[]).includes(value);
}

/** Per-agent drill-down. P2 ships latency + calibration; P3 adds reward source link. */
export function AgentDetail() {
  const { name } = useParams<{ name: string }>();
  const api = useSynapseApi();
  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.listAgents(),
    refetchInterval: 5_000,
  });

  const decisions = useFirehoseStore((s) => s.decisions.items);

  // All hooks run unconditionally (rules-of-hooks); the unknown-agent guard
  // is deferred until after every hook below.
  const value = agents.data?.agents?.[name ?? ""] as AgentMetrics | string | undefined;
  const metrics: AgentMetrics =
    typeof value === "string" ? { status: value } : (value ?? { status: "unknown" });

  const lastDecisions = useMemo(
    () =>
      decisions
        .filter((d) => d.proposals.some((p) => (p as Record<string, unknown>).agent_name === name))
        .slice(-12)
        .reverse(),
    [decisions, name],
  );

  // Synthetic calibration curve from current coverage; P3 swaps for real
  // histogram from /api/v1/metrics/agents.
  const curvePoints = useMemo(() => {
    const cov = metrics.calibration_coverage_90 ?? 0.85;
    return [0.1, 0.25, 0.5, 0.75, 0.9, 1].map((nominal) => ({
      nominal,
      empirical: Math.min(1, nominal * (cov / 0.9)),
    }));
  }, [metrics.calibration_coverage_90]);

  if (!isAgentName(name)) {
    return (
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold text-ink">Unknown agent</h1>
        <p className="text-sm text-ink-muted">
          <Link to="/agents" className="text-accent underline">
            Back to Agent Council
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/agents" className="text-2xs text-ink-muted hover:text-ink">
            ← Agent Council
          </Link>
          <h1 className="text-2xl font-semibold capitalize text-ink">{name.replace(/_/g, " ")}</h1>
        </div>
        <Badge tone={metrics.status === "healthy" ? "success" : "warning"}>{metrics.status}</Badge>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        {(["latency_p50_ms", "latency_p95_ms", "latency_p99_ms"] as const).map((field) => (
          <div key={field} className="syn-card-raised p-3">
            <div className="text-2xs uppercase tracking-wide text-ink-muted">
              {field.replace("latency_", "").replace("_ms", "")}
            </div>
            <div className="mt-1 font-mono text-2xl text-ink">
              {metrics[field] !== null && metrics[field] !== undefined
                ? `${fmt.decimal(metrics[field] as number, 1)}ms`
                : "—"}
            </div>
          </div>
        ))}
      </div>

      <section className="syn-card-raised space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink">Calibration coverage</h2>
        <p className="text-2xs text-ink-muted">
          INV-DP-002 requires ≥85% empirical coverage on the 90% MAPIE interval.
        </p>
        <CalibrationCurve points={curvePoints} />
        {metrics.calibration_coverage_90 !== null &&
          metrics.calibration_coverage_90 !== undefined && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-ink-muted">Current:</span>
              <ConfidenceChip value={metrics.calibration_coverage_90} threshold={0.85} />
            </div>
          )}
      </section>

      <section className="syn-card overflow-hidden">
        <header className="border-b border-border px-3 py-2 text-2xs uppercase tracking-wide text-ink-muted">
          Recent decisions (firehose)
        </header>
        <ul className="divide-y divide-border">
          {lastDecisions.length === 0 && (
            <li className="px-3 py-6 text-center text-xs text-ink-muted">
              Waiting for decisions involving {name.replace(/_/g, " ")}…
            </li>
          )}
          {lastDecisions.map((d) => (
            <li key={d.decision_id} className="flex items-center gap-3 px-3 py-2 text-xs">
              <span className="font-mono text-ink-muted">{fmt.shortId(d.decision_id)}</span>
              <TierBadge tier={d.tier} />
              <ConfidenceChip value={d.confidence} />
              <span className="ml-auto text-ink-subtle">{fmt.relativeTime(d.timestamp)}</span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
