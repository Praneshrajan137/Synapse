import "./lib/zod-config";
import "./styles/global.css";
import "./i18n";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { onCLS, onINP, onLCP } from "web-vitals";
import { App } from "./app/App";
import { installPreloadReload } from "./app/LazyChunkBoundary";
import { log } from "./lib/log";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("SYNAPSE: #root not found in document");
}

// After a deploy, a chunk of the build this page was opened on is gone and its import rejects
// (finding 92). Reload once onto the current build; the loop guard, and the error state that
// renders when it holds, are in ./app/LazyChunkBoundary. Registered before the first render so
// a deep link's own route chunk is covered.
installPreloadReload({
  target: window,
  storage: () => window.sessionStorage,
  now: () => Date.now(),
  reload: () => window.location.reload(),
});

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Web Vitals — sent to the self-hosted telemetry endpoint (FE-INV-010/030).
const report = (metric: { name: string; value: number; id: string; rating?: string }) => {
  log({
    kind: "web_vitals",
    metric: metric.name,
    value: metric.value,
    id: metric.id,
    rating: metric.rating,
    path: window.location.pathname,
  });
};
onCLS(report);
onINP(report);
onLCP(report);
