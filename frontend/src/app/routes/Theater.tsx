import { useDecision, useRecentDecisions } from "@/application/decisions";
import { useSound } from "@/aux-ui/sound";
import type { ConsensusPhase } from "@/domain/decision";
import { ContextTape } from "@/ui/components/ContextTape";
import { PhaseRibbon } from "@/ui/components/PhaseRibbon";
import { TierBadge } from "@/ui/components/TierBadge";
import { AGENT_LABEL } from "@/ui/icons/AgentSigil";
import { cn } from "@/ui/lib/cn";
import { shortId } from "@/ui/lib/format";
import { Badge, Button, Card, CardBody } from "@/ui/primitives";
import { AGENT_NAMES, type AgentName } from "@/ui/tokens";
import { ParetoCell } from "@/ui/viz/ParetoCell";
import { ProposalConstellation } from "@/ui/viz/ProposalConstellation";
import { Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

/**
 * Theater — witness consensus. The five protocol phases unfold as a
 * single cinematic process the operator can play, pause and scrub
 * (plan section 5.2).
 */
export default function Theater() {
  const params = useParams<{ decisionId?: string }>();
  const recent = useRecentDecisions(1);
  const decisionId = params.decisionId ?? recent.data?.[0]?.id;
  const { data: decision, isLoading } = useDecision(decisionId);
  const { play: playSound } = useSound();

  const messages = useMemo(() => decision?.contextMessages ?? [], [decision]);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentName | null>(null);

  // Reset the playhead when the decision changes.
  useEffect(() => {
    setStep(0);
    setPlaying(false);
    setSelectedAgent(null);
  }, []);

  // Advance the playhead while playing.
  useEffect(() => {
    if (!playing) return;
    if (step >= messages.length) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => setStep((s) => s + 1), 900);
    return () => clearTimeout(timer);
  }, [playing, step, messages.length]);

  const revealed = messages.slice(0, step);
  const currentPhase: ConsensusPhase = revealed.at(-1)?.phase ?? "collecting";
  const prevPhase: ConsensusPhase = revealed.at(-2)?.phase ?? "collecting";

  // Sound cues on reveal.
  useEffect(() => {
    if (step === 0) return;
    const last = messages[step - 1];
    if (!last) return;
    if (last.phase !== prevPhase) playSound("phase");
    else if ((AGENT_NAMES as readonly string[]).includes(last.source)) playSound("a2a");
  }, [step, messages, prevPhase, playSound]);

  const revealedAgents = useMemo(() => {
    const set = new Set<AgentName>();
    for (const m of revealed) {
      if ((AGENT_NAMES as readonly string[]).includes(m.source)) {
        set.add(m.source as AgentName);
      }
    }
    return set;
  }, [revealed]);

  if (isLoading || !decision) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-hint">
        Loading consensus…
      </div>
    );
  }

  const atEnd = step >= messages.length;
  const selectedProposal = decision.proposals.find((p) => p.agentName === selectedAgent);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-line-faint bg-paper px-4 py-2.5">
        <h1 className="font-display text-sm font-semibold text-ink-primary">Theater</h1>
        <span className="font-mono text-2xs text-ink-hint">{shortId(decision.id)}</span>
        <TierBadge tier={decision.tier} showLatency />
        {decision.escalated && (
          <Badge tone="warn" dot>
            Escalated
          </Badge>
        )}
        <div className="ml-auto flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setStep(0);
              setPlaying(false);
            }}
            aria-label="Restart"
          >
            <RotateCcw size={14} aria-hidden="true" />
          </Button>
          <Button
            size="sm"
            variant="signal"
            onClick={() => {
              if (atEnd) setStep(0);
              setPlaying((p) => !p);
            }}
          >
            {playing ? (
              <Pause size={14} aria-hidden="true" />
            ) : (
              <Play size={14} aria-hidden="true" />
            )}
            {playing ? "Pause" : atEnd ? "Replay" : "Play"}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setStep((s) => Math.min(messages.length, s + 1))}
            disabled={atEnd}
            aria-label="Step forward"
          >
            <SkipForward size={14} aria-hidden="true" />
          </Button>
        </div>
      </header>

      <PhaseRibbon
        current={currentPhase}
        budgetProgress={messages.length ? step / messages.length : 0}
        className="border-b border-line-faint bg-paper"
      />

      {/* Stage */}
      <div className="flex min-h-0 flex-1">
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6">
          <ProposalConstellation
            proposals={decision.proposals}
            revealed={revealedAgents}
            debating={currentPhase === "debating"}
            selectedAgent={selectedAgent}
            onSelectAgent={(a) => setSelectedAgent((cur) => (cur === a ? null : a))}
          />
          {selectedProposal && (
            <Card accent="var(--color-sig-think)" className="w-full max-w-xl">
              <CardBody className="pt-3">
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="font-display text-xs font-semibold text-ink-primary">
                    {AGENT_LABEL[selectedProposal.agentName]}
                  </span>
                  <span className="font-mono text-2xs text-ink-hint">
                    {selectedProposal.action.kind}
                  </span>
                </div>
                <ul className="flex flex-col gap-0.5">
                  {selectedProposal.justificationTrace.map((line) => (
                    <li key={line} className="text-2xs text-ink-secondary">
                      • {line}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          )}
        </div>

        {/* Right rail */}
        <aside className="flex w-[360px] shrink-0 flex-col border-l border-line-faint">
          <div className="p-3">
            <ParetoCell front={decision.paretoFront} className={cn("h-52")} />
          </div>
          <ContextTape
            messages={revealed}
            className="min-h-0 flex-1 border-t border-line-faint"
          />
        </aside>
      </div>
    </div>
  );
}
