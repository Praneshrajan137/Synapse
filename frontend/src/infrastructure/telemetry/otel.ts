/**
 * OpenTelemetry browser tracing.
 *
 * The SYNAPSE backend has Prometheus metrics but no distributed tracing
 * (audit finding). This wires the frontend into a self-hosted Tempo/
 * Jaeger collector via OTLP-HTTP so an operator action can be traced
 * end-to-end: click → fetch → orchestrator span.
 *
 * Zero third-party telemetry — collector is self-hosted (plan tenet
 * T-12, invariant I-1). Initialization is fully defensive: if the
 * collector is unreachable or the env flag is off, this is a no-op and
 * never throws into app startup.
 */

import { ZoneContextManager } from "@opentelemetry/context-zone";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { DocumentLoadInstrumentation } from "@opentelemetry/instrumentation-document-load";
import { FetchInstrumentation } from "@opentelemetry/instrumentation-fetch";
import { Resource } from "@opentelemetry/resources";
import { BatchSpanProcessor, WebTracerProvider } from "@opentelemetry/sdk-trace-web";
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
} from "@opentelemetry/semantic-conventions";

const APP_VERSION = "0.5.0";

/** Default OTLP-HTTP traces endpoint (Tempo). Override with VITE_OTLP_ENDPOINT. */
const DEFAULT_ENDPOINT = "http://localhost:4318/v1/traces";

let initialized = false;

/**
 * Initialize browser tracing. Idempotent and safe to call before render.
 * Enabled when VITE_OTEL_ENABLED is "true"; otherwise a deliberate no-op
 * so local development is not noisy.
 */
export function initTelemetry(): void {
  if (initialized) return;
  initialized = true;

  const enabled = import.meta.env.VITE_OTEL_ENABLED === "true";
  if (!enabled) return;

  try {
    const endpoint = import.meta.env.VITE_OTLP_ENDPOINT ?? DEFAULT_ENDPOINT;

    const provider = new WebTracerProvider({
      resource: new Resource({
        [ATTR_SERVICE_NAME]: "synapse-frontend",
        [ATTR_SERVICE_VERSION]: APP_VERSION,
      }),
      spanProcessors: [new BatchSpanProcessor(new OTLPTraceExporter({ url: endpoint }))],
    });

    provider.register({ contextManager: new ZoneContextManager() });

    registerInstrumentations({
      instrumentations: [
        new DocumentLoadInstrumentation(),
        new FetchInstrumentation({
          // Trace API calls to our own gateway; ignore static assets.
          propagateTraceHeaderCorsUrls: [/\/api\//, /\/health/],
        }),
      ],
    });
  } catch (error) {
    // Telemetry must never break the app. Log and move on.
    console.warn("[telemetry] initialization failed; continuing without tracing", error);
  }
}
