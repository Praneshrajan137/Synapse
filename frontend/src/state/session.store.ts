import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

// Operator session state.
// JWT access token lives in memory only (security — STRIDE). Refresh token
// is held in an HttpOnly cookie set by the gateway. Persisted fields are
// limited to non-sensitive UI preferences.

export type Role = "viewer" | "ops" | "engineer" | "admin" | "anonymous";

interface SessionState {
  readonly role: Role;
  readonly operatorTokenRef: string | null;
  readonly accessToken: string | null;
  readonly tokenExpiresAt: number | null;
  setAuth(
    role: Role,
    accessToken: string,
    operatorTokenRef: string | null,
    expiresInSeconds: number,
  ): void;
  rotateAccessToken(accessToken: string, expiresInSeconds: number): void;
  clearAuth(): void;
}

interface PersistedPrefs {
  role: Role;
  operatorTokenRef: string | null;
}

export const useSessionStore = create<SessionState>()(
  persist<SessionState, [], [], PersistedPrefs>(
    (set) => ({
      role: "anonymous",
      operatorTokenRef: null,
      accessToken: null,
      tokenExpiresAt: null,
      setAuth(role, accessToken, operatorTokenRef, expiresInSeconds) {
        set({
          role,
          accessToken,
          operatorTokenRef,
          tokenExpiresAt: Date.now() + expiresInSeconds * 1000,
        });
      },
      rotateAccessToken(accessToken, expiresInSeconds) {
        set({
          accessToken,
          tokenExpiresAt: Date.now() + expiresInSeconds * 1000,
        });
      },
      clearAuth() {
        set({
          role: "anonymous",
          accessToken: null,
          operatorTokenRef: null,
          tokenExpiresAt: null,
        });
      },
    }),
    {
      name: "synapse.session",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (s) => ({ role: s.role, operatorTokenRef: s.operatorTokenRef }),
    },
  ),
);
