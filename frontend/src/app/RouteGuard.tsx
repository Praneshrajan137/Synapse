import { type Role, useSessionStore } from "@state/session.store";
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
 * Gates a route by role. While the Sprint-16 boot auto-login is in flight
 * an anonymous session sees a minimal splash (never a /login flash);
 * a settled anonymous session → /login (the fallback surface).
 * Authenticated below required role → /. Sufficient → renders children.
 */
export function RouteGuard({ minRole, children }: PropsWithChildren<RouteGuardProps>) {
  const role = useSessionStore((s) => s.role);
  const bootAuth = useSessionStore((s) => s.bootAuth);
  const location = useLocation();
  const { t } = useTranslation("common");

  if (role === "anonymous") {
    if (bootAuth !== "settled") {
      return (
        <output
          aria-live="polite"
          className="grid min-h-screen place-items-center bg-canvas text-sm text-ink-muted"
        >
          {t("auth.signing_in")}
        </output>
      );
    }
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  if (RANK[role] < RANK[minRole]) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
