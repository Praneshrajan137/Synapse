import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initTelemetry } from "./infrastructure/telemetry/otel";
import "./styles/globals.css";

initTelemetry();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 5_000 },
  },
});

const mockingEnabled = import.meta.env.VITE_MOCK_API !== "false";

/**
 * Start the MSW mock gateway unless explicitly disabled. This keeps the
 * interface fully demonstrable (and the demo build live) without the
 * Python stack. Build with VITE_MOCK_API=false to hit a real backend.
 */
async function enableMocking(): Promise<void> {
  if (!mockingEnabled) return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass", quiet: true });
}

/**
 * Register the PWA service worker for offline support — but only when
 * MSW is not the gateway, since MSW owns the service-worker scope in
 * mock mode and the two cannot both control the page.
 */
async function enablePWA(): Promise<void> {
  if (mockingEnabled || !import.meta.env.PROD) return;
  const { registerSW } = await import("virtual:pwa-register");
  registerSW({ immediate: true });
}

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("SYNAPSE: root element #root not found in document");
}

enableMocking().then(() => {
  createRoot(rootElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
  void enablePWA();
});
