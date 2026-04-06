import React from "react";
import KPITicker from "../components/KPITicker";

export default function Dashboard() {
  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>SYNAPSE Dashboard</h1>
      <KPITicker data={{}} />
      <div
        style={{
          marginTop: 24,
          height: 500,
          background: "#1e293b",
          borderRadius: 12,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#64748b",
        }}
      >
        Deck.gl + MapLibre GL map (25 dark stores, order arcs, rider positions, demand heatmap)
      </div>
    </div>
  );
}
