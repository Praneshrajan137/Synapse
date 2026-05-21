import {
  type ParetoWeights,
  type TierThresholds,
  useSteeringStore,
} from "@/app/store/steeringStore";
import { useUIStore } from "@/app/store/uiStore";
import { LOCALES, LOCALE_LABEL } from "@/i18n/catalog";
import { useT } from "@/i18n/useT";
import { cn } from "@/ui/lib/cn";
import { Button, Card, CardBody, CardHeader, CardTitle, Switch } from "@/ui/primitives";
import { densityModes } from "@/ui/tokens";
import { Clapperboard, RotateCcw, Sliders } from "lucide-react";
import { useId } from "react";

/**
 * Steering — operator-tunable governance (plan section 6.7).
 *
 * Pareto objective weights, per-tier confidence thresholds, and the
 * presentation preferences. Steering is governed: in production every
 * change is audit-logged to synapse.steering.config.
 */

const WEIGHT_LABELS: Record<keyof ParetoWeights, string> = {
  cost: "Cost",
  time: "Time",
  sustainability: "Sustainability",
  fairness: "Fairness",
};

const THRESHOLD_LABELS: Record<keyof TierThresholds, string> = {
  tier_2: "Tier 2 escalation",
  tier_3: "Tier 3 escalation",
  tier_4: "Tier 4 escalation",
};

function Row({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="flex justify-between text-xs text-ink-secondary">
        <span>{label}</span>
        <span className="tnum font-mono text-ink-primary">{value.toFixed(2)}</span>
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="accent-sig-live"
      />
    </div>
  );
}

export default function Steering() {
  const ids = useId();
  const t = useT();
  const steering = useSteeringStore();
  const ui = useUIStore();

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 overflow-y-auto p-6">
      <h1 className="flex items-center gap-2 font-display text-lg font-semibold text-ink-primary">
        <Sliders size={18} className="text-sig-live" aria-hidden="true" />
        Steering
      </h1>

      <Card tone="elevated">
        <CardHeader>
          <CardTitle>Pareto objective weights</CardTitle>
          <span className="text-2xs text-ink-hint">arbitration preference</span>
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          {(Object.keys(steering.paretoWeights) as (keyof ParetoWeights)[]).map((key) => (
            <Row
              key={key}
              id={`${ids}-w-${key}`}
              label={WEIGHT_LABELS[key]}
              value={steering.paretoWeights[key]}
              onChange={(v) => steering.setParetoWeight(key, v)}
            />
          ))}
        </CardBody>
      </Card>

      <Card tone="elevated">
        <CardHeader>
          <CardTitle>Confidence thresholds</CardTitle>
          <span className="text-2xs text-ink-hint">HITL escalation gate</span>
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          {(Object.keys(steering.tierThresholds) as (keyof TierThresholds)[]).map(
            (tier) => (
              <Row
                key={tier}
                id={`${ids}-t-${tier}`}
                label={THRESHOLD_LABELS[tier]}
                value={steering.tierThresholds[tier]}
                onChange={(v) => steering.setTierThreshold(tier, v)}
              />
            ),
          )}
        </CardBody>
      </Card>

      <Card tone="elevated">
        <CardHeader>
          <CardTitle>Presentation</CardTitle>
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-ink-secondary">Sound cues</span>
            <Switch
              aria-label="Sound cues"
              checked={ui.soundEnabled}
              onCheckedChange={ui.setSoundEnabled}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-ink-secondary">Information density</span>
            <div className="flex gap-1">
              {densityModes.map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => {
                    if (ui.density !== mode) ui.cycleDensity();
                  }}
                  aria-pressed={ui.density === mode}
                  className={cn(
                    "rounded-xs px-2 py-0.5 font-mono text-2xs transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live",
                    ui.density === mode
                      ? "bg-elevated text-ink-primary"
                      : "text-ink-hint hover:text-ink-secondary",
                  )}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <label htmlFor={`${ids}-locale`} className="text-xs text-ink-secondary">
              {t("common.language")}
            </label>
            <select
              id={`${ids}-locale`}
              value={ui.locale}
              onChange={(e) => ui.setLocale(e.target.value as (typeof LOCALES)[number])}
              className="rounded-sm border border-line-strong bg-void px-2 py-1 text-xs text-ink-primary focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live"
            >
              {LOCALES.map((locale) => (
                <option key={locale} value={locale}>
                  {LOCALE_LABEL[locale]}
                </option>
              ))}
            </select>
          </div>
        </CardBody>
      </Card>

      <Card tone="elevated">
        <CardHeader>
          <CardTitle>Demo</CardTitle>
        </CardHeader>
        <CardBody className="flex items-center justify-between gap-4">
          <p className="text-2xs leading-relaxed text-ink-hint">
            Run the cinematic five-segment SYNAPSE narrative across the surfaces.
          </p>
          <Button variant="signal" onClick={() => ui.setDemoMode(true)}>
            <Clapperboard size={14} aria-hidden="true" />
            Start demo
          </Button>
        </CardBody>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-2xs text-ink-hint">
          Steering changes are audit-logged to synapse.steering.config.
        </p>
        <Button variant="ghost" size="sm" onClick={steering.reset}>
          <RotateCcw size={13} aria-hidden="true" />
          Reset to defaults
        </Button>
      </div>
    </div>
  );
}
