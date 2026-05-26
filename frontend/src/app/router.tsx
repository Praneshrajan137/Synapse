import { AgentCouncil } from "@surfaces/agent-council/AgentCouncil";
import { AgentDetail } from "@surfaces/agent-council/AgentDetail";
import { AuditVault } from "@surfaces/audit-vault/AuditVault";
import { Login } from "@surfaces/auth/Login";
import { DecisionDetail } from "@surfaces/decision-theater/DecisionDetail";
import { DecisionTheater } from "@surfaces/decision-theater/DecisionTheater";
import { DemoTheater } from "@surfaces/demo-theater/DemoTheater";
import { MissionControl } from "@surfaces/mission-control/MissionControl";
import { Cockpit } from "@surfaces/override-cockpit/Cockpit";
import { Steering } from "@surfaces/steering/Steering";
import { TwinLab } from "@surfaces/twin-lab/TwinLab";
import { Navigate, createBrowserRouter } from "react-router-dom";
import { RouteGuard } from "./RouteGuard";
import { Shell } from "./Shell";

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
      { path: "escalations", element: <Navigate to="/cockpit" replace /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
