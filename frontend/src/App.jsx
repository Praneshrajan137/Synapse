import React from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import DecisionLog from "./pages/DecisionLog";
import OverrideConsole from "./pages/OverrideConsole";
import AgentStatus from "./pages/AgentStatus";
import DigitalTwin from "./pages/DigitalTwin";

const NAV_ITEMS = [
  { path: "/", label: "Dashboard" },
  { path: "/decisions", label: "Decision Log" },
  { path: "/escalations", label: "Override Console" },
  { path: "/agents", label: "Agent Status" },
  { path: "/twin", label: "Digital Twin" },
];

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
        <nav style={{ display: "flex", gap: 16, padding: "12px 24px", background: "#0f172a", color: "#e2e8f0" }}>
          <span style={{ fontWeight: 700, marginRight: 24 }}>SYNAPSE</span>
          {NAV_ITEMS.map(({ path, label }) => (
            <NavLink
              key={path}
              to={path}
              style={({ isActive }) => ({
                color: isActive ? "#38bdf8" : "#94a3b8",
                textDecoration: "none",
              })}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <main style={{ flex: 1, overflow: "auto", padding: 24, background: "#020617", color: "#e2e8f0" }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/decisions" element={<DecisionLog />} />
            <Route path="/escalations" element={<OverrideConsole />} />
            <Route path="/agents" element={<AgentStatus />} />
            <Route path="/twin" element={<DigitalTwin />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
