import React, { useState } from "react";

export default function DigitalTwin() {
  const [scenario, setScenario] = useState("demand_spike");
  const [running, setRunning] = useState(false);

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>Digital Twin</h1>
      <div style={{ display: "flex", gap: 24 }}>
        <div style={{ flex: 1 }}>
          <div style={{ background: "#1e293b", borderRadius: 12, height: 400, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b" }}>
            3D Supply Network (react-force-graph-3d)
          </div>
        </div>
        <div style={{ width: 320 }}>
          <div style={{ background: "#1e293b", borderRadius: 12, padding: 20 }}>
            <h3 style={{ marginBottom: 12 }}>What-If Scenario</h3>
            <label style={{ color: "#94a3b8", fontSize: 13 }}>Disruption Type</label>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0", marginBottom: 12 }}
            >
              <option value="demand_spike">Demand Spike</option>
              <option value="supplier_failure">Supplier Failure</option>
              <option value="route_disruption">Route Disruption</option>
              <option value="weather_event">Weather Event</option>
            </select>
            <button
              onClick={() => setRunning(true)}
              disabled={running}
              style={{ width: "100%", padding: "10px 0", borderRadius: 6, border: "none", background: running ? "#334155" : "#3b82f6", color: "#fff", cursor: running ? "not-allowed" : "pointer" }}
            >
              {running ? "Running Monte Carlo..." : "Run Simulation"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
