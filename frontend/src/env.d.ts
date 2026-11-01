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
  // ADR-057 (finding 89): VITE_AUTO_LOGIN, VITE_AUTO_LOGIN_EMAIL and VITE_AUTO_LOGIN_PASSWORD
  // are gone. Every VITE_ value ships in the public bundle, so none may hold a credential.
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
