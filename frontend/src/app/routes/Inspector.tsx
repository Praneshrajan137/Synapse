import { useAgentDetail } from "@/application/observability";
import type { AgentDetail } from "@/domain/observability";
import { KPISpark } from "@/ui/charts/KPISpark";
import { AgentSigil } from "@/ui/icons";
import { AGENT_LABEL } from "@/ui/icons/AgentSigil";
import { cn } from "@/ui/lib/cn";
import { Card, CardBody, CardHeader, CardTitle } from "@/ui/primitives";
import { AGENT_NAMES, type AgentName, agentColor } from "@/ui/tokens";
import { useNavigate, useParams } from "react-router-dom";

/**
 * Inspector — per-agent x-ray (plan section 5.6): rewards, latency,
 * confidence calibration, recent decisions and A2A traffic.
 */

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-display text-2xs font-semibold uppercase tracking-[0.1em] text-ink-hint">
        {label}
      </span>
      <span className="tnum font-display text-lg font-semibold text-ink-primary">
        {value}
      </span>
    </div>
  );
}

function ConfidenceHistogram({ detail }: { detail: AgentDetail }) {
  const max = Math.max(1, ...detail.confidenceHistogram);
  return (
    <div className="flex h-20 items-end gap-1">
      {detail.confidenceHistogram.map((count, i) => (
        <div
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed 10-bucket histogram
          key={i}
          className="flex-1 rounded-xs"
          style={{
            height: `${(count / max) * 100}%`,
            backgroundColor: i >= 6 ? "var(--color-sig-ok)" : "var(--color-sig-warn)",
            opacity: 0.5 + (count / max) * 0.5,
          }}
          title={`Confidence bucket ${i / 10}–${(i + 1) / 10}: ${count}`}
        />
      ))}
    </div>
  );
}

export default function Inspector() {
  const params = useParams<{ agentName?: string }>();
  const navigate = useNavigate();
  const active = (
    params.agentName && (AGENT_NAMES as readonly string[]).includes(params.agentName)
      ? params.agentName
      : AGENT_NAMES[0]
  ) as AgentName;
  const { data: detail } = useAgentDetail(active);

  return (
    <div className="flex h-full">
      {/* Agent rail */}
      <nav
        aria-label="Agents"
        className="flex w-52 shrink-0 flex-col gap-0.5 overflow-y-auto border-r border-line-faint bg-paper p-2"
      >
        {AGENT_NAMES.map((agent) => (
          <button
            key={agent}
            type="button"
            onClick={() => navigate(`/inspector/${agent}`)}
            aria-current={agent === active}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-xs transition-colors",
              "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sig-live",
              agent === active
                ? "bg-elevated text-ink-primary"
                : "text-ink-secondary hover:bg-elevated/60",
            )}
          >
            <AgentSigil agent={agent} size={20} />
            <span className="truncate">{AGENT_LABEL[agent]}</span>
          </button>
        ))}
      </nav>

      {/* Detail */}
      <div className="min-w-0 flex-1 overflow-y-auto p-5">
        {!detail ? (
          <div className="flex h-full items-center justify-center text-sm text-ink-hint">
            Loading agent…
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            <header
              className="flex items-center gap-4 rounded-lg border border-line-faint p-4"
              style={{
                background: `linear-gradient(120deg, color-mix(in oklab, ${agentColor[active]} 14%, var(--color-paper)), var(--color-paper))`,
              }}
            >
              <AgentSigil agent={active} size={48} title={AGENT_LABEL[active]} />
              <div className="flex flex-col gap-1">
                <h1 className="font-display text-lg font-semibold text-ink-primary">
                  {AGENT_LABEL[active]}
                </h1>
                <code className="font-mono text-2xs text-ink-secondary">
                  {detail.rewardFunction}
                </code>
              </div>
            </header>

            <div className="grid grid-cols-3 gap-3 rounded-lg border border-line-faint bg-paper p-4">
              <Stat label="p50 latency" value={`${detail.p50LatencyMs}ms`} />
              <Stat label="p99 latency" value={`${detail.p99LatencyMs}ms`} />
              <Stat label="Decisions / min" value={String(detail.decisionsPerMin)} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Card tone="elevated">
                <CardHeader>
                  <CardTitle>Reward curve</CardTitle>
                </CardHeader>
                <CardBody>
                  <KPISpark
                    data={detail.rewardCurve}
                    width={300}
                    height={72}
                    label={`${AGENT_LABEL[active]} reward over training episodes`}
                    color={agentColor[active]}
                  />
                </CardBody>
              </Card>
              <Card tone="elevated">
                <CardHeader>
                  <CardTitle>Confidence distribution</CardTitle>
                </CardHeader>
                <CardBody>
                  <ConfidenceHistogram detail={detail} />
                </CardBody>
              </Card>
            </div>

            {detail.conformal && (
              <Card tone="elevated">
                <CardHeader>
                  <CardTitle>Conformal calibration</CardTitle>
                  <span className="text-2xs text-ink-hint">target 90% coverage</span>
                </CardHeader>
                <CardBody>
                  <ul className="flex flex-col gap-1.5">
                    {detail.conformal.map((c) => {
                      const drift = Math.abs(c.actual - c.target);
                      return (
                        <li key={c.horizon} className="flex items-center gap-3 text-2xs">
                          <span className="w-10 font-mono text-ink-secondary">
                            {c.horizon}
                          </span>
                          <div className="h-1.5 flex-1 rounded-full bg-membrane">
                            <div
                              className="h-full rounded-full bg-sig-trace"
                              style={{ width: `${c.actual * 100}%` }}
                            />
                          </div>
                          <span
                            className="tnum font-mono"
                            style={{
                              color:
                                drift > 0.02
                                  ? "var(--color-sig-warn)"
                                  : "var(--color-ink-secondary)",
                            }}
                          >
                            {(c.actual * 100).toFixed(0)}%
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </CardBody>
              </Card>
            )}

            <Card tone="elevated">
              <CardHeader>
                <CardTitle>A2A traffic</CardTitle>
              </CardHeader>
              <CardBody className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-2xs text-ink-hint">produces</span>
                  {detail.topicsProduced.map((t) => (
                    <span
                      key={t}
                      className="rounded-xs border border-line-faint bg-membrane px-1.5 py-0.5 font-mono text-2xs text-ink-secondary"
                    >
                      {t}
                    </span>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-2xs text-ink-hint">consumes</span>
                  {detail.topicsConsumed.map((t) => (
                    <span
                      key={t}
                      className="rounded-xs border border-line-faint bg-membrane px-1.5 py-0.5 font-mono text-2xs text-ink-secondary"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </CardBody>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
