/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  /** Enables OpenTelemetry browser tracing when "true". */
  readonly VITE_OTEL_ENABLED?: string;
  /** OTLP-HTTP traces endpoint. Defaults to the local Tempo collector. */
  readonly VITE_OTLP_ENDPOINT?: string;
  /** When "true", Playwright E2E hits the live backend instead of MSW. */
  readonly VITE_E2E_LIVE?: string;
  /** Set "false" to disable the MSW mock gateway and hit a real backend. */
  readonly VITE_MOCK_API?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
