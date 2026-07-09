import { useSessionStore } from "@state/session.store";
import { createRefreshGate } from "@transport/auth-refresh";
import { HttpError } from "@transport/errors";
import { type SynapseApi, createSynapseApi } from "@transport/synapse-api";
import { useMemo, useRef } from "react";

// Single SynapseApi per render tree, with bearer token wired through.
// 401 responses on any call trigger a single-flight /refresh; a refresh
// failure OR a second 401 clears the session, which routes the operator to
// /login via RouteGuard — a client-side navigation, never a full page reload
// (Req 12.2, FE-INV-023).

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
      // NOTE: 401 recovery is owned entirely by the single-flight refresh gate
      // below. We deliberately do NOT clear the session on a raw 401 here —
      // doing so would tear down the operator's role before the refresh had a
      // chance to recover it, defeating the silent single-flight refresh
      // (Req 12.2, FE-INV-023).
    });
    // Wrap every method with the refresh gate.
    const wrapped = new Proxy(base, {
      get(target, prop, receiver) {
        const value = Reflect.get(target, prop, receiver) as unknown;
        if (typeof value !== "function") return value;
        // Refresh is itself the recovery operation — do not wrap it.
        if (prop === "refresh" || prop === "login" || prop === "logout") return value;
        return (...args: unknown[]) =>
          gate
            .withRefreshRetry(
              () => (value as (...a: unknown[]) => Promise<unknown>).apply(target, args),
              async () => {
                try {
                  const r = await base.refresh();
                  useSessionStore.getState().rotateAccessToken(r.access_token, r.expires_in);
                } catch {
                  // Refresh failed — the session is unrecoverable. Clear it so
                  // RouteGuard routes to /login without a full page reload.
                  useSessionStore.getState().clearAuth();
                  throw new Error("session expired");
                }
              },
            )
            .catch((err: unknown) => {
              // A 401 that survives the single-flight refresh (a SECOND 401 on
              // replay) is terminal: clear the session so RouteGuard routes to
              // /login without a reload (Req 12.2, FE-INV-023).
              if (err instanceof HttpError && err.status === 401) {
                useSessionStore.getState().clearAuth();
              }
              throw err;
            });
      },
    }) as SynapseApi;
    apiRef.current = wrapped;
    return wrapped;
  }, []);
}
