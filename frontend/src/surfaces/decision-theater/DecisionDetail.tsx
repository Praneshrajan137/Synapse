import { ConsensusDecisionSchema } from "@domain/consensus-decision";
import {
  AgentProposalChip,
  ConfidenceChip,
  ParetoFrontier,
  type ParetoPoint,
  ReasoningTimeline,
  TierBadge,
} from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { fmt } from "@lib/formatters";
import { phaseName, replayDecision } from "@lib/replay";
import * as Slider from "@radix-ui/react-slider";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

export function DecisionDetail() {
  const { id } = useParams<{ id: string }>();
  // POC: api/v1/decisions/{id} returns a richer row; we map it into our
  // ConsensusDecision Zod schema for replay purity.
  const query = useQuery({
    queryKey: ["decision", id],
    queryFn: async () => {
      // Use the typed HTTP client directly through the API surface; the
      // GET /api/v1/decisions/{id} endpoint isn't on the typed client
      // yet (P4 will codegen via OpenAPI), so we hand-fetch with a
      // schema validation step.
      const resp = await fetch(`/api/v1/decisions/${id}`);
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
      const raw = (await resp.json()) as Record<string, unknown>;
      // Re-shape into ConsensusDecision shape for the replay function.
      const candidate = {
        decision_id: raw.decision_id ?? id,
        timestamp: raw.created_at ?? new Date().toISOString(),
        tier: raw.tier ?? "tier_2",
        proposals: raw.proposals ?? [],
        selected_action: raw.selected_action ?? {},
        pareto_weights: raw.pareto_weights ?? {},
        confidence: raw.confidence ?? 0,
        audit_trace: raw.audit_trace ?? [],
        phase_reached: raw.phase_reached ?? 1,
        debate_rounds: raw.debate_rounds ?? 0,
        human_override: raw.human_override ?? null,
        context_messages: raw.context_messages ?? [],
        execution_confirmations: raw.execution_confirmations ?? [],
        escalated_to_human: raw.escalated ?? false,
      };
      const parsed = ConsensusDecisionSchema.safeParse(candidate);
      if (!parsed.success) {
        throw new Error(`schema violation: ${parsed.error.issues[0]?.message ?? "unknown"}`);
      }
      return { decision: parsed.data, raw };
    },
    enabled: !!id,
  });

  const decision = query.data?.decision;

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
          <h1 className="font-mono text-xl font-semibold text-ink">{decision.decision_id}</h1>
          <TierBadge tier={decision.tier} />
          <ConfidenceChip value={decision.confidence} />
          {decision.escalated_to_human && <Badge tone="warning">Escalated</Badge>}
        </div>
        <p className="text-2xs text-ink-subtle">Committed {fmt.relativeTime(decision.timestamp)}</p>
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
                  return (
                    <AgentProposalChip
                      key={`${agentName}-${i}`}
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
                  );
                })}
              </div>
            )}
          </div>

          {paretoPoints.length > 1 && (
            <div className="syn-card-raised space-y-2 p-4">
              <h2 className="text-sm font-semibold text-ink">Pareto frontier</h2>
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
              {slice.auditTraceSoFar.map((line, i) => (
                <li key={i} className="break-words font-mono text-2xs">
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
