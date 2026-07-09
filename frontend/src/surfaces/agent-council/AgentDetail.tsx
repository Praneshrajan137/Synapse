import { AGENT_NAMES, type AgentMetrics, type AgentName } from "@domain/agent-health";
import type { LiveDecision } from "@domain/decision-envelope";
import { CalibrationCurve, ConfidenceChip, TierBadge } from "@ds/compounds";
import { mapAgentHealth, processStateFor } from "@ds/compounds/CouncilStrip";
import { Badge } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { AGENT_COLOR_VAR, type AgentName as IdentityAgentName } from "@lib/agent-identity";
import { processStateColor } from "@lib/chromatics";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

function isAgentName(value: string | undefined): value is AgentName {
  return !!value && (AGENT_NAMES as readonly string[]).includes(value);
}

/**
 * The agent's current process state (ADR-044 grammar): acting when it
 * contributed to a recent live decision, waiting when healthy and idle,
 * interrupted when unreachable. Identity hue stays frozen; the state is
 * the chroma ration + the state WORD (INV-CLR-011, FE-INV-040).
 */
function ProcessStatePanel({
  name,
  metrics,
  decisions,
}: {
  readonly name: AgentName;
  readonly metrics: AgentMetrics;
  readonly decisions: ReadonlyArray<LiveDecision>;
}) {
  const active = useMemo(
    () => decisions.slice(-8).some((d) => d.agents.some((a) => a.agent_name === name)),
    [decisions, name],
  );
  const state = processStateFor({ status: mapAgentHealth(metrics.status), active });
  if (!state) return null;
  const colorVar = AGENT_COLOR_VAR[name as IdentityAgentName];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1 text-2xs font-medium uppercase tracking-wide text-ink-muted"
      data-process-state={state}
    >
      <span
        className="size-2 rounded-full"
        style={{ background: processStateColor(colorVar, state) }}
        aria-hidden
      />
      {state}
    </span>
  );
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
      // ADR-044: the live envelope's lean `agents` summary names the
      // contributing agents (the full proposals stay in the audit row).
      decisions
        .filter((d) => d.agents.some((a) => a.agent_name === name))
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
          <h1 className="font-display text-display-md font-semibold capitalize text-ink">
            {name.replace(/_/g, " ")}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <ProcessStatePanel name={name} metrics={metrics} decisions={decisions} />
          <Badge tone={metrics.status === "healthy" ? "success" : "warning"}>
            {metrics.status}
          </Badge>
        </div>
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
            // FE-INV-004 / Req 4.1: every rendered decision carries Tier +
            // Confidence AND a single-activation route to its audit row. The
            // whole row is one anchor, so one pointer click OR one keyboard
            // activation opens the decision detail (the audit-anchored replay).
            <li key={d.decision_id}>
              <Link
                to={`/decisions/${d.decision_id}`}
                aria-label={`Open audit detail for decision ${fmt.shortId(d.decision_id)}`}
                className="flex items-center gap-3 px-3 py-2 text-xs transition-colors duration-fast hover:bg-surface-raised/60 focus-visible:outline-none focus-visible:shadow-focus"
              >
                <span className="font-mono text-ink-muted">{fmt.shortId(d.decision_id)}</span>
                <TierBadge tier={d.tier} />
                <ConfidenceChip value={d.confidence} />
                <span className="ml-auto text-ink-subtle">{fmt.relativeTime(d.timestamp)}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
