import { useEffect } from "react";
import { useSessionStore } from "@state/session.store";
import { useSynapseApi } from "@hooks/use-synapse-api";

const REFRESH_BUFFER_MS = 60_000; // refresh 60s before expiry

/**
 * Schedules a silent /api/v1/auth/refresh shortly before token expiry.
 * Mounts once at the app root; tears down its timer on unmount.
 * FE-INV-023 — silent refresh, no user-visible disruption.
 */
export function useAuthRefresh(): void {
  const api = useSynapseApi();
  const tokenExpiresAt = useSessionStore((s) => s.tokenExpiresAt);
  const rotate = useSessionStore((s) => s.rotateAccessToken);
  const clear = useSessionStore((s) => s.clearAuth);

  useEffect(() => {
    if (!tokenExpiresAt) return;
    const fireAt = Math.max(0, tokenExpiresAt - Date.now() - REFRESH_BUFFER_MS);
    const id = window.setTimeout(async () => {
      try {
        const r = await api.refresh();
        rotate(r.access_token, r.expires_in);
      } catch {
        clear();
      }
    }, fireAt);
    return () => window.clearTimeout(id);
  }, [api, tokenExpiresAt, rotate, clear]);
}
