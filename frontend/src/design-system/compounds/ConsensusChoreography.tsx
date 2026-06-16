import type { ConsensusDecision } from "@domain/consensus-decision";
import { fmt } from "@lib/formatters";
import { phaseName, replayDecision } from "@lib/replay";
import * as Slider from "@radix-ui/react-slider";
import type { DecisionDetailResponse } from "@transport/synapse-api";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AgentProposalChip } from "./AgentProposalChip";
import { ChainIntegrityChip } from "./ChainIntegrityChip";
import { ConfidenceChip } from "./ConfidenceChip";
import { ParetoFrontier, type ParetoPoint } from "./ParetoFrontier";
import { ParetoParallel } from "./ParetoParallel";
import { ProposalConstellation } from "./ProposalConstellation";
import { ReasoningTimeline } from "./ReasoningTimeline";
import { SyntheticBadge } from "./SyntheticBadge";

/**
 * ConsensusChoreography — the five-phase council deliberation, narrated.
 *
 * SYNAPSE's real "thinking" is the consensus FSM in
 * `orchestrator/consensus/protocol.py`: COLLECTING → DEBATING → ARBITRATING →
 * EXECUTING → LEARNING. All of it is recorded in `audit_consensus` and exposed
 * by `GET /api/v1/decisions/{id}`, but the analyst surface renders it as a
 * manual slider. This compound turns the SAME recorded row into an
 * auto-narrated reconstruction so the deliberation reads as the causal story it
 * is.
 *
 * Honest by construction (I-7): every element is a slice of the recorded row
 * via the pure `replayDecision` (FE-INV-028) — the auto-advance drives only the
 * phase INDEX, never the slice. A phase the row did not record (no debate on a
 * fast path, no Pareto front) renders an explicit "not recorded" state; nothing
 * is invented. It is labelled a RECORDED RECONSTRUCTION, never "live" — the live
 * cognition channel is the deferred follow-up (ADR-048).
 *
 * Motion is causality, not decoration: phases cross-fade in sequence, and
 * `prefers-reduced-motion` collapses the player into a static, all-phases-at-once
 * reveal where every state is carried by text (FE-INV-046, parity with
 * FE-INV-040). Colour reaches the screen only through chromatic tokens — agent
 * hues, the confidence scale (INV-CLR-009/012).
 */

const PHASE_BLURB = {
  proposal: "Eight specialists submit independent proposals.",
  debate: "Agents reconcile conflicts over up to three rounds.",
  arbitration: "A Pareto front is computed; the knee-point solution is chosen.",
  execution: "The decision is dispatched and confirmations are bound.",
  learning: "Weights and the semantic cache update from the realized outcome.",
} as const;

// Per-phase dwell for the auto-narration. A sequencing cadence (not a new
// easing/spring curve) — the motion grammar itself is unchanged.
const PHASE_DWELL_MS = 2200;

/** Best-effort speaker + text from an open-shape recited context message. */
function messageLine(m: Record<string, unknown>): { speaker: string | null; text: string } {
  const speaker =
    typeof m.agent_name === "string"
      ? m.agent_name
      : typeof m.role === "string"
        ? m.role
        : typeof m.speaker === "string"
          ? m.speaker
          : null;
  const text =
    typeof m.content === "string"
      ? m.content
      : typeof m.message === "string"
        ? m.message
        : typeof m.text === "string"
          ? m.text
          : JSON.stringify(m);
  return { speaker, text };
}

export interface ConsensusChoreographyProps {
  readonly decision: ConsensusDecision;
  /** Raw envelope for the honesty fields the strict schema does not carry. */
  readonly raw?: DecisionDetailResponse | undefined;
  /** Auto-narrate from phase 1 on mount (motion only). Default true. */
  readonly autoPlay?: boolean | undefined;
  /** Park on a specific phase (e.g. a shared `?phase=` link). Suppresses autoplay. */
  readonly initialPhase?: number | undefined;
  /** Fired when the operator parks on a phase (scrub / step) — for URL sync. */
  readonly onPhaseChange?: ((phase: number) => void) | undefined;
}

