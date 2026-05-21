/**
 * SYNAPSE Atlas Console — counterfactual diff card.
 *
 * Renders the Δ between this scenario's central estimate and the
 * actual outcome at decision time. Positive = scenario better than
 * actual; negative = worse. AAA-contrast on safety-critical deltas.
 */
import { memo } from "react";

import { Badge } from "@shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";

import type { WhatIfResult } from "../model/scenario";

const ENTRIES: ReadonlyArray<{
  key: keyof NonNullable<WhatIfResult["counterfactual"]>;
  label: string;
  unit?: string;
  goodWhenPositive: boolean;
}> = [
  { key: "revenue_delta", label: "Revenue Δ", unit: "₹", goodWhenPositive: true },
  { key: "fill_rate_delta", label: "Fill rate Δ", unit: "pp", goodWhenPositive: true },
  { key: "co2_delta", label: "CO₂ Δ", unit: "kg", goodWhenPositive: false },
];

export interface CounterfactualDiffProps {
  readonly result: WhatIfResult;
}

export const CounterfactualDiff = memo(function CounterfactualDiff({ result }: CounterfactualDiffProps) {
  const cf = result.counterfactual;
  if (!cf) {
    return (
      <Card>
        <CardContent className="text-ops-sm text-muted-fg">
          No counterfactual baseline attached.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-ops-base">Counterfactual diff vs actual</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 sm:grid-cols-3">
        {ENTRIES.map(({ key, label, unit, goodWhenPositive }) => {
          const value = cf[key] as number | undefined;
          if (typeof value !== "number") return null;
          const isGood =
            value === 0 ? null : goodWhenPositive ? value > 0 : value < 0;
          const variant = isGood === null ? "muted" : isGood ? "ok" : "critical";
          return (
            <div key={key} className="flex items-center justify-between gap-2 rounded border border-border/60 bg-bg/40 p-2">
              <span className="text-ops-sm text-muted-fg">{label}</span>
              <Badge variant={variant}>
                {value > 0 ? "+" : ""}
                {value.toFixed(2)}
                {unit ? ` ${unit}` : ""}
              </Badge>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
});
