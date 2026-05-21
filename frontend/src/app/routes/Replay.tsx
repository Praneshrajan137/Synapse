import { useAuditRow, useAuditTimeline } from "@/application/audit";
import type { ConsensusPhase } from "@/domain/decision";
import { AuditRowFooter } from "@/ui/components/AuditRowFooter";
import { ContextTape } from "@/ui/components/ContextTape";
import { OutcomePanel } from "@/ui/components/OutcomePanel";
import { PhaseRibbon } from "@/ui/components/PhaseRibbon";
import { ScrubberTimeline } from "@/ui/components/ScrubberTimeline";
import { TierBadge } from "@/ui/components/TierBadge";
import { shortId } from "@/ui/lib/format";
import { Badge } from "@/ui/primitives";
import { AGENT_NAMES, type AgentName } from "@/ui/tokens";
import { ParetoCell } from "@/ui/viz/ParetoCell";
import { ProposalConstellation } from "@/ui/viz/ProposalConstellation";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

/**
 * Replay — perfect-fidelity time travel through any past decision
 * (plan section 5.4). The scrubber position is held in the URL
 * (?step=N) so a shared link reproduces an exact frame (tenet T-1).
 */
export default function Replay() {
  const params = useParams<{ decisionId?: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const timeline = useAuditTimeline(48);
  const decisionId = params.decisionId ?? timeline.data?.[0]?.decisionId;
  const audit = useAuditRow(decisionId ? `audit-${decisionId}` : undefined);

  const messages = useMemo(
    () => audit.data?.decision.contextMessages ?? [],
    [audit.data],
  );
  const stepParam = Number(searchParams.get("step") ?? "0");
  const [step, setStep] = useState(Number.isFinite(stepParam) ? stepParam : 0);

  // Clamp the step to the loaded decision and keep the URL in sync.
  // Both writes are guarded so the effect settles instead of looping.
  useEffect(() => {
    const clamped = Math.max(0, Math.min(messages.length, step));
    if (clamped !== step) {
      setStep(clamped);
      return;
    }
    if (searchParams.get("step") !== String(clamped)) {
      const next = new URLSearchParams(searchParams);
      next.set("step", String(clamped));
      setSearchParams(next, { replace: true });
    }
  }, [step, messages.length, searchParams, setSearchParams]);

  if (timeline.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-hint">
        Loading audit timeline…
      </div>
    );
  }

  const decision = audit.data?.decision;
  const revealed = messages.slice(0, step);
  const currentPhase: ConsensusPhase = revealed.at(-1)?.phase ?? "collecting";
  const revealedAgents = new Set<AgentName>(
    revealed
      .map((m) => m.source)
      .filter((s): s is AgentName => (AGENT_NAMES as readonly string[]).includes(s)),
  );

  return (
    <div className="flex h-full flex-col">
      <ScrubberTimeline
        entries={timeline.data ?? []}
        selectedDecisionId={decisionId}
        onSelect={(id) => navigate(`/replay/${id}`)}
        className="border-b border-line-faint"
      />

      {!decision ? (
        <div className="flex flex-1 items-center justify-center text-sm text-ink-hint">
          Select a decision from the timeline to replay it.
        </div>
      ) : (
        <>
          <div className="flex min-h-0 flex-1">
            {/* Replica */}
            <div className="flex min-w-0 flex-1 flex-col">
              <header className="flex items-center gap-3 border-b border-line-faint bg-paper px-4 py-2.5">
                <h1 className="font-display text-sm font-semibold text-ink-primary">
                  Replay
                </h1>
                <span className="font-mono text-2xs text-ink-hint">
                  {shortId(decision.id)}
                </span>
                <TierBadge tier={decision.tier} showLatency />
                {decision.escalated && (
                  <Badge tone="warn" dot>
                    Escalated
                  </Badge>
                )}
                {decision.humanOverride && (
                  <Badge tone="trace" dot>
                    Human override
                  </Badge>
                )}
                <label className="ml-auto flex items-center gap-2 text-2xs text-ink-hint">
                  <span>Scrub</span>
                  <input
                    type="range"
                    min={0}
                    max={messages.length}
                    value={step}
                    onChange={(e) => setStep(Number(e.target.value))}
                    aria-label="Scrub consensus replay"
                    className="w-40 accent-sig-live"
                  />
                  <span className="tnum w-12 font-mono">
                    {step}/{messages.length}
                  </span>
                </label>
              </header>

              <PhaseRibbon
                current={currentPhase}
                budgetProgress={messages.length ? step / messages.length : 0}
                className="border-b border-line-faint bg-paper"
              />

              <div className="flex flex-1 items-center justify-center p-6">
                <ProposalConstellation
                  proposals={decision.proposals}
                  revealed={revealedAgents}
                  debating={currentPhase === "debating"}
                />
              </div>
            </div>

            {/* Right rail */}
            <aside className="flex w-[360px] shrink-0 flex-col border-l border-line-faint">
              <div className="flex flex-col gap-3 p-3">
                <ParetoCell front={decision.paretoFront} className="h-44" />
                <OutcomePanel outcome={decision.outcome} />
              </div>
              <ContextTape
                messages={revealed}
                follow={false}
                className="min-h-0 flex-1 border-t border-line-faint"
              />
            </aside>
          </div>

          {audit.data && (
            <AuditRowFooter audit={audit.data} className="border-t border-line-faint" />
          )}
        </>
      )}
    </div>
  );
}
