import React from "react";

const KPI_ITEMS = [
  { key: "orders_min", label: "Orders/min", fmt: (v) => v?.toFixed(1) ?? "--" },
  { key: "avg_delivery_min", label: "Avg Delivery", fmt: (v) => (v ? `${v.toFixed(1)}m` : "--") },
  { key: "fill_rate", label: "Fill Rate", fmt: (v) => (v ? `${(v * 100).toFixed(1)}%` : "--") },
  { key: "waste_rate", label: "Waste Rate", fmt: (v) => (v ? `${(v * 100).toFixed(2)}%` : "--") },
  { key: "carbon_per_delivery", label: "CO2/Delivery", fmt: (v) => (v ? `${v.toFixed(2)}kg` : "--") },
];

export default function KPITicker({ data = {} }) {
  return (
    <div style={{ display: "flex", gap: 32, padding: "8px 16px", background: "#1e293b", borderRadius: 8 }}>
      {KPI_ITEMS.map(({ key, label, fmt }) => (
        <div key={key} style={{ textAlign: "center" }}>
          <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase" }}>{label}</div>
          <div style={{ fontSize: 20, fontWeight: 600, color: "#f1f5f9" }}>{fmt(data[key])}</div>
        </div>
      ))}
    </div>
  );
}
