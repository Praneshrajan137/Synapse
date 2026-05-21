import { type PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useSessionStore, type Role } from "@state/session.store";

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
 * Gates a route by role. Anonymous → /login. Authenticated below required
 * role → /. Authenticated and sufficient → renders children.
 */
export function RouteGuard({ minRole, children }: PropsWithChildren<RouteGuardProps>) {
  const role = useSessionStore((s) => s.role);
  const location = useLocation();

  if (role === "anonymous") {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  if (RANK[role] < RANK[minRole]) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
