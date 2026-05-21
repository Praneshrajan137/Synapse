import React from "react";

// Each KPI carries a hairline accent in the colour of the agent (or state)
// that owns the metric — colour earned, never decorative. The value itself
// stays in primary text so the metric is legible without colour.
const KPI_ITEMS = [
  {
    key: "orders_min",
    label: "Orders / min",
    accent: "var(--color-brand-base)",
    fmt: (v) => v?.toFixed(1) ?? "--",
  },
  {
    key: "avg_delivery_min",
    label: "Avg Delivery",
    accent: "var(--color-agent-routing-navigator)",
    fmt: (v) => (v ? `${v.toFixed(1)}m` : "--"),
  },
  {
    key: "fill_rate",
    label: "Fill Rate",
    accent: "var(--color-state-success)",
    fmt: (v) => (v ? `${(v * 100).toFixed(1)}%` : "--"),
  },
  {
    key: "waste_rate",
    label: "Waste Rate",
    accent: "var(--color-agent-freshness-guardian)",
    fmt: (v) => (v ? `${(v * 100).toFixed(2)}%` : "--"),
  },
  {
    key: "carbon_per_delivery",
    label: "CO₂ / Delivery",
    accent: "var(--color-agent-sustainability-agent)",
    fmt: (v) => (v ? `${v.toFixed(2)}kg` : "--"),
  },
];

export default function KPITicker({ data = {} }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {KPI_ITEMS.map(({ key, label, fmt, accent }) => (
        <div
          key={key}
          className="panel relative overflow-hidden p-4 transition-colors hover:border-border-strong"
        >
          <span
            className="absolute inset-x-0 top-0 h-[3px]"
            style={{ background: accent }}
            aria-hidden="true"
          />
          <div className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">
            {label}
          </div>
          <div className="mt-1.5 font-mono text-2xl font-semibold text-text-primary">
            {fmt(data[key])}
          </div>
        </div>
      ))}
    </div>
  );
}
