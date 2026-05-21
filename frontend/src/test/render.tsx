import { TooltipProvider } from "@/ui/primitives";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type RenderResult, render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

/**
 * Render a component tree inside the providers every surface needs:
 * a fresh React Query client, a memory router, and the tooltip
 * provider. Retries are off so failed queries surface immediately.
 *
 * Pass `path` to mount the component under a route pattern so
 * `useParams` resolves (e.g. path "/inspector/:agentName").
 */
export function renderWithProviders(
  ui: ReactElement,
  options: { route?: string; path?: string } = {},
): RenderResult {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[options.route ?? "/"]}>
          <TooltipProvider>
            {options.path ? (
              <Routes>
                <Route path={options.path} element={children} />
              </Routes>
            ) : (
              children
            )}
          </TooltipProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper });
}
