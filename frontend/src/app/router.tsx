import { MissionControl } from "@surfaces/mission-control/MissionControl";
import { lazy } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import { LazySurface } from "./LazySurface";
import { RouteGuard } from "./RouteGuard";
import { Shell } from "./Shell";

// Every surface except Mission Control is route-split (FE-INV-014/025). "/" is where the
// mobile Web_Vitals_Budget is measured (Req 15.4, tests/e2e/mobile-reality.spec.ts), so its
// first render must not wait on any other surface's code; each other route loads its own
// chunk on first visit, through the one shared boundary in `LazySurface`.
//
// Splitting a route removes only what that surface alone imports. A chunk the entry still
// imports statically for another reason stays on "/"'s critical path, so the build lists the
// entry's eager set and fails on the heavy viz chunks (scripts/check-entry-preloads.mjs).
const Login = lazy(() => import("@surfaces/auth/Login").then((m) => ({ default: m.Login })));
const Cockpit = lazy(() =>
  import("@surfaces/override-cockpit/Cockpit").then((m) => ({ default: m.Cockpit })),
);
const DecisionTheater = lazy(() =>
  import("@surfaces/decision-theater/DecisionTheater").then((m) => ({
    default: m.DecisionTheater,
  })),
);
const DecisionDetail = lazy(() =>
  import("@surfaces/decision-theater/DecisionDetail").then((m) => ({ default: m.DecisionDetail })),
);
const CouncilTheater = lazy(() =>
  import("@surfaces/council-theater/CouncilTheater").then((m) => ({ default: m.CouncilTheater })),
);
const AuditVault = lazy(() =>
  import("@surfaces/audit-vault/AuditVault").then((m) => ({ default: m.AuditVault })),
);
const AgentCouncil = lazy(() =>
  import("@surfaces/agent-council/AgentCouncil").then((m) => ({ default: m.AgentCouncil })),
);
const AgentDetail = lazy(() =>
  import("@surfaces/agent-council/AgentDetail").then((m) => ({ default: m.AgentDetail })),
);
const TwinLab = lazy(() =>
  import("@surfaces/twin-lab/TwinLab").then((m) => ({ default: m.TwinLab })),
);
const LiveMarkets = lazy(() =>
  import("@surfaces/live-markets/LiveMarkets").then((m) => ({ default: m.LiveMarkets })),
);
const Ingress = lazy(() =>
  import("@surfaces/ingress/Ingress").then((m) => ({ default: m.Ingress })),
);
const DemoTheater = lazy(() =>
  import("@surfaces/demo-theater/DemoTheater").then((m) => ({ default: m.DemoTheater })),
);
const Steering = lazy(() =>
  import("@surfaces/steering/Steering").then((m) => ({ default: m.Steering })),
);
const Operations = lazy(() =>
  import("@surfaces/operations/Operations").then((m) => ({ default: m.Operations })),
);

export const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <LazySurface name="Sign-in">
        <Login />
      </LazySurface>
    ),
  },
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
            <LazySurface name="Override Cockpit">
              <Cockpit />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "decisions",
        element: (
          <RouteGuard minRole="viewer">
            <LazySurface name="Decision Theater">
              <DecisionTheater />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "decisions/:id",
        element: (
          <RouteGuard minRole="viewer">
            <LazySurface name="Decision Detail">
              <DecisionDetail />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "council/:id",
        element: (
          <RouteGuard minRole="viewer">
            <LazySurface name="Council Theater">
              <CouncilTheater />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "audit",
        element: (
          <RouteGuard minRole="viewer">
            <LazySurface name="Audit Vault">
              <AuditVault />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "agents",
        element: (
          <RouteGuard minRole="engineer">
            <LazySurface name="Agent Council">
              <AgentCouncil />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "agents/:name",
        element: (
          <RouteGuard minRole="engineer">
            <LazySurface name="Agent Detail">
              <AgentDetail />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "twin",
        element: (
          <RouteGuard minRole="engineer">
            <LazySurface name="Twin Lab">
              <TwinLab />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "markets",
        element: (
          <RouteGuard minRole="viewer">
            <LazySurface name="Live Markets">
              <LiveMarkets />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "ingress",
        element: (
          <RouteGuard minRole="ops">
            <LazySurface name="Ingress Console">
              <Ingress />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "demo",
        element: (
          <RouteGuard minRole="viewer">
            <LazySurface name="Demo Theater">
              <DemoTheater />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "steering",
        element: (
          <RouteGuard minRole="ops">
            <LazySurface name="Steering">
              <Steering />
            </LazySurface>
          </RouteGuard>
        ),
      },
      {
        path: "operations",
        element: (
          <RouteGuard minRole="viewer">
            <LazySurface name="Standing Watch">
              <Operations />
            </LazySurface>
          </RouteGuard>
        ),
      },
      { path: "escalations", element: <Navigate to="/cockpit" replace /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
