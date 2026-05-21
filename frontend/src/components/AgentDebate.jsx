import React from "react";
import ConfidenceGauge from "./ConfidenceGauge";
import { agentOf } from "../theme/agents";

// Agent proposals — each card wears its agent's identity colour as a left
// rail + glyph chip + a faint identity tint. Colour is one of three channels
// (chip glyph and name label are the others), per INV-CLR-011.
function ProposalCard({ proposal }) {
  const agent = agentOf(proposal.agent_name);
  const accent = agent ? `var(--color-agent-${agent.key})` : "var(--color-state-neutral)";
  return (
    <article
      className="panel relative overflow-hidden p-4"
      style={{ "--accent": accent }}
    >
      <span className="absolute inset-y-0 left-0 w-1" style={{ background: accent }} aria-hidden="true" />
      <header className="flex items-center gap-2.5">
        <span
          className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-base font-bold accent-tint"
          style={{ color: accent }}
          aria-hidden="true"
        >
          {agent?.glyph ?? "•"}
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-text-primary">
            {agent?.label ?? proposal.agent_name}
          </div>
          <div className="truncate text-[11px] text-text-tertiary">{agent?.role ?? "Agent"}</div>
        </div>
      </header>
      <div className="mt-3 flex items-center gap-3">
        <ConfidenceGauge value={proposal.confidence ?? 0} size={78} label={false} />
        <dl className="text-xs">
          <dt className="text-text-tertiary">Utility</dt>
          <dd className="font-mono text-base font-semibold text-text-primary">
            {proposal.utility_score?.toFixed(3) ?? "--"}
          </dd>
        </dl>
      </div>
      <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-text-secondary">
        {proposal.justification_trace?.[0] ?? "No justification trace."}
      </p>
    </article>
  );
}

export default function AgentDebate({ proposals = [], debateRounds = [] }) {
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
        Agent Proposals
      </h3>
      {proposals.length === 0 ? (
        <p className="panel p-6 text-sm text-text-tertiary">No proposals in this consensus round.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {proposals.map((p, i) => (
            <ProposalCard key={p.agent_name ?? i} proposal={p} />
          ))}
        </div>
      )}

      {debateRounds.length > 0 && (
        <div className="mt-6">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Debate Rounds
          </h3>
          <ol className="space-y-2">
            {debateRounds.map((round, i) => (
              <li key={i} className="panel p-3">
                <span className="text-xs font-semibold text-brand-base">
                  Round {round.round_number}
                </span>
                <p className="mt-1 text-[13px] text-text-secondary">
                  {round.llm_analysis ?? "No analysis."}
                </p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
