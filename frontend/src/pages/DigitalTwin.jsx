import React, { useState } from "react";

const SCENARIOS = [
  { value: "demand_spike", label: "Demand Spike" },
  { value: "supplier_failure", label: "Supplier Failure" },
  { value: "route_disruption", label: "Route Disruption" },
  { value: "weather_event", label: "Weather Event" },
];

function PageHeader({ title, subtitle }) {
  return (
    <header className="mb-5">
      <h1 className="text-xl font-bold tracking-tight text-text-primary">{title}</h1>
      {subtitle && <p className="mt-0.5 text-sm text-text-tertiary">{subtitle}</p>}
    </header>
  );
}

export default function DigitalTwin() {
  const [scenario, setScenario] = useState("demand_spike");
  const [running, setRunning] = useState(false);

  return (
    <div className="mx-auto max-w-[1400px] animate-fade-in">
      <PageHeader
        title="Digital Twin"
        subtitle="What-if simulation against the live supply-network model (I-12)"
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <div className="panel flex min-h-[440px] items-center justify-center p-6 text-center text-sm text-text-tertiary">
          3D Supply Network — react-force-graph-3d (nodes coloured by owning agent)
        </div>

        <aside className="panel h-fit p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
            What-If Scenario
          </h2>

          <label htmlFor="scenario" className="mt-4 block text-xs font-medium text-text-tertiary">
            Disruption Type
          </label>
          <select
            id="scenario"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            className="mt-1.5 w-full rounded-md border border-border-subtle bg-surface-raised px-3 py-2 text-sm text-text-primary focus-visible:border-brand-base focus-visible:outline-none"
          >
            {SCENARIOS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => setRunning(true)}
            disabled={running}
            className="mt-4 w-full rounded-md px-4 py-2.5 text-sm font-semibold text-brand-fg transition-transform hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
            style={{ background: running ? "var(--color-surface-overlay)" : "var(--color-brand-base)" }}
          >
            {running ? "Running Monte Carlo…" : "Run Simulation"}
          </button>
          <p className="mt-3 text-[11px] leading-relaxed text-text-tertiary">
            Simulation runs as a Tier 4 decision — Monte Carlo rollouts validated against the
            twin's KL-divergence bound.
          </p>
        </aside>
      </div>
    </div>
  );
}
