import { useEffect, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";

import i18n, { bootstrapI18n } from "@shared/i18n";
import { FlagsProvider } from "@shared/flags";

/**
 * SYNAPSE Atlas Console — root providers tree.
 *
 *   <QueryClientProvider>     ← server state (TanStack Query)
 *     <I18nextProvider>       ← i18n (en + hi day-1)
 *       <FlagsProvider>       ← Unleash feature flags (stub mode if no Edge)
 *         {children}
 *
 * Theme attribute is owned by index.css (`[data-theme]`); a useEffect in
 * RootLayout flips it based on user preference and `prefers-color-scheme`.
 *
 * The error boundary lives one layer above (in main.tsx) so it catches
 * provider mount errors too.
 */

interface ProvidersProps {
  readonly children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 2, staleTime: 5_000, refetchOnWindowFocus: false },
        },
      }),
  );

  // Bootstrap i18n exactly once. Suspending here would block first paint;
  // we instead resolve eagerly and let i18next fall back to the embedded
  // resources (en-IN + hi-IN). Missing-key warnings live in CI, not runtime.
  useEffect(() => {
    void bootstrapI18n();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <FlagsProvider>{children}</FlagsProvider>
      </I18nextProvider>
    </QueryClientProvider>
  );
}

export { useState }; // re-export so providers.tsx remains the single seam tested