export function ConsensusChoreography({
  decision,
  raw,
  autoPlay = true,
  initialPhase,
  onPhaseChange,
}: ConsensusChoreographyProps) {
  const reduced = useReducedMotion() ?? false;
  const maxPhase = Math.max(1, Math.min(5, decision.phase_reached));

  const clampPhase = useCallback(
    (n: number) => Math.max(1, Math.min(maxPhase, Math.floor(n))),
    [maxPhase],
  );

  const [phase, setPhase] = useState<number>(() =>
    initialPhase != null ? clampPhase(initialPhase) : autoPlay ? 1 : maxPhase,
  );
  const [playing, setPlaying] = useState<boolean>(() => autoPlay && initialPhase == null);

  // Auto-advance (motion only). Drives ONLY the phase index; `replayDecision`
  // stays pure (FE-INV-028). Reduced motion never plays; manual nav pauses.
  useEffect(() => {
    if (!playing || reduced) return;
    if (phase >= maxPhase) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setPhase((p) => Math.min(maxPhase, p + 1)), PHASE_DWELL_MS);
    return () => clearTimeout(t);
  }, [playing, reduced, phase, maxPhase]);

  const goToPhase = useCallback(
    (next: number) => {
      setPlaying(false);
      const c = clampPhase(next);
      setPhase(c);
      onPhaseChange?.(c);
    },
    [clampPhase, onPhaseChange],
  );

  const atEnd = phase >= maxPhase;
  const togglePlay = useCallback(() => {
    if (reduced) return;
    if (atEnd) {
      setPhase(1);
      setPlaying(true);
      onPhaseChange?.(1);
    } else {
      setPlaying((p) => !p);
    }
  }, [reduced, atEnd, onPhaseChange]);

  const paretoFront = useMemo<Record<string, number>[]>(() => {
    const f = decision.pareto_front;
    if (!f) return [];
    return f.map((r) => {
      const out: Record<string, number> = {};
      for (const [k, v] of Object.entries(r)) if (typeof v === "number") out[k] = v;
      return out;
    });
  }, [decision]);

  const paretoPoints = useMemo<ParetoPoint[]>(
    () =>
      decision.proposals.map((pp, i) => {
        const name = typeof pp.agent_name === "string" ? pp.agent_name : `proposal-${i}`;
        return {
          id: `${name}-${String(i)}`,
          x: typeof pp.utility_score === "number" ? pp.utility_score : 0,
          y: typeof pp.confidence === "number" ? pp.confidence : 0,
          label: name,
        };
      }),
    [decision],
  );

  // ─── Per-phase bodies — each a slice of the recorded row ──────────────────

  const collectBody = () => (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <ProposalConstellation proposals={decision.proposals} />
      <div className="space-y-2">
        <h4 className="text-2xs uppercase tracking-wide text-ink-muted">
          Proposals collected ({decision.proposals.length})
        </h4>
        {decision.proposals.length === 0 ? (
          <p className="text-xs text-ink-muted">No proposals recorded for this decision.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {decision.proposals.map((pp, i) => {
              const name = typeof pp.agent_name === "string" ? pp.agent_name : `proposal-${i}`;
              return (
                <AgentProposalChip
                  key={`${name}:${pp.utility_score ?? "u"}:${pp.confidence ?? "c"}`}
                  agentName={name}
                  utilityScore={typeof pp.utility_score === "number" ? pp.utility_score : undefined}
                  confidence={typeof pp.confidence === "number" ? pp.confidence : undefined}
                  status={
                    (pp.status as "proposed" | "rejected" | "selected" | "modified" | undefined) ??
                    "proposed"
                  }
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );

  const debateBody = () => {
    const transcript = decision.context_messages;
    const hasDebate = decision.debate_rounds > 0 && transcript.length > 0;
    if (!hasDebate) {
      return (
        <div className="rounded-sm border border-border bg-surface p-4">
          <p className="text-sm font-medium text-ink">No debate — fast path.</p>
          <p className="mt-1 text-xs text-ink-muted">
            Tier 1–2 decisions skip the LLM debate round; the initial proposals went straight to
            arbitration. This decision recorded {decision.debate_rounds} debate round
            {decision.debate_rounds === 1 ? "" : "s"}.
          </p>
        </div>
      );
    }
    return (
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ProposalConstellation proposals={decision.proposals} debating />
        <div className="space-y-2">
          <h4 className="text-2xs uppercase tracking-wide text-ink-muted">
            Debate transcript · {decision.debate_rounds} round
            {decision.debate_rounds === 1 ? "" : "s"}
          </h4>
          <ol className="space-y-2">
            {transcript.map((m, i) => {
              const { speaker, text } = messageLine(m);
              return (
                <li
                  key={`${String(i)}-${text.slice(0, 24)}`}
                  className="rounded-sm bg-surface-raised p-2 text-xs"
                >
                  {speaker && (
                    <span className="mr-1 font-semibold capitalize text-ink">
                      {speaker.replace(/_/g, " ")}:
                    </span>
                  )}
                  <span className="break-words text-ink-muted">{text}</span>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    );
  };

  const arbitrateBody = () => (
    <div className="space-y-3">
      <div className="space-y-2">
        <h4 className="text-2xs uppercase tracking-wide text-ink-muted">
          Consensus front — 8 objectives
        </h4>
        <p className="text-2xs text-ink-muted">
          The non-dominated arbitration front; the chosen knee-point solution is bold.
          {paretoFront.length === 0 && " This decision recorded no Pareto front (fast path)."}
        </p>
        <ParetoParallel front={paretoFront} weights={decision.pareto_weights} />
      </div>
      {paretoPoints.length > 1 && (
        <div className="space-y-2">
          <h4 className="text-2xs uppercase tracking-wide text-ink-muted">
            Proposal utility × confidence
          </h4>
          <ParetoFrontier
            points={paretoPoints}
            weights={decision.pareto_weights}
            xLabel="utility"
            yLabel="confidence"
          />
        </div>
      )}
    </div>
  );

  const executeBody = () => {
    const actionEntries = Object.entries(decision.selected_action).filter(([, v]) => v != null);
    const confirmations = decision.execution_confirmations;
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <h4 className="text-2xs uppercase tracking-wide text-ink-muted">Selected action</h4>
          {actionEntries.length === 0 ? (
            <p className="text-xs text-ink-muted">No action payload recorded.</p>
          ) : (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {actionEntries.map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-ink-muted">{k.replace(/_/g, " ")}</dt>
                  <dd className="break-words font-mono text-ink">
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {decision.escalated_to_human && (
            <p className="text-xs font-medium text-confidence-warn">
              Escalated to a human operator (I-5).
            </p>
          )}
        </div>
        <div className="space-y-2">
          <h4 className="text-2xs uppercase tracking-wide text-ink-muted">
            Execution confirmations
          </h4>
          {confirmations.length === 0 ? (
            <p className="text-xs text-ink-muted">No confirmations recorded.</p>
          ) : (
            <ul className="space-y-1 text-xs">
              {confirmations.map((c, i) => (
                <li key={`${c}-${String(i)}`} className="flex items-center gap-2 font-mono">
                  <span
                    className={c.startsWith("error") ? "text-signal-danger" : "text-signal-success"}
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
      </div>
    );
  };

  const learningBody = (slicePhase: number) => {
    const slice = replayDecision(decision, slicePhase);
    const outcome = raw?.outcome;
    const hasOutcome = !!outcome && Object.keys(outcome).length > 0;
    // ADR-047 tri-state: `unknown` is its own drained state, NEVER "confirmed".
    let outcomeNode = null;
    if (hasOutcome) {
      const o = outcome as Record<string, unknown>;
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
      outcomeNode = (
        <div className="space-y-1">
          <h4 className="text-2xs uppercase tracking-wide text-ink-muted">Outcome</h4>
          <p className={`text-sm font-medium ${tone}`}>
            <span aria-hidden>
              {status === "confirmed" ? "✓ " : status === "diverged" ? "✗ " : "? "}
            </span>
            {label}
          </p>
        </div>
      );
    }
    return (
      <div className="space-y-3">
        {outcomeNode ?? (
          <p className="text-sm text-ink-muted">
            Learning recorded — meta-RL weights and the semantic cache update from this decision.
            <span className="block text-xs text-ink-subtle">
              No realized outcome scored yet (ADR-047).
            </span>
          </p>
        )}
        {slice.auditTraceSoFar.length > 0 && (
          <details className="text-xs text-ink-muted">
            <summary className="cursor-pointer text-sm font-medium text-ink">Audit trace</summary>
            <ol className="mt-2 list-decimal space-y-1 pl-5">
              {slice.auditTraceSoFar.map((line) => (
                <li key={line} className="break-words font-mono text-2xs">
                  {line}
                </li>
              ))}
            </ol>
          </details>
        )}
      </div>
    );
  };

  const phaseBody = (p: number) => {
    const ph = clampPhase(p);
    if (ph === 1) return collectBody();
    if (ph === 2) return debateBody();
    if (ph === 3) return arbitrateBody();
    if (ph === 4) return executeBody();
    return learningBody(ph);
  };

  const activeName = phaseName(clampPhase(phase) as 1 | 2 | 3 | 4 | 5);

  return (
    <section aria-label="Consensus deliberation reconstruction" className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <span className="rounded-sm bg-surface-raised px-2 py-0.5 text-2xs font-medium uppercase tracking-wide text-ink-muted">
          Recorded reconstruction
        </span>
        <span className="font-mono text-2xs text-ink-subtle">{decision.decision_id}</span>
        <ConfidenceChip value={decision.confidence} />
        {raw?.is_synthetic && <SyntheticBadge />}
        <ChainIntegrityChip
          verified={raw?.chain_verified}
          prevHash={raw?.prev_hash}
          currentHash={raw?.current_hash}
        />
        <span className="ml-auto text-2xs text-ink-subtle">
          Committed {fmt.relativeTime(decision.timestamp)}
        </span>
      </header>

      <div className="grid gap-4 lg:grid-cols-[200px_minmax(0,1fr)]">
        <aside className="syn-card-raised space-y-3 p-4">
          <h3 className="text-2xs uppercase tracking-wide text-ink-muted">Phases</h3>
          <ReasoningTimeline phaseReached={maxPhase} {...(reduced ? {} : { activePhase: phase })} />
        </aside>

        <div className="space-y-3">
          {reduced ? (
            // FE-INV-046: reduced motion → the whole deliberation at once, static,
            // every state carried by text. No autoplay, no scrubber.
            <div className="space-y-4">
              <p className="text-2xs text-ink-muted">
                Reduced motion — the full deliberation is shown at once.
              </p>
              {Array.from({ length: maxPhase }, (_, i) => i + 1).map((p) => (
                <section
                  key={p}
                  className="space-y-2 border-t border-border pt-3 first:border-t-0 first:pt-0"
                >
                  <h3 className="text-sm font-semibold text-ink">
                    Phase {p} —{" "}
                    <span className="capitalize">{phaseName(p as 1 | 2 | 3 | 4 | 5)}</span>
                  </h3>
                  <p className="text-2xs text-ink-muted">
                    {PHASE_BLURB[phaseName(p as 1 | 2 | 3 | 4 | 5)]}
                  </p>
                  {phaseBody(p)}
                </section>
              ))}
            </div>
          ) : (
            <>
              <div className="syn-card-raised flex flex-wrap items-center gap-3 p-3">
                <button
                  type="button"
                  onClick={togglePlay}
                  aria-label={playing ? "Pause" : atEnd ? "Replay from start" : "Play"}
                  className="rounded-sm border border-border px-2.5 py-1 text-xs font-medium text-ink transition-colors duration-fast ease-standard hover:bg-surface focus-visible:outline-none focus-visible:shadow-focus"
                >
                  {playing ? "❚❚ Pause" : atEnd ? "↺ Replay" : "▶ Play"}
                </button>
                <button
                  type="button"
                  onClick={() => goToPhase(phase - 1)}
                  disabled={phase <= 1}
                  aria-label="Previous phase"
                  className="rounded-sm border border-border px-2 py-1 text-xs text-ink-muted transition-colors duration-fast hover:text-ink disabled:opacity-40 focus-visible:outline-none focus-visible:shadow-focus"
                >
                  ‹
                </button>
                <Slider.Root
                  min={1}
                  max={maxPhase}
                  step={1}
                  value={[phase]}
                  onValueChange={(v) => goToPhase(v[0] ?? 1)}
                  className="relative flex h-6 min-w-[8rem] flex-1 touch-none select-none items-center"
                  aria-label="Phase scrubber"
                >
                  <Slider.Track className="relative h-1.5 grow rounded-full bg-surface">
                    <Slider.Range className="absolute h-full rounded-full bg-accent" />
                  </Slider.Track>
                  <Slider.Thumb className="block h-4 w-4 rounded-full border border-accent bg-canvas focus-visible:outline-none focus-visible:shadow-focus" />
                </Slider.Root>
                <button
                  type="button"
                  onClick={() => goToPhase(phase + 1)}
                  disabled={phase >= maxPhase}
                  aria-label="Next phase"
                  className="rounded-sm border border-border px-2 py-1 text-xs text-ink-muted transition-colors duration-fast hover:text-ink disabled:opacity-40 focus-visible:outline-none focus-visible:shadow-focus"
                >
                  ›
                </button>
                <span className="text-2xs tabular-nums text-ink-muted">
                  phase {phase}/{maxPhase} · <span className="capitalize">{activeName}</span>
                </span>
              </div>

              <p className="text-xs text-ink-muted">{PHASE_BLURB[activeName]}</p>

              <div className="relative min-h-[16rem]">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={phase}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.32, ease: "easeOut" }}
                  >
                    {phaseBody(phase)}
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Text parity for the motion narration (FE-INV-046). */}
              <div className="sr-only" aria-live="polite">
                Phase {phase} of {maxPhase}: {activeName}. {PHASE_BLURB[activeName]}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
