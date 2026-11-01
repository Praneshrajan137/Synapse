import { type Role, useSessionStore } from "@state/session.store";
import { AccessBadge } from "@surfaces/auth/AccessBadge";
import { InsufficientAuthority } from "@surfaces/auth/InsufficientAuthority";
import { useAccessStore } from "@surfaces/auth/access.store";
import type { PropsWithChildren } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useLocation } from "react-router-dom";

const RANK: Record<Role, number> = {
  anonymous: 0,
  viewer: 10,
  ops: 20,
  engineer: 30,
  admin: 40,
};

interface RouteGuardProps {
  readonly minRole: Role;
}

/**
 * Gates a route by role (ADR-057).
 *
 * - While boot access is in flight an anonymous session sees a minimal splash, never a
 *   /login flash.
 * - An anonymous session goes to /login only when the gateway requires sign-in.
 * - Otherwise the console OPENS: an anonymous visitor (gateway unreachable, or a refused
 *   preview grant) reads every viewer surface, and each surface shows its own honest
 *   unavailable state.
 * - A session below the route's role sees an insufficient-authority state that says why,
 *   never a redirect.
 *
 * Every guarded surface carries the open-mode access badge.
 */
export function RouteGuard({ minRole, children }: PropsWithChildren<RouteGuardProps>) {
  const role = useSessionStore((s) => s.role);
  const bootAuth = useSessionStore((s) => s.bootAuth);
  const accessKind = useAccessStore((s) => s.access.kind);
  const location = useLocation();
  const { t } = useTranslation("common");

  if (role === "anonymous" && bootAuth !== "settled") {
    return (
      <output
        aria-live="polite"
        className="grid min-h-screen place-items-center bg-canvas text-sm text-ink-muted"
      >
        {t("auth.signing_in")}
      </output>
    );
  }
  if (role === "anonymous" && accessKind === "authenticated") {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  const held = role === "anonymous" ? RANK.viewer : RANK[role];
  if (held < RANK[minRole]) {
    return (
      <>
        <InsufficientAuthority required={minRole} />
        <AccessBadge />
      </>
    );
  }
  return (
    <>
      {children}
      <AccessBadge />
    </>
  );
}
