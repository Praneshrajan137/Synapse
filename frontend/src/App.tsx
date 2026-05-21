import { AppShell } from "@/app/shell/AppShell";
import { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

/**
 * Application root — routes the seven Synaptic Calm surfaces inside the
 * persistent app shell.
 *
 * Every surface is lazy-loaded so heavy visualization libraries are
 * fetched only when their surface is entered — see the performance
 * budgets in the plan, section 10.
 */

const Bridge = lazy(() => import("@/app/routes/Bridge"));
const Theater = lazy(() => import("@/app/routes/Theater"));
const Council = lazy(() => import("@/app/routes/Council"));
const Replay = lazy(() => import("@/app/routes/Replay"));
const Twin = lazy(() => import("@/app/routes/Twin"));
const Inspector = lazy(() => import("@/app/routes/Inspector"));
const Streams = lazy(() => import("@/app/routes/Streams"));
const Steering = lazy(() => import("@/app/routes/Steering"));

function SurfaceFallback() {
  return (
    <div className="flex h-full items-center justify-center text-sm text-ink-hint">
      Loading surface…
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Suspense fallback={<SurfaceFallback />}>
          <Routes>
            <Route path="/" element={<Bridge />} />
            <Route path="/theater" element={<Theater />} />
            <Route path="/theater/:decisionId" element={<Theater />} />
            <Route path="/council" element={<Council />} />
            <Route path="/council/:decisionId" element={<Council />} />
            <Route path="/replay" element={<Replay />} />
            <Route path="/replay/:decisionId" element={<Replay />} />
            <Route path="/twin" element={<Twin />} />
            <Route path="/inspector" element={<Inspector />} />
            <Route path="/inspector/:agentName" element={<Inspector />} />
            <Route path="/streams" element={<Streams />} />
            <Route path="/steering" element={<Steering />} />

            {/* Redirects from the pre-Synaptic-Calm routes. */}
            <Route path="/decisions" element={<Navigate to="/replay" replace />} />
            <Route path="/escalations" element={<Navigate to="/council" replace />} />
            <Route path="/agents" element={<Navigate to="/inspector" replace />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AppShell>
    </BrowserRouter>
  );
}
