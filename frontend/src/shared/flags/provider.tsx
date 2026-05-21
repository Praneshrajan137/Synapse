/**
 * SYNAPSE Atlas Console — Unleash provider component.
 *
 * Wraps the app in `<FlagProvider>` when an Edge URL is configured.
 * Otherwise renders children directly so surfaces can run in stub mode.
 */
import type { ReactNode } from "react";
import { FlagProvider } from "@unleash/proxy-client-react";

import { flagsAreLive } from "./index";

const PROXY_URL = import.meta.env["VITE_UNLEASH_PROXY_URL"];
const PROXY_TOKEN = import.meta.env["VITE_UNLEASH_TOKEN"];
const APP_NAME = "atlas-console";

interface FlagsProviderProps {
  readonly children: ReactNode;
}

export function FlagsProvider({ children }: FlagsProviderProps) {
  if (!flagsAreLive) return <>{children}</>;

  return (
    <FlagProvider
      config={{
        url: PROXY_URL!,
        clientKey: PROXY_TOKEN!,
        appName: APP_NAME,
        refreshInterval: 30,
        environment: import.meta.env.MODE,
      }}
    >
      {children}
    </FlagProvider>
  );
}
