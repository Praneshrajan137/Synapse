import React from "react";

const AGENTS = [
  "demand_prophet", "routing_navigator", "inventory_sentinel", "freshness_guardian",
  "pricing_oracle", "disruption_shield", "supplier_trust", "sustainability_agent",
];

export default function AgentStatus() {
  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>Agent Status</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
        {AGENTS.map((name) => (
          <div key={name} style={{ background: "#1e293b", borderRadius: 12, padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 8 }}>{name.replace(/_/g, " ")}</div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ color: "#94a3b8" }}>Status</span>
              <span style={{ color: "#22c55e" }}>Healthy</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ color: "#94a3b8" }}>p50 Latency</span>
              <span>-- ms</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ color: "#94a3b8" }}>p99 Latency</span>
              <span>-- ms</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#94a3b8" }}>Decisions/min</span>
              <span>--</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
