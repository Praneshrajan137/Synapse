/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ORCHESTRATOR_URL?: string;
  readonly VITE_GATEWAY_URL?: string;
  readonly VITE_TWIN_URL?: string;
  readonly VITE_DEFAULT_CITY?: "bengaluru" | "mumbai";
  readonly VITE_TILES_URL?: string;
  readonly VITE_TELEMETRY_ENDPOINT?: string;
  readonly VITE_BUILD_SHA?: string;
  readonly VITE_BUILD_TIME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
