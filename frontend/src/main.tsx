import "./styles/global.css";
import "./i18n";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { onCLS, onINP, onLCP } from "web-vitals";
import { App } from "./app/App";
import { log } from "./lib/log";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("SYNAPSE: #root not found in document");
}

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
