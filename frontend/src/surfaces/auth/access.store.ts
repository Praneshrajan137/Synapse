import { create } from "zustand";

// The gateway's access posture as this console last read it (ADR-057). Not persisted:
// each boot asks GET /api/v1/auth/mode again, so a posture change reaches a visitor on
// their next load. `resolving` until the first answer; `unavailable` when the gateway
// could not be reached and no posture is known.

export type OpenAuthority = "view" | "act";

export type ConsoleAccess =
  | { readonly kind: "resolving" }
  | { readonly kind: "open"; readonly authority: OpenAuthority }
  | { readonly kind: "authenticated" }
  | { readonly kind: "unavailable" };

interface AccessState {
  readonly access: ConsoleAccess;
  setAccess(access: ConsoleAccess): void;
}

export const useAccessStore = create<AccessState>()((set) => ({
  access: { kind: "resolving" },
  setAccess(access) {
    set({ access });
  },
}));
