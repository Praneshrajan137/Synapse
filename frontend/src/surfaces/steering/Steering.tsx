import {
  AGENT_NAMES,
  type AgentName,
  ProposalConstellation,
  type ProposalLike,
} from "@ds/compounds/ProposalConstellation";
import { Button, Card, CardBody, CardHeader, CardTitle } from "@ds/primitives";
import { cn } from "@lib/cn";
import {
  DEFAULT_PARETO_WEIGHTS,
  DEFAULT_TIER_THRESHOLDS,
  type ParetoWeights,
  useSteeringStore,
} from "@state/steering.store";
import { RotateCcw, Sliders } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

/**
 * Steering — operator-tunable governance surface.
 *
 * Renders two slider banks (Pareto weights, tier thresholds) plus a live
 * preview that uses the ProposalConstellation viz to visualise *how the
 * current weights would arbitrate* a synthetic 8-agent decision. The
 * preview's "selected" agent updates as the operator moves the sliders,
 * giving immediate causal feedback (T-5 / FE-INV-033).
 *
 * Persistence: state lives in useSteeringStore (Zustand + persist →
 * localStorage["synapse.steering"]). In production the same change set
 * is also forwarded to `synapse.steering.config` via the audit
 * pipeline (out of scope of this PR; covered by FE-INV-021's row-first
 * commit pattern).
 *
 * Access: gated to `minRole="ops"` by the router.
 */

/**
 * Synthetic preview proposals — fixed utility profiles per agent so the
 * preview is deterministic across renders (FE-INV-009). Each agent has
 * a per-objective utility vector; the "winner" is computed by dot
 * product with the current Pareto weights.
 */
const PREVIEW_UTILITY: Record<
  AgentName,
  { cost: number; time: number; sustainability: number; fairness: number; confidence: number }
> = {
  demand_prophet: { cost: 0.62, time: 0.58, sustainability: 0.55, fairness: 0.6, confidence: 0.82 },
  routing_navigator: {
    cost: 0.78,
    time: 0.86,
    sustainability: 0.48,
    fairness: 0.5,
    confidence: 0.9,
  },
  inventory_sentinel: {
    cost: 0.7,
    time: 0.62,
    sustainability: 0.55,
    fairness: 0.72,
    confidence: 0.84,
  },
  freshness_guardian: {
    cost: 0.55,
    time: 0.6,
    sustainability: 0.92,
    fairness: 0.78,
    confidence: 0.78,
  },
  pricing_oracle: { cost: 0.88, time: 0.7, sustainability: 0.45, fairness: 0.4, confidence: 0.91 },
  disruption_shield: {
    cost: 0.5,
    time: 0.75,
    sustainability: 0.5,
    fairness: 0.55,
    confidence: 0.7,
  },
  supplier_trust: { cost: 0.66, time: 0.55, sustainability: 0.7, fairness: 0.85, confidence: 0.79 },
  sustainability_agent: {
    cost: 0.4,
    time: 0.5,
    sustainability: 0.95,
    fairness: 0.82,
    confidence: 0.76,
  },
};

function dot(weights: ParetoWeights, utility: (typeof PREVIEW_UTILITY)[AgentName]): number {
  return (
    weights.cost * utility.cost +
    weights.time * utility.time +
    weights.sustainability * utility.sustainability +
    weights.fairness * utility.fairness
  );
}

interface SliderRowProps {
  readonly id: string;
  readonly label: string;
  readonly value: number;
  readonly onChange: (value: number) => void;
  readonly suffix?: string;
}

function SliderRow({ id, label, value, onChange, suffix }: SliderRowProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="flex justify-between text-xs text-ink-muted">
        <span>{label}</span>
        <span className="font-mono tabular-nums text-ink">
          {value.toFixed(2)}
          {suffix ?? ""}
        </span>
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="accent-accent"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={value}
      />
    </div>
  );
}

