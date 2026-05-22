import { applyTheme, useThemeStore } from "@state/theme.store";
import { useAuthRefresh } from "@surfaces/auth/useAuthRefresh";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { type PropsWithChildren, useEffect } from "react";
import { Toaster } from "sonner";
import { ErrorBoundary } from "./error-boundary";

// Single QueryClient for the SPA. retry=2 / staleTime=5s preserves the
// previous default while we re-tune per surface in P1.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5_000,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

function SessionSidecar() {
  // Mounts inside the QueryClient so useSynapseApi() can resolve. Returns
  // null but keeps the silent refresh timer alive.
  useAuthRefresh();
  return null;
}

export function AppProviders({ children }: PropsWithChildren) {
  const theme = useThemeStore((s) => s.theme);
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SessionSidecar />
        {children}
        <Toaster
          theme="dark"
          richColors
          closeButton
          position="top-right"
          toastOptions={{ duration: 5_000 }}
        />
        {import.meta.env.DEV && <ReactQueryDevtools buttonPosition="bottom-left" />}
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
