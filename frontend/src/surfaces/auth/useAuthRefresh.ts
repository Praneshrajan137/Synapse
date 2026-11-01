import { useSynapseApi } from "@hooks/use-synapse-api";
import { useSessionStore } from "@state/session.store";
import { useEffect } from "react";
import { requestPreviewGrant } from "./access-api";
import { useAccessStore } from "./access.store";

const REFRESH_BUFFER_MS = 60_000; // refresh 60s before expiry

/**
 * Schedules a silent renewal shortly before token expiry.
 * Mounts once at the app root; tears down its timer on unmount.
 * FE-INV-023 — silent refresh, no user-visible disruption.
 *
 * ADR-057: a signed-in session renews through POST /api/v1/auth/refresh and its HttpOnly
 * cookie. An open-mode preview grant has no refresh cookie, so it renews by taking a fresh
 * grant instead, and records that grant's authority beside it, so the access badge never names
 * an authority the session no longer holds. A refusal clears the session, which hands it back
 * to the boot access hook.
 */
export function useAuthRefresh(): void {
  const api = useSynapseApi();
  const tokenExpiresAt = useSessionStore((s) => s.tokenExpiresAt);
  const rotate = useSessionStore((s) => s.rotateAccessToken);
  const setAuth = useSessionStore((s) => s.setAuth);
  const clear = useSessionStore((s) => s.clearAuth);
  const setAccess = useAccessStore((s) => s.setAccess);
  const openPreview = useAccessStore((s) => s.access.kind === "open");

  useEffect(() => {
    if (!tokenExpiresAt) return;
    const fireAt = Math.max(0, tokenExpiresAt - Date.now() - REFRESH_BUFFER_MS);
    const id = window.setTimeout(async () => {
      try {
        if (openPreview) {
          const grant = await requestPreviewGrant();
          setAuth(grant.role, grant.access_token, grant.operator_token_ref, grant.expires_in);
          setAccess({ kind: "open", authority: grant.authority });
          return;
        }
        const r = await api.refresh();
        rotate(r.access_token, r.expires_in);
      } catch {
        clear();
      }
    }, fireAt);
    return () => window.clearTimeout(id);
  }, [api, tokenExpiresAt, rotate, setAuth, setAccess, clear, openPreview]);
}
