/**
 * SYNAPSE Atlas Console — entrypoint.
 *
 * Order of concerns (top → bottom):
 *   1. Design tokens + Tailwind base CSS.
 *   2. ErrorBoundary — catches provider mount errors.
 *   3. Providers — QueryClient, i18n, Unleash.
 *   4. RouterProvider — TanStack Router instance.
 *   5. Web-vitals beacon — kicked off after first paint so it doesn't
 *      compete with hydration.
 *
 * StrictMode is intentional. Hooks under @shared/realtime are written
 * to be StrictMode-safe (refs survive double-mount; reconnect attempts
 * don't multiply).
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { QueryClient } from "@tanstack/react-query";

import "@shared/design-tokens/index.css";
import { ErrorBoundary } from "@app/error-boundary";
import { Providers } from "@app/providers";
import { createAppRouter } from "@app/router";
import { startWebVitals } from "@shared/telemetry/web-vitals";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 5_000, refetchOnWindowFocus: false },
  },
});

const router = createAppRouter(queryClient);

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Atlas Console: missing #root mount point in index.html");
}

createRoot(rootEl).render(
  <StrictMode>
    <ErrorBoundary>
      <Providers>
        <RouterProvider router={router} />
      </Providers>
    </ErrorBoundary>
  </StrictMode>,
);

// Kick off RUM beacon. Idempotent + lazy-loads web-vitals to keep the
// shell bundle lean.
void startWebVitals();
