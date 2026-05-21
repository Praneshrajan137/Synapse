/**
 * SYNAPSE Atlas Console — KPITicker (TS port).
 *
 * Five tiles per Living City surface (plan §5.1). Tokens drive colour;
 * Recharts is no longer needed at this size — pure layout.
 *
 * If a value is missing we render an em-dash placeholder, never zero —
 * zero is itself a meaningful business value.
 */
import { memo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "./cn";

export interface KPIData {
  readonly orders_min?: number | null;
  readonly avg_delivery_min?: number | null;
  readonly fill_rate?: number | null;
  readonly waste_rate?: number | null;
  readonly carbon_per_delivery?: number | null;
}

interface KPIItem {
  readonly key: keyof KPIData;
  readonly i18nKey: string;
  readonly format: (v: number) => ReactNode;
}

const ITEMS: readonly KPIItem[] = [
  { key: "orders_min", i18nKey: "livingCity.kpi.ordersPerMin", format: (v) => v.toFixed(1) },
  {
    key: "avg_delivery_min",
    i18nKey: "livingCity.kpi.avgDelivery",
    format: (v) => `${v.toFixed(1)}m`,
  },
  {
    key: "fill_rate",
    i18nKey: "livingCity.kpi.fillRate",
    format: (v) => `${(v * 100).toFixed(1)}%`,
  },
  {
    key: "waste_rate",
    i18nKey: "livingCity.kpi.wasteRate",
    format: (v) => `${(v * 100).toFixed(2)}%`,
  },
  {
    key: "carbon_per_delivery",
    i18nKey: "livingCity.kpi.co2PerDelivery",
    format: (v) => `${v.toFixed(2)}kg`,
  },
];

const PLACEHOLDER = "—";

export interface KPITickerProps {
  readonly data?: KPIData;
  readonly className?: string;
}

export const KPITicker = memo(function KPITicker({ data = {}, className }: KPITickerProps) {
  const { t } = useTranslation();
  return (
    <div
      role="region"
      aria-label="Key performance indicators"
      className={cn(
        "flex flex-wrap gap-4 rounded-lg border border-border bg-card px-4 py-3 sm:gap-8 sm:px-5",
        className,
      )}
    >
      {ITEMS.map(({ key, i18nKey, format }) => {
        const value = data[key];
        return (
          <div key={key} className="text-center">
            <div className="text-ops-xs uppercase tracking-wide text-muted-fg">
              {t(i18nKey)}
            </div>
            <div className="text-ops-xl font-semibold text-fg" aria-live="polite">
              {value === null || value === undefined ? PLACEHOLDER : format(value)}
            </div>
          </div>
        );
      })}
    </div>
  );
});
