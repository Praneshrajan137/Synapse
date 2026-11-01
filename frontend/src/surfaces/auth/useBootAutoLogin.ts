import { useSessionStore } from "@state/session.store";
import { useEffect, useRef, useState } from "react";
import { fetchAccessMode, requestPreviewGrant } from "./access-api";
import { useAccessStore } from "./access.store";

// Boot access (ADR-057, finding 89). The name is historical: providers.tsx mounts this hook
// where it mounted the Sprint-16 auto-login, which signed every visitor in as admin with a
// development credential compiled into this public bundle. That credential and its
// VITE_AUTO_LOGIN switches are gone; nothing in the bundle can sign anyone in.
//
// A session that holds no access token asks the gateway how to enter (GET /api/v1/auth/mode).
// A reloaded session is one of them: session.store.ts persists the role, never the token.
//   open           -> take a preview grant (POST /api/v1/auth/preview) at the gateway's open
//                     authority, viewer or ops and never higher, and store it exactly as a
//                     sign-in token, in place of any reloaded role;
//   authenticated  -> take nothing; RouteGuard sends an anonymous visitor to /login, and a
//                     reloaded role stays for the refresh gate to renew from its HttpOnly
//                     cookie on the first 401 (FE-INV-023);
//   unreachable    -> take nothing and still open the console, whose surfaces then show
//                     their honest unavailable states; a reloaded role stays as it was.
//
// Attempts start at least REACQUIRE_FLOOR_MS apart, so a gateway that keeps refusing can never
// drive a request loop. A failed attempt, or a session lost while the floor holds, arms one
// timer for the rest of the floor and tries again then, so neither an outage nor a grant lost
// moments after it was issued strands a visitor until a reload. A retry after a failure runs
// behind the open console: it never brings the boot splash back.

/** The shortest interval between two access attempts in one boot. */
export const REACQUIRE_FLOOR_MS = 30_000;

export function useBootAutoLogin(): void {
  // No token, no session: a role on its own is what a reload leaves behind.
  const tokenless = useSessionStore((s) => s.accessToken === null);
  const setAuth = useSessionStore((s) => s.setAuth);
  const setBootAuth = useSessionStore((s) => s.setBootAuth);
  const setAccess = useAccessStore((s) => s.setAccess);
  // StrictMode double-invokes effects; the in-flight latch keeps it to one attempt.
  const inflight = useRef(false);
  const lastAttemptAt = useRef<number | null>(null);
  const lastFailed = useRef(false);
  // A failed attempt and the floor timer each bump this to run the effect again.
  const [wake, setWake] = useState(0);

  // biome-ignore lint/correctness/useExhaustiveDependencies: wake is the re-run trigger, unread
  useEffect(() => {
    if (!tokenless) {
      setBootAuth("settled");
      return;
    }
    if (inflight.current) return;
    const now = Date.now();
    if (lastAttemptAt.current !== null && now < lastAttemptAt.current) {
      // A clock set back since the last attempt restarts the floor instead of stretching it.
      lastAttemptAt.current = now;
    }
    const last = lastAttemptAt.current;
    const rest = last === null ? 0 : last + REACQUIRE_FLOOR_MS - now;
    if (rest <= 0) {
      inflight.current = true;
      lastAttemptAt.current = now;
      if (!lastFailed.current) setBootAuth("pending");
      void (async () => {
        let failed = false;
        try {
          const mode = await fetchAccessMode();
          if (mode.mode === "authenticated") {
            setAccess({ kind: "authenticated" });
            return;
          }
          setAccess({ kind: "open", authority: mode.authority });
          const grant = await requestPreviewGrant();
          setAuth(grant.role, grant.access_token, grant.operator_token_ref, grant.expires_in);
        } catch {
          failed = true;
          // Unreachable gateway or refused grant: the console still opens. A posture already
          // read stays as read; only a posture never read becomes unavailable.
          if (useAccessStore.getState().access.kind === "resolving") {
            setAccess({ kind: "unavailable" });
          }
        } finally {
          inflight.current = false;
          lastFailed.current = failed;
          setBootAuth("settled");
          // Run the effect again: it waits out the rest of the floor, then retries.
          if (failed) setWake((n) => n + 1);
        }
      })();
      return;
    }
    // Inside the floor: one timer for the rest of it, cleared if the effect runs again or the
    // console unmounts first.
    setBootAuth("settled");
    const timer = window.setTimeout(() => setWake((n) => n + 1), rest);
    return () => window.clearTimeout(timer);
  }, [tokenless, wake, setAuth, setBootAuth, setAccess]);
}
