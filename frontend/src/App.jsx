import React from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import DecisionLog from "./pages/DecisionLog";
import OverrideConsole from "./pages/OverrideConsole";
import AgentStatus from "./pages/AgentStatus";
import DigitalTwin from "./pages/DigitalTwin";
import { useTheme } from "./theme/useTheme";

const NAV_ITEMS = [
  { path: "/", label: "Dashboard", end: true },
  { path: "/decisions", label: "Decision Log" },
  { path: "/escalations", label: "Override Console" },
  { path: "/agents", label: "Agent Status" },
  { path: "/twin", label: "Digital Twin" },
];

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:text-text-primary hover:border-border-strong"
    >
      <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}

function navClass({ isActive }) {
  return [
    "relative px-3 py-1.5 text-sm rounded-md transition-colors",
    isActive
      ? "text-brand-base font-semibold bg-[color-mix(in_oklab,var(--color-brand-base)_14%,transparent)]"
      : "text-text-tertiary hover:text-text-primary",
  ].join(" ");
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen flex-col bg-surface-canvas text-text-primary">
        <nav className="flex items-center gap-1 border-b border-border-subtle bg-surface-panel px-6 shadow-panel">
          <div className="mr-6 flex h-14 items-center gap-2.5">
            <span
              className="glow-accent grid h-6 w-6 place-items-center rounded-md text-[13px] font-bold text-brand-fg"
              style={{ "--accent": "var(--color-brand-base)", background: "var(--color-brand-base)" }}
              aria-hidden="true"
            >
              S
            </span>
            <span className="text-[15px] font-bold tracking-[0.18em] text-text-primary">
              SYNAPSE
            </span>
          </div>
          {NAV_ITEMS.map(({ path, label, end }) => (
            <NavLink key={path} to={path} end={end} className={navClass}>
              {label}
            </NavLink>
          ))}
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </nav>
        <main className="flex-1 overflow-auto p-6">
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
