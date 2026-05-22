import { useSessionStore } from "@state/session.store";
import { createRefreshGate } from "@transport/auth-refresh";
import { type SynapseApi, createSynapseApi } from "@transport/synapse-api";
import { useMemo, useRef } from "react";

// Single SynapseApi per render tree, with bearer token wired through.
// 401 responses on any call trigger a single-flight /refresh; failure
// of the refresh kicks the operator to /login (handled by RouteGuard).

const ORCHESTRATOR_URL = import.meta.env.VITE_ORCHESTRATOR_URL ?? "";
const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "";
const TWIN_URL = import.meta.env.VITE_TWIN_URL ?? "";

export function useSynapseApi(): SynapseApi {
  const apiRef = useRef<SynapseApi | null>(null);
  return useMemo(() => {
    if (apiRef.current) return apiRef.current;
    const gate = createRefreshGate();
    const base = createSynapseApi({
      orchestratorUrl: ORCHESTRATOR_URL,
      gatewayUrl: GATEWAY_URL,
      twinUrl: TWIN_URL || undefined,
      getAccessToken: () => useSessionStore.getState().accessToken,
      onAuthExpired: () => useSessionStore.getState().clearAuth(),
    });
    // Wrap every method with the refresh gate.
    const wrapped = new Proxy(base, {
      get(target, prop, receiver) {
        const value = Reflect.get(target, prop, receiver) as unknown;
        if (typeof value !== "function") return value;
        // Refresh is itself the recovery operation — do not wrap it.
        if (prop === "refresh" || prop === "login" || prop === "logout") return value;
        return (...args: unknown[]) =>
          gate.withRefreshRetry(
            () => (value as (...a: unknown[]) => Promise<unknown>).apply(target, args),
            async () => {
              try {
                const r = await base.refresh();
                useSessionStore.getState().rotateAccessToken(r.access_token, r.expires_in);
              } catch {
                useSessionStore.getState().clearAuth();
                throw new Error("session expired");
              }
            },
          );
      },
    }) as SynapseApi;
    apiRef.current = wrapped;
    return wrapped;
  }, []);
}
