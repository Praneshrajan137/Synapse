/**
 * SYNAPSE Atlas Console — Twin Studio route (S5 deep work).
 *
 * Plan §5.4: Monte-Carlo what-if. URL-driven input, Visx fan-out,
 * KL-divergence sparkline (I-12), counterfactual diff vs the actual,
 * Zustand+IDB scenario library.
 */
import { createFileRoute, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";

import { CounterfactualDiff } from "./components/counterfactual-diff";
import { FanOutChart } from "./components/fan-out-chart";
import { KlSparkline } from "./components/kl-sparkline";
import { ScenarioForm } from "./components/scenario-form";
import { ScenarioLibrary } from "./components/scenario-library";
import { useScenarioLibrary } from "./hooks/use-scenario-library";
import { useSimulate } from "./hooks/use-simulate";
import {
  type ScenarioInput,
  ScenarioInputSchema,
} from "./model/scenario";

export const Route = createFileRoute("/$city/twin/")({
  validateSearch: (search) => ScenarioInputSchema.parse(search),
  component: TwinStudio,
});

function TwinStudio() {
  const { t } = useTranslation();
  const { city } = useParams({ from: "/$city/twin/" });
  const search = useSearch({ from: "/$city/twin/" });
  const navigate = useNavigate({ from: "/$city/twin/" });

  const { run, result, isRunning } = useSimulate();
  const { scenarios, save, remove } = useScenarioLibrary();

  const onChange = useCallback(
    <K extends keyof ScenarioInput>(key: K, value: ScenarioInput[K]) => {
      void navigate({
        search: (prev) => ({ ...prev, [key]: value }),
        replace: true,
      });
    },
    [navigate],
  );

  const onLoad = useCallback(
    (input: ScenarioInput) => {
      void navigate({
        search: () => ({ ...input }),
        replace: true,
      });
    },
    [navigate],
  );

  const onSave = useCallback(() => {
    const label = `Scenario @ ${new Date().toLocaleTimeString("en-IN", {
      timeZone: "Asia/Kolkata",
      hour12: false,
    })}`;
    save(label, search);
  }, [save, search]);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-ops-xl font-bold tracking-tight">{t("twinStudio.title")}</h1>
        <span className="text-ops-sm text-muted-fg">{t(`city.${city}`)}</span>
      </header>

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col gap-3">
          <ScenarioForm
            value={search}
            onChange={onChange}
            onRun={() => run(search)}
            onSave={onSave}
            isRunning={isRunning}
          />
          <ScenarioLibrary scenarios={scenarios} onLoad={onLoad} onRemove={remove} />
        </div>

        <div className="flex flex-col gap-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-ops-base">
                {t("twinStudio.results.fanOut")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {result ? (
                <FanOutChart result={result} />
              ) : (
                <p className="text-ops-sm text-muted-fg">
                  Run a scenario to populate the fan-out (n={search.n_scenarios}, INV-TW-004 ≤ 10s).
                </p>
              )}
            </CardContent>
          </Card>
          {result && (
            <>
              <KlSparkline result={result} />
              <CounterfactualDiff result={result} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
