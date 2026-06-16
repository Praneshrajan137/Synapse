import {
  AgentProposalChip,
  ChainIntegrityChip,
  ConfidenceChip,
  ParetoFrontier,
  ParetoParallel,
  type ParetoPoint,
  ProvenanceChip,
  type ProvenanceLike,
  ReasoningTimeline,
  SyntheticBadge,
  TierBadge,
  TwinDivergenceCaveat,
} from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useDecisionQuery } from "@hooks/use-decision";
import { useFirehose } from "@hooks/use-firehose";
import { fmt } from "@lib/formatters";
import { phaseName, replayDecision } from "@lib/replay";
import * as Slider from "@radix-ui/react-slider";
import { useCallback, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

export function DecisionDetail() {
  const { id } = useParams<{ id: string }>();
  // Shared, validated decision source (hooks/use-decision). The Council Theater
  // consumes the SAME hook, so the analyst scrubber here and the cinematic
  // reconstruction there can never drift on the reshape (FE-INV-002).
  const query = useDecisionQuery(id);

  const decision = query.data?.decision;
  const raw = query.data?.raw;

  // Live twin-divergence feed for the trust caveat next to confidence —
  // confidence numbers rest on the twin's world-model (I-12).
  useFirehose({ topics: ["twin"] });

  // URL-synced replay phase (FE-INV-028): `?phase=N` is the source of
  // truth so a replay frame is shareable. The Zod parser tolerates the
  // missing/invalid case by falling back to the decision's terminal
  // phase, mirroring the prior useState default. Setter uses
  // `replace: true` so the back button doesn't accumulate one entry
  // per slider tick.
  const [searchParams, setSearchParams] = useSearchParams();
  const phaseParsed = useMemo(
    () => z.coerce.number().int().min(1).max(5).safeParse(searchParams.get("phase")),
    [searchParams],
  );
  const phase = phaseParsed.success ? phaseParsed.data : (decision?.phase_reached ?? 1);

  const setPhase = useCallback(
    (next: number) => {
      const clamped = Math.max(1, Math.min(5, Math.floor(next)));
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          params.set("phase", String(clamped));
          return params;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const slice = useMemo(
    () => (decision ? replayDecision(decision, phase) : null),
    [decision, phase],
  );

  // The genuine 8-D arbitration front (numeric-coerced from the open proto
  // shape). Empty when the audit row carries none (fast-path / older rows).
  const paretoFront = useMemo(() => {
    const raw = decision?.pareto_front;
    if (!raw) return [];
    return raw.map((r) => {
      const out: Record<string, number> = {};
      for (const [k, v] of Object.entries(r)) {
        if (typeof v === "number") out[k] = v;
      }
      return out;
    });
  }, [decision]);

  const paretoPoints: ParetoPoint[] = useMemo(() => {
    if (!slice) return [];
    return slice.proposalsVisible.map((p, i) => {
      const agentName = typeof p.agent_name === "string" ? p.agent_name : `proposal-${i}`;
      return {
        id: `${agentName}-${i}`,
        x: typeof p.utility_score === "number" ? p.utility_score : 0,
        y: typeof p.confidence === "number" ? p.confidence : 0,
        label: agentName,
      };
    });
  }, [slice]);

  if (query.isLoading) {
    return <p className="text-sm text-ink-muted">Loading decision…</p>;
  }
  if (query.isError || !decision || !slice) {
    return (
      <div role="alert" className="text-sm text-confidence-risk">
        Decision unavailable: {(query.error as Error | undefined)?.message ?? "not found"}
        <div className="mt-2">
          <Link to="/decisions" className="text-2xs text-accent underline">
            Back to Decision Theater
          </Link>
        </div>
      </div>
    );
  }

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <Link to="/decisions" className="text-2xs text-ink-muted hover:text-ink">
          ← Decision Theater
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-mono text-lg font-medium tracking-tight text-ink">
            {decision.decision_id}
          </h1>
          <TierBadge tier={decision.tier} />
          <ConfidenceChip value={decision.confidence} />
          <TwinDivergenceCaveat />
          {decision.escalated_to_human && <Badge tone="warning">Escalated</Badge>}
          {raw?.is_synthetic && <SyntheticBadge />}
          <ChainIntegrityChip
            verified={raw?.chain_verified}
            prevHash={raw?.prev_hash}
            currentHash={raw?.current_hash}
          />
        </div>
        <p className="text-2xs text-ink-subtle">Committed {fmt.relativeTime(decision.timestamp)}</p>
        <Link
          to={`/council/${decision.decision_id}`}
          className="inline-flex w-fit items-center gap-1 text-2xs font-medium text-accent hover:underline"
        >
          Watch deliberation →
        </Link>
      </header>

      <section className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="syn-card-raised space-y-3 p-4">
          <h2 className="text-2xs uppercase tracking-wide text-ink-muted">Phases</h2>
          <ReasoningTimeline phaseReached={decision.phase_reached} activePhase={phase} />
        </aside>
        <div className="space-y-4">
          <div className="syn-card-raised space-y-3 p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-ink">
                Replay — phase {phase}/5 ({phaseName(phase as 1 | 2 | 3 | 4 | 5)})
              </h2>
              <span className="text-2xs text-ink-muted">
                debate rounds: {slice.debateRoundsCompleted}
              </span>
            </div>
            <Slider.Root
              min={1}
              max={5}
              step={1}
              value={[phase]}
              onValueChange={(v) => setPhase(v[0] ?? 1)}
              className="relative flex h-6 w-full touch-none select-none items-center"
              aria-label="Phase scrubber"
            >
              <Slider.Track className="relative h-1.5 grow rounded-full bg-surface">
                <Slider.Range className="absolute h-full rounded-full bg-accent" />
              </Slider.Track>
              <Slider.Thumb className="block h-4 w-4 rounded-full border border-accent bg-canvas focus-visible:outline-none focus-visible:shadow-focus" />
            </Slider.Root>
          </div>

          <div className="syn-card-raised space-y-3 p-4">
            <h2 className="text-sm font-semibold text-ink">Proposals at this phase</h2>
            {slice.proposalsVisible.length === 0 ? (
              <p className="text-xs text-ink-muted">No proposals visible at this phase yet.</p>
            ) : (
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
                {slice.proposalsVisible.map((p, i) => {
                  const agentName =
                    typeof p.agent_name === "string" ? p.agent_name : `proposal-${i}`;
                  // Stable identity: agent_name + utility_score is unique within a
                  // phase slice; falling back to agentName alone is also stable
                  // because two proposals with the same agent_name would be a
                  // domain bug, not a key collision.
                  const stableKey = `${agentName}:${p.utility_score ?? "u"}:${p.confidence ?? "c"}`;
                  // ADR-044: structured provenance rides inside the proposal.
                  const provenance =
                    p.provenance && typeof p.provenance === "object"
                      ? (p.provenance as ProvenanceLike)
                      : null;
                  const justification = Array.isArray(p.justification_trace)
                    ? p.justification_trace
                    : [];
                  return (
                    <div key={stableKey} className="space-y-1">
                      <AgentProposalChip
                        agentName={agentName}
                        utilityScore={
                          typeof p.utility_score === "number" ? p.utility_score : undefined
                        }
                        confidence={typeof p.confidence === "number" ? p.confidence : undefined}
                        status={
                          (p.status as
                            | "proposed"
                            | "rejected"
                            | "selected"
                            | "modified"
                            | undefined) ?? "proposed"
                        }
                      />
                      <ProvenanceChip provenance={provenance} />
                      {justification.length > 0 && (
                        <details className="text-2xs text-ink-muted">
                          <summary className="cursor-pointer">
                            Justification ({justification.length})
                          </summary>
                          <ul className="mt-1 list-disc space-y-0.5 pl-4">
                            {justification.map((line) => (
                              <li key={line} className="break-words">
                                {line}
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {(decision.execution_confirmations.length > 0 ||
            (raw?.outcome && Object.keys(raw.outcome).length > 0)) && (
            <div className="syn-card-raised grid gap-4 p-4 md:grid-cols-2">
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-ink">Execution confirmations</h2>
                {decision.execution_confirmations.length === 0 ? (
                  <p className="text-xs text-ink-muted">No confirmations recorded.</p>
                ) : (
                  <ul className="space-y-1 text-xs">
                    {decision.execution_confirmations.map((c, i) => (
                      <li key={`${c}-${String(i)}`} className="flex items-center gap-2 font-mono">
                        <span
                          className={
                            c.startsWith("error") ? "text-signal-danger" : "text-signal-success"
                          }
                          aria-hidden
                        >
                          {c.startsWith("error") ? "✗" : "✓"}
                        </span>
                        <span className="break-all text-ink-muted">{c}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {raw?.outcome &&
                Object.keys(raw.outcome).length > 0 &&
                (() => {
                  // ADR-047: the scored outcome from the append-only
                  // decision_outcomes stream. Tri-state (FE-INV-041): `unknown`
                  // is its own drained state, NEVER shown as confirmed.
                  const o = raw.outcome as Record<string, unknown>;
                  const status = typeof o.status === "string" ? o.status : "unknown";
                  const tone =
                    status === "confirmed"
                      ? "text-signal-success"
                      : status === "diverged"
                        ? "text-signal-danger"
                        : "text-state-degraded";
                  const label =
                    status === "confirmed"
                      ? "Confirmed — played out as decided"
                      : status === "diverged"
                        ? "Diverged — reality differed"
                        : "Unknown — not yet realized";
                  return (
                    <div className="space-y-2">
                      <h2 className="text-sm font-semibold text-ink">Outcome</h2>
                      <p className={`text-sm font-medium ${tone}`}>
                        <span aria-hidden>
                          {status === "confirmed" ? "✓ " : status === "diverged" ? "✗ " : "? "}
                        </span>
                        {label}
                      </p>
                      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                        {typeof o.source === "string" && o.source !== "none" && (
                          <div className="contents">
                            <dt className="text-ink-muted">realized via</dt>
                            <dd className="font-mono text-ink">{o.source.replace(/_/g, " ")}</dd>
                          </div>
                        )}
                        {typeof o.error === "number" && (
                          <div className="contents">
                            <dt className="text-ink-muted">error</dt>
                            <dd className="font-mono tabular-nums text-ink">
                              {o.error.toFixed(3)}
                            </dd>
                          </div>
                        )}
                        {typeof o.scored_at === "string" && (
                          <div className="contents">
                            <dt className="text-ink-muted">scored</dt>
                            <dd className="text-ink">{fmt.relativeTime(o.scored_at)}</dd>
                          </div>
                        )}
                      </dl>
                    </div>
                  );
                })()}
            </div>
          )}

          {Array.isArray(raw?.escalations) && raw.escalations.length > 0 && (
            <div className="syn-card-raised space-y-2 p-4">
              <h2 className="text-sm font-semibold text-ink">Operator overrides</h2>
              <ul className="space-y-2">
                {(raw.escalations as Array<Record<string, unknown>>).map((e) => (
                  <li
                    key={String(e.audit_escalation_id ?? e.override_at)}
                    className="flex flex-wrap items-center gap-2 text-xs"
                  >
                    <Badge
                      tone={
                        e.override_action === "approved"
                          ? "success"
                          : e.override_action === "rejected"
                            ? "danger"
                            : "warning"
                      }
                    >
                      {String(e.override_action ?? "pending")}
                    </Badge>
                    <span className="font-mono text-ink-muted">
                      {String(e.operator_token_ref ?? "")}
                    </span>
                    <span className="text-ink-muted">{String(e.override_reason ?? "")}</span>
                    {typeof e.override_at === "string" && (
                      <span className="ml-auto text-ink-subtle">
                        {fmt.relativeTime(e.override_at)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="syn-card-raised space-y-2 p-4">
            <h2 className="text-sm font-semibold text-ink">Consensus front — 8 objectives</h2>
            <p className="text-2xs text-ink-muted">
              The non-dominated arbitration front. Each axis is one objective in its agent's colour;
              the chosen knee-point solution is bold.
            </p>
            <ParetoParallel front={paretoFront} weights={decision.pareto_weights} />
          </div>

          {paretoPoints.length > 1 && (
            <div className="syn-card-raised space-y-2 p-4">
              <h2 className="text-sm font-semibold text-ink">Proposal utility × confidence</h2>
              <ParetoFrontier
                points={paretoPoints}
                weights={decision.pareto_weights}
                xLabel="utility"
                yLabel="confidence"
              />
            </div>
          )}

          <details className="syn-card p-3 text-xs text-ink-muted">
            <summary className="cursor-pointer text-sm font-medium text-ink">
              Audit trace (cumulative through phase)
            </summary>
            <ol className="mt-2 list-decimal space-y-1 pl-5">
              {slice.auditTraceSoFar.map((line) => (
                // The trace is an append-only ledger; each line is unique by
                // content (timestamp + decision-id + action are all present).
                <li key={line} className="break-words font-mono text-2xs">
                  {line}
                </li>
              ))}
            </ol>
          </details>
        </div>
      </section>
    </section>
  );
}
