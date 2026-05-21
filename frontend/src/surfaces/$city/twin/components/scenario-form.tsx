/**
 * SYNAPSE Atlas Console — Twin Studio scenario form.
 *
 * Bound to TanStack Router search-params (S2 wiring) and to the
 * scenario library (S5). Submit triggers `useSimulate.run()`.
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";

import type { ScenarioInput } from "../model/scenario";

const FIELDS: ReadonlyArray<{
  key: keyof ScenarioInput;
  step?: number;
  min?: number;
  max?: number;
  i18n: string;
}> = [
  { key: "demand_multiplier", step: 0.1, min: 0, max: 10, i18n: "twinStudio.form.demand_multiplier" },
  { key: "lead_time_multiplier", step: 0.1, min: 0, max: 10, i18n: "twinStudio.form.lead_time_multiplier" },
  { key: "failure_rate_multiplier", step: 0.1, min: 0, max: 10, i18n: "twinStudio.form.failure_rate_multiplier" },
  { key: "spoilage_rate_multiplier", step: 0.1, min: 0, max: 10, i18n: "twinStudio.form.spoilage_rate_multiplier" },
  { key: "n_scenarios", min: 1, max: 10_000, i18n: "twinStudio.form.n_scenarios" },
  { key: "duration_hours", step: 0.25, min: 0.25, max: 168, i18n: "twinStudio.form.duration_hours" },
];

export interface ScenarioFormProps {
  readonly value: ScenarioInput;
  readonly onChange: <K extends keyof ScenarioInput>(key: K, next: ScenarioInput[K]) => void;
  readonly onRun: () => void;
  readonly onSave: () => void;
  readonly isRunning: boolean;
}

export const ScenarioForm = memo(function ScenarioForm({
  value,
  onChange,
  onRun,
  onSave,
  isRunning,
}: ScenarioFormProps) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("twinStudio.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            <span className="mb-1 block text-ops-xs uppercase tracking-wide text-muted-fg">
              {t(f.i18n)}
            </span>
            <input
              type="number"
              {...(f.step !== undefined ? { step: f.step } : {})}
              {...(f.min !== undefined ? { min: f.min } : {})}
              {...(f.max !== undefined ? { max: f.max } : {})}
              value={value[f.key]}
              onChange={(e) => onChange(f.key, Number(e.target.value) as ScenarioInput[typeof f.key])}
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-ops-base text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
        ))}
        <div className="flex flex-wrap gap-2">
          <Button onClick={onRun} disabled={isRunning} className="flex-1">
            {isRunning ? t("common.loading") : t("twinStudio.form.run")}
          </Button>
          <Button variant="outline" onClick={onSave} disabled={isRunning}>
            Save scenario
          </Button>
        </div>
      </CardContent>
    </Card>
  );
});
