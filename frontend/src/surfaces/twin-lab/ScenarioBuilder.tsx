import { Button } from "@ds/primitives";
import { type FormEvent, useState } from "react";

interface ScenarioBuilderProps {
  readonly pending?: boolean;
  readonly onRun: (req: ScenarioRequest) => void;
}

export interface ScenarioRequest {
  readonly name: string;
  readonly demand_multiplier: number;
  readonly lead_time_multiplier: number;
  readonly failure_rate_multiplier: number;
  readonly spoilage_rate_multiplier: number;
  readonly n_scenarios: number;
  readonly duration_hours: number;
}

const PRESETS: Record<string, ScenarioRequest> = {
  warehouse_offline: {
    name: "warehouse_offline",
    demand_multiplier: 1.0,
    lead_time_multiplier: 1.8,
    failure_rate_multiplier: 2.5,
    spoilage_rate_multiplier: 1.4,
    n_scenarios: 1000,
    duration_hours: 4,
  },
  monsoon_flood: {
    name: "monsoon_flood",
    demand_multiplier: 1.3,
    lead_time_multiplier: 2.0,
    failure_rate_multiplier: 1.8,
    spoilage_rate_multiplier: 1.6,
    n_scenarios: 1000,
    duration_hours: 4,
  },
  supplier_default: {
    name: "supplier_default",
    demand_multiplier: 0.9,
    lead_time_multiplier: 3.0,
    failure_rate_multiplier: 1.2,
    spoilage_rate_multiplier: 1.1,
    n_scenarios: 1000,
    duration_hours: 6,
  },
  demand_spike: {
    name: "demand_spike",
    demand_multiplier: 3.5,
    lead_time_multiplier: 1.1,
    failure_rate_multiplier: 1.0,
    spoilage_rate_multiplier: 1.0,
    n_scenarios: 1000,
    duration_hours: 2,
  },
};

export function ScenarioBuilder({ pending, onRun }: ScenarioBuilderProps) {
  const [request, setRequest] = useState<ScenarioRequest>(PRESETS.warehouse_offline!);

  function applyPreset(name: keyof typeof PRESETS) {
    setRequest(PRESETS[name]!);
  }

  function update<K extends keyof ScenarioRequest>(key: K, value: ScenarioRequest[K]) {
    setRequest((s) => ({ ...s, [key]: value }));
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    onRun(request);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="syn-card-raised space-y-3 p-4"
      aria-label="Scenario builder"
    >
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Scenario</h2>
      </header>

      <div className="flex flex-wrap gap-2">
        {Object.keys(PRESETS).map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => applyPreset(id as keyof typeof PRESETS)}
            className="rounded bg-surface-raised px-2 py-0.5 text-2xs font-medium uppercase tracking-wide text-ink-muted hover:text-ink"
          >
            {id.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      <Slider
        label="Demand ×"
        value={request.demand_multiplier}
        min={0.1}
        max={5}
        step={0.1}
        onChange={(v) => update("demand_multiplier", v)}
      />
      <Slider
        label="Lead time ×"
        value={request.lead_time_multiplier}
        min={0.5}
        max={5}
        step={0.1}
        onChange={(v) => update("lead_time_multiplier", v)}
      />
      <Slider
        label="Failure ×"
        value={request.failure_rate_multiplier}
        min={0.5}
        max={5}
        step={0.1}
        onChange={(v) => update("failure_rate_multiplier", v)}
      />
      <Slider
        label="Spoilage ×"
        value={request.spoilage_rate_multiplier}
        min={0.5}
        max={5}
        step={0.1}
        onChange={(v) => update("spoilage_rate_multiplier", v)}
      />

      <div className="grid grid-cols-2 gap-2 text-2xs">
        <label className="block">
          <span className="block uppercase tracking-wide text-ink-muted">n scenarios</span>
          <input
            type="number"
            min={100}
            max={5000}
            step={100}
            value={request.n_scenarios}
            onChange={(e) => update("n_scenarios", Number(e.target.value))}
            className="mt-1 h-8 w-full rounded-md border border-border bg-surface px-2 text-sm text-ink"
          />
        </label>
        <label className="block">
          <span className="block uppercase tracking-wide text-ink-muted">duration h</span>
          <input
            type="number"
            min={1}
            max={24}
            step={1}
            value={request.duration_hours}
            onChange={(e) => update("duration_hours", Number(e.target.value))}
            className="mt-1 h-8 w-full rounded-md border border-border bg-surface px-2 text-sm text-ink"
          />
        </label>
      </div>

      <Button type="submit" variant="primary" size="md" disabled={pending} className="w-full">
        {pending ? "Running Monte Carlo…" : "Run simulation"}
      </Button>
      <p className="text-2xs text-ink-subtle">
        INV-TW-004: 1000 scenarios complete within 10s on the reference twin.
      </p>
    </form>
  );
}

interface SliderProps {
  readonly label: string;
  readonly value: number;
  readonly min: number;
  readonly max: number;
  readonly step: number;
  readonly onChange: (v: number) => void;
}

function Slider({ label, value, min, max, step, onChange }: SliderProps) {
  return (
    <label className="block text-2xs">
      <span className="flex items-center justify-between uppercase tracking-wide text-ink-muted">
        <span>{label}</span>
        <span className="font-mono text-ink">{value.toFixed(2)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full accent-accent"
      />
    </label>
  );
}
