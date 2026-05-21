import { useTwinTopology, useWhatIf } from "@/application/twin";
import {
  type KpiDistribution,
  SCENARIO_LABEL,
  SHOCK_SCENARIOS,
  type ShockParams,
  type ShockScenario,
} from "@/domain/twin";
import { cn } from "@/ui/lib/cn";
import { Button, Card, CardBody, CardHeader, CardTitle } from "@/ui/primitives";
import { signal } from "@/ui/tokens";
import { SupplyGraph } from "@/ui/viz/SupplyGraph";
import { Boxes, Play } from "lucide-react";
import { useId, useState } from "react";

/**
 * Twin — the counterfactual canvas (plan section 5.5). The supply
 * network plus a 1000-scenario Monte Carlo what-if over four shock
 * parameters.
 */

interface ShockSlider {
  key: keyof ShockParams;
  label: string;
  min: number;
  max: number;
  step: number;
}

const SLIDERS: readonly ShockSlider[] = [
  { key: "demand", label: "Demand ×", min: 0.5, max: 3, step: 0.1 },
  { key: "leadTime", label: "Lead time ×", min: 1, max: 3, step: 0.1 },
  { key: "failureRate", label: "Failure rate", min: 0, max: 1, step: 0.05 },
  { key: "spoilage", label: "Spoilage rate", min: 0, max: 1, step: 0.05 },
];

const DEFAULT_PARAMS: ShockParams = {
  demand: 1.6,
  leadTime: 1.3,
  failureRate: 0.2,
  spoilage: 0.15,
};

function DistributionRow({ dist }: { dist: KpiDistribution }) {
  const lo = Math.min(dist.p5, dist.baseline);
  const hi = Math.max(dist.p95, dist.baseline);
  const span = hi - lo || 1;
  const pct = (v: number) => ((v - lo) / span) * 100;
  return (
    <li className="flex flex-col gap-1 border-b border-line-faint/60 pb-2 last:border-0">
      <div className="flex justify-between text-2xs">
        <span className="text-ink-secondary">{dist.label}</span>
        <span className="tnum font-mono text-ink-primary">
          {dist.p50}
          {dist.unit} <span className="text-ink-hint">p50</span>
        </span>
      </div>
      <div className="relative h-2.5 rounded-full bg-membrane">
        <div
          className="absolute h-full rounded-full"
          style={{
            left: `${pct(dist.p5)}%`,
            width: `${pct(dist.p95) - pct(dist.p5)}%`,
            backgroundColor: `color-mix(in oklab, ${signal.live} 40%, transparent)`,
          }}
        />
        <div
          className="absolute top-[-1px] h-[calc(100%+2px)] w-0.5 bg-sig-live"
          style={{ left: `${pct(dist.p50)}%` }}
        />
        <div
          className="absolute top-[-1px] h-[calc(100%+2px)] w-0.5 bg-ink-hint"
          style={{ left: `${pct(dist.baseline)}%` }}
        />
      </div>
      <div className="flex justify-between text-2xs text-ink-hint">
        <span className="tnum">p5 {dist.p5}</span>
        <span className="tnum">baseline {dist.baseline}</span>
        <span className="tnum">p95 {dist.p95}</span>
      </div>
    </li>
  );
}

export default function Twin() {
  const sliderId = useId();
  const topology = useTwinTopology();
  const whatIf = useWhatIf();
  const [scenario, setScenario] = useState<ShockScenario>("demand_spike");
  const [params, setParams] = useState<ShockParams>(DEFAULT_PARAMS);

  return (
    <div className="flex h-full">
      <section className="flex min-w-0 flex-1 flex-col p-4">
        <h1 className="mb-3 flex items-center gap-2 font-display text-sm font-semibold text-ink-primary">
          <Boxes size={16} className="text-sig-live" aria-hidden="true" />
          Digital Twin
        </h1>
        {topology.data ? (
          <SupplyGraph topology={topology.data} className="min-h-0 flex-1" />
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-ink-hint">
            Loading supply network…
          </div>
        )}
      </section>

      <aside className="flex w-[380px] shrink-0 flex-col gap-4 overflow-y-auto border-l border-line-faint p-4">
        <Card tone="elevated">
          <CardHeader>
            <CardTitle>Scenario</CardTitle>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-1.5">
              {SHOCK_SCENARIOS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setScenario(s)}
                  aria-pressed={scenario === s}
                  className={cn(
                    "rounded-md border px-2 py-1.5 text-2xs transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live",
                    scenario === s
                      ? "border-sig-live/50 bg-sig-live/12 text-sig-live"
                      : "border-line-faint text-ink-secondary hover:border-line-strong",
                  )}
                >
                  {SCENARIO_LABEL[s]}
                </button>
              ))}
            </div>

            {SLIDERS.map((slider) => (
              <div key={slider.key} className="flex flex-col gap-1">
                <label
                  htmlFor={`${sliderId}-${slider.key}`}
                  className="flex justify-between text-2xs text-ink-secondary"
                >
                  <span>{slider.label}</span>
                  <span className="tnum font-mono text-ink-primary">
                    {params[slider.key].toFixed(2)}
                  </span>
                </label>
                <input
                  id={`${sliderId}-${slider.key}`}
                  type="range"
                  min={slider.min}
                  max={slider.max}
                  step={slider.step}
                  value={params[slider.key]}
                  onChange={(e) =>
                    setParams((p) => ({ ...p, [slider.key]: Number(e.target.value) }))
                  }
                  className="accent-sig-live"
                />
              </div>
            ))}

            <Button
              variant="signal"
              onClick={() => whatIf.mutate({ scenario, params })}
              disabled={whatIf.isPending}
            >
              <Play size={13} aria-hidden="true" />
              {whatIf.isPending ? "Simulating…" : "Run what-if · 1000 scenarios"}
            </Button>
          </CardBody>
        </Card>

        {whatIf.data && (
          <Card tone="elevated">
            <CardHeader>
              <CardTitle>Monte Carlo result</CardTitle>
              <span className="text-2xs text-ink-hint">
                {whatIf.data.scenarioCount} scenarios
              </span>
            </CardHeader>
            <CardBody>
              <ul className="flex flex-col gap-2">
                {whatIf.data.distributions.map((dist) => (
                  <DistributionRow key={dist.id} dist={dist} />
                ))}
              </ul>
            </CardBody>
          </Card>
        )}

        {whatIf.isIdle && (
          <p className="px-1 text-2xs leading-relaxed text-ink-hint">
            Choose a scenario, tune the four shock parameters, and run the twin to see the
            predicted KPI distribution against the live baseline.
          </p>
        )}
      </aside>
    </div>
  );
}
