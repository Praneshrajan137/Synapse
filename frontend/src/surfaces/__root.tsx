/**
 * SYNAPSE Atlas Console — root route.
 *
 * Owns the chrome (nav, locale picker, theme toggle, residency chip,
 * sign-out) shared across every surface and the city layout. The
 * actual top nav lives in `<RootLayout>` (sibling component) so the
 * route file stays small and TS-friendly.
 *
 * Suspense boundary at the layout level catches lazy-route loading;
 * NotFound + Error are configured on the router itself in `app/router.tsx`.
 */
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import type { QueryClient } from "@tanstack/react-query";

import { RootLayout } from "@app/root-layout";

export interface RouterContext {
  readonly queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: () => (
    <RootLayout>
      <Outlet />
    </RootLayout>
  ),
});
