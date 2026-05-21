import React from "react";
import KPITicker from "../components/KPITicker";

const TIERS = [
  { n: 1, latency: "< 100 ms", note: "RL-only reflex" },
  { n: 2, latency: "< 500 ms", note: "phi3:mini" },
  { n: 3, latency: "2 – 15 s", note: "deepseek-r1" },
  { n: 4, latency: "15 – 120 s", note: "Monte Carlo + LLM" },
];

function PageHeader({ title, subtitle }) {
  return (
    <header className="mb-5">
      <h1 className="text-xl font-bold tracking-tight text-text-primary">{title}</h1>
      {subtitle && <p className="mt-0.5 text-sm text-text-tertiary">{subtitle}</p>}
    </header>
  );
}

export default function Dashboard() {
  return (
    <div className="mx-auto max-w-[1400px] animate-fade-in">
      <PageHeader title="Operations Dashboard" subtitle="Live quick-commerce supply network — Bengaluru" />
      <KPITicker data={{}} />

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="panel flex min-h-[460px] items-center justify-center p-6 text-center text-sm text-text-tertiary">
          Deck.gl + MapLibre GL — 25 dark stores, order arcs, rider positions, demand heatmap
        </div>

        <aside className="panel p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Decision Tier Ladder
          </h2>
          <p className="mt-1 text-xs text-text-tertiary">
            Tier is ordinal — encoded as lightness (I-8). Lighter = faster reflex, deeper = longer deliberation.
          </p>
          <div className="gradient-tier mt-3 h-2.5 rounded-full" aria-hidden="true" />
          <ul className="mt-4 space-y-2.5">
            {TIERS.map(({ n, latency, note }) => (
              <li key={n} className="flex items-center gap-3">
                <span
                  className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-xs font-bold text-text-inverse"
                  style={{ background: `var(--color-tier-${n})` }}
                >
                  T{n}
                </span>
                <div className="flex-1">
                  <div className="text-[13px] font-medium text-text-primary">
                    Tier {n} · {note}
                  </div>
                  <div className="font-mono text-[11px] text-text-tertiary">{latency}</div>
                </div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
