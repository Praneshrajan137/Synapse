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
  /** Sprint 16: "false" restores the login-first flow (default: auto-login). */
  readonly VITE_AUTO_LOGIN?: string;
  readonly VITE_AUTO_LOGIN_EMAIL?: string;
  readonly VITE_AUTO_LOGIN_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
