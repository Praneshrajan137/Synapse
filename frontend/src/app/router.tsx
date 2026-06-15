import { AgentCouncil } from "@surfaces/agent-council/AgentCouncil";
import { AgentDetail } from "@surfaces/agent-council/AgentDetail";
import { AuditVault } from "@surfaces/audit-vault/AuditVault";
import { Login } from "@surfaces/auth/Login";
import { DecisionDetail } from "@surfaces/decision-theater/DecisionDetail";
import { DecisionTheater } from "@surfaces/decision-theater/DecisionTheater";
import { DemoTheater } from "@surfaces/demo-theater/DemoTheater";
import { Ingress } from "@surfaces/ingress/Ingress";
import { LiveMarkets } from "@surfaces/live-markets/LiveMarkets";
import { MissionControl } from "@surfaces/mission-control/MissionControl";
import { Cockpit } from "@surfaces/override-cockpit/Cockpit";
import { Steering } from "@surfaces/steering/Steering";
import { TwinLab } from "@surfaces/twin-lab/TwinLab";
import { Suspense, lazy } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import { RouteGuard } from "./RouteGuard";
import { Shell } from "./Shell";

// Operations is route-split (FE-INV-014/025): its panels stay out of the entry
// bundle so the flagship surfaces load fast.
const Operations = lazy(() =>
  import("@surfaces/operations/Operations").then((m) => ({ default: m.Operations })),
);

export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  {
    path: "/",
    element: <Shell />,
    children: [
      {
        index: true,
        element: (
          <RouteGuard minRole="viewer">
            <MissionControl />
          </RouteGuard>
        ),
      },
      {
        path: "cockpit",
        element: (
          <RouteGuard minRole="ops">
            <Cockpit />
          </RouteGuard>
        ),
      },
      {
        path: "decisions",
        element: (
          <RouteGuard minRole="viewer">
            <DecisionTheater />
          </RouteGuard>
        ),
      },
      {
        path: "decisions/:id",
        element: (
          <RouteGuard minRole="viewer">
            <DecisionDetail />
          </RouteGuard>
        ),
      },
      {
        path: "audit",
        element: (
          <RouteGuard minRole="viewer">
            <AuditVault />
          </RouteGuard>
        ),
      },
      {
        path: "agents",
        element: (
          <RouteGuard minRole="engineer">
            <AgentCouncil />
          </RouteGuard>
        ),
      },
      {
        path: "agents/:name",
        element: (
          <RouteGuard minRole="engineer">
            <AgentDetail />
          </RouteGuard>
        ),
      },
      {
        path: "twin",
        element: (
          <RouteGuard minRole="engineer">
            <TwinLab />
          </RouteGuard>
        ),
      },
      {
        path: "markets",
        element: (
          <RouteGuard minRole="viewer">
            <LiveMarkets />
          </RouteGuard>
        ),
      },
      {
        path: "ingress",
        element: (
          <RouteGuard minRole="ops">
            <Ingress />
          </RouteGuard>
        ),
      },
      {
        path: "demo",
        element: (
          <RouteGuard minRole="viewer">
            <DemoTheater />
          </RouteGuard>
        ),
      },
      {
        path: "steering",
        element: (
          <RouteGuard minRole="ops">
            <Steering />
          </RouteGuard>
        ),
      },
      {
        path: "operations",
        element: (
          <RouteGuard minRole="viewer">
            <Suspense
              fallback={<div className="p-6 text-sm text-ink-muted">Loading Standing Watch…</div>}
            >
              <Operations />
            </Suspense>
          </RouteGuard>
        ),
      },
      { path: "escalations", element: <Navigate to="/cockpit" replace /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
