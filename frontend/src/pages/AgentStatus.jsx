import React from "react";
import { AGENTS } from "../theme/agents";

// Showcase of the 8 agent identities — nominal data on the OKLCH Hue axis.
// Each card is keyed to one earned hue; the glyph and label are the
// colour-independent channels (INV-CLR-011).
const STATS = [
  { label: "p50 Latency", value: "-- ms" },
  { label: "p99 Latency", value: "-- ms" },
  { label: "Decisions / min", value: "--" },
];

function PageHeader({ title, subtitle }) {
  return (
    <header className="mb-5">
      <h1 className="text-xl font-bold tracking-tight text-text-primary">{title}</h1>
      {subtitle && <p className="mt-0.5 text-sm text-text-tertiary">{subtitle}</p>}
    </header>
  );
}

function AgentCard({ agent }) {
  const accent = `var(--color-agent-${agent.key})`;
  return (
    <article
      className="panel group p-5 transition-shadow hover:[box-shadow:0_4px_30px_-10px_var(--accent)]"
      style={{ "--accent": accent, borderLeft: `3px solid ${accent}` }}
    >
      <header className="flex items-center gap-3">
        <span
          className="grid h-10 w-10 shrink-0 place-items-center rounded-lg text-lg font-bold accent-tint"
          style={{ color: accent }}
          aria-hidden="true"
        >
          {agent.glyph}
        </span>
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-text-primary">{agent.label}</h2>
          <p className="truncate text-[11px] text-text-tertiary">{agent.role}</p>
        </div>
      </header>

      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs text-text-tertiary">Status</span>
        <span className="flex items-center gap-1.5 text-xs font-semibold text-state-success">
          <span className="h-2 w-2 rounded-full bg-state-success" aria-hidden="true" />
          Healthy
        </span>
      </div>
      <dl className="mt-2 space-y-1.5">
        {STATS.map((s) => (
          <div key={s.label} className="flex items-center justify-between text-xs">
            <dt className="text-text-tertiary">{s.label}</dt>
            <dd className="font-mono text-text-secondary">{s.value}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

export default function AgentStatus() {
  return (
    <div className="mx-auto max-w-[1400px] animate-fade-in">
      <PageHeader
        title="Agent Status"
        subtitle="8 specialised agents — each with an earned identity hue"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {AGENTS.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>
    </div>
  );
}
