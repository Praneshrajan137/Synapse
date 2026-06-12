import { useSynapseApi } from "@hooks/use-synapse-api";
import { type Role, useSessionStore } from "@state/session.store";
import { useEffect, useRef } from "react";

// Demo-console boot auth (Sprint 16): the operator console opens straight
// into Mission Control — no login wall. On boot, an anonymous session is
// silently signed in with the demo admin operator (admin unlocks all 8
// surfaces; ops would block /agents + /twin behind the engineer rank).
//
// HONEST FAILURE: if the gateway is down or the credential is rejected,
// the hook settles silently and RouteGuard falls through to /login exactly
// as before — the login surface remains the fallback, not a dead end.
//
// Reversible: VITE_AUTO_LOGIN=false restores the login-first flow; the
// credential pair is overridable per environment. The default mirrors the
// dev operator hardcoded in api/routers/auth.py — no new secret surface.

export function useBootAutoLogin(): void {
  const api = useSynapseApi();
  const role = useSessionStore((s) => s.role);
  const setAuth = useSessionStore((s) => s.setAuth);
  const setBootAuth = useSessionStore((s) => s.setBootAuth);
  // One attempt per app boot — StrictMode double-invokes effects, and a
  // failed attempt must NOT loop (the 15s posture poll already exercises
  // the gateway; auth retry adds nothing but noise).
  const attempted = useRef(false);

  useEffect(() => {
    // Env reads live inside the effect so tests can stub them per-case.
    const enabled = import.meta.env.VITE_AUTO_LOGIN !== "false";
    if (!enabled || role !== "anonymous" || attempted.current) {
      setBootAuth("settled");
      return;
    }
    attempted.current = true;
    setBootAuth("pending");
    void (async () => {
      try {
        const r = await api.login({
          operator_id: import.meta.env.VITE_AUTO_LOGIN_EMAIL ?? "admin@synapse.local",
          password: import.meta.env.VITE_AUTO_LOGIN_PASSWORD ?? "admin_dev_2026!!",
        });
        setAuth(r.role as Role, r.access_token, r.operator_token_ref, r.expires_in);
      } catch {
        // Silent: RouteGuard sends the operator to /login as before.
      } finally {
        setBootAuth("settled");
      }
    })();
  }, [api, role, setAuth, setBootAuth]);
}