export function Steering() {
  const ids = useId();
  const { t } = useTranslation("steering");
  const paretoWeights = useSteeringStore((s) => s.paretoWeights);
  const tierThresholds = useSteeringStore((s) => s.tierThresholds);
  const setParetoWeight = useSteeringStore((s) => s.setParetoWeight);
  const setTierThreshold = useSteeringStore((s) => s.setTierThreshold);
  const reset = useSteeringStore((s) => s.reset);
  const [previewSelected, setPreviewSelected] = useState<AgentName | null>(null);

  // Live preview: 8 proposals weighted by current Pareto config.
  const previewProposals = useMemo<ReadonlyArray<ProposalLike>>(
    () =>
      AGENT_NAMES.map((agent) => ({
        agent_name: agent,
        utility_score: dot(paretoWeights, PREVIEW_UTILITY[agent]),
        confidence: PREVIEW_UTILITY[agent].confidence,
      })),
    [paretoWeights],
  );

  // The "winner" is the agent whose weighted utility is highest. Shown
  // with the constellation's selected-ring so operators see immediate
  // causal feedback as sliders move.
  const previewWinner = useMemo<AgentName>(() => {
    let best: AgentName = AGENT_NAMES[0];
    let bestScore = Number.NEGATIVE_INFINITY;
    for (const agent of AGENT_NAMES) {
      const s = dot(paretoWeights, PREVIEW_UTILITY[agent]);
      if (s > bestScore) {
        best = agent;
        bestScore = s;
      }
    }
    return best;
  }, [paretoWeights]);

  const isDirty =
    paretoWeights.cost !== DEFAULT_PARETO_WEIGHTS.cost ||
    paretoWeights.time !== DEFAULT_PARETO_WEIGHTS.time ||
    paretoWeights.sustainability !== DEFAULT_PARETO_WEIGHTS.sustainability ||
    paretoWeights.fairness !== DEFAULT_PARETO_WEIGHTS.fairness ||
    tierThresholds.tier_2 !== DEFAULT_TIER_THRESHOLDS.tier_2 ||
    tierThresholds.tier_3 !== DEFAULT_TIER_THRESHOLDS.tier_3 ||
    tierThresholds.tier_4 !== DEFAULT_TIER_THRESHOLDS.tier_4;

  return (
    <section className="mx-auto flex max-w-3xl flex-col gap-4">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-ink">
          <Sliders size={18} className="text-accent" aria-hidden="true" />
          {t("title")}
        </h1>
        <p className="max-w-2xl text-sm text-ink-muted">{t("subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <div className="space-y-0.5">
            <CardTitle>{t("weights.title")}</CardTitle>
            <p className="text-2xs text-ink-subtle">{t("weights.subtitle")}</p>
          </div>
        </CardHeader>
        <CardBody>
          <SliderRow
            id={`${ids}-w-cost`}
            label={t("weights.cost")}
            value={paretoWeights.cost}
            onChange={(v) => setParetoWeight("cost", v)}
          />
          <SliderRow
            id={`${ids}-w-time`}
            label={t("weights.time")}
            value={paretoWeights.time}
            onChange={(v) => setParetoWeight("time", v)}
          />
          <SliderRow
            id={`${ids}-w-sustainability`}
            label={t("weights.sustainability")}
            value={paretoWeights.sustainability}
            onChange={(v) => setParetoWeight("sustainability", v)}
          />
          <SliderRow
            id={`${ids}-w-fairness`}
            label={t("weights.fairness")}
            value={paretoWeights.fairness}
            onChange={(v) => setParetoWeight("fairness", v)}
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="space-y-0.5">
            <CardTitle>{t("thresholds.title")}</CardTitle>
            <p className="text-2xs text-ink-subtle">{t("thresholds.subtitle")}</p>
          </div>
        </CardHeader>
        <CardBody>
          <SliderRow
            id={`${ids}-t-tier_2`}
            label={t("thresholds.tier_2")}
            value={tierThresholds.tier_2}
            onChange={(v) => setTierThreshold("tier_2", v)}
          />
          <SliderRow
            id={`${ids}-t-tier_3`}
            label={t("thresholds.tier_3")}
            value={tierThresholds.tier_3}
            onChange={(v) => setTierThreshold("tier_3", v)}
          />
          <SliderRow
            id={`${ids}-t-tier_4`}
            label={t("thresholds.tier_4")}
            value={tierThresholds.tier_4}
            onChange={(v) => setTierThreshold("tier_4", v)}
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="space-y-0.5">
            <CardTitle>{t("preview.title")}</CardTitle>
            <p className="text-2xs text-ink-subtle">{t("preview.subtitle")}</p>
          </div>
        </CardHeader>
        <CardBody>
          <ProposalConstellation
            proposals={previewProposals}
            selectedAgent={previewSelected ?? previewWinner}
            onSelectAgent={setPreviewSelected}
          />
        </CardBody>
      </Card>

      <div
        className={cn(
          "flex items-center justify-between gap-3 rounded-md border border-border bg-surface-raised px-4 py-3",
          isDirty && "border-accent/40",
        )}
      >
        <p className="text-2xs text-ink-muted">{t("audit.note")}</p>
        <Button variant="ghost" size="sm" onClick={reset} disabled={!isDirty}>
          <RotateCcw size={13} aria-hidden="true" />
          {t("reset")}
        </Button>
      </div>
    </section>
  );
}
