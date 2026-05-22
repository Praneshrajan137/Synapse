import { Button } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { type Role, useSessionStore } from "@state/session.store";
import { HttpError } from "@transport/errors";
import { type FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

const DEFAULT_ROUTES: Record<Role, string> = {
  anonymous: "/login",
  viewer: "/",
  ops: "/cockpit",
  engineer: "/",
  admin: "/",
};

/**
 * Operator login. Posts to /api/v1/auth/login; stores access token in
 * memory; refresh token is set as an HttpOnly cookie by the BE. Redirects
 * the operator to the highest-utility route for their role unless a
 * `from` location was preserved by RouteGuard.
 */
export function Login() {
  const api = useSynapseApi();
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useSessionStore((s) => s.setAuth);
  const currentRole = useSessionStore((s) => s.role);

  const [operatorId, setOperatorId] = useState("ops@synapse.local");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  if (currentRole !== "anonymous") {
    return <Navigate to={DEFAULT_ROUTES[currentRole]} replace />;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    try {
      const res = await api.login({ operator_id: operatorId, password });
      setAuth(res.role as Role, res.access_token, res.operator_token_ref, res.expires_in);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? DEFAULT_ROUTES[res.role as Role], { replace: true });
    } catch (err) {
      const message =
        err instanceof HttpError && err.status === 401
          ? "Invalid credentials"
          : err instanceof Error
            ? err.message
            : "Login failed";
      toast.error(message);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-canvas p-6">
      <form
        onSubmit={onSubmit}
        className="syn-card-raised w-full max-w-sm space-y-4 p-6"
        aria-label="Operator sign-in"
      >
        <header className="space-y-1">
          <h1 className="text-xl font-semibold text-ink">SYNAPSE Console</h1>
          <p className="text-xs text-ink-muted">
            Sign in with your operator credentials. Your refresh token lives in an HttpOnly cookie;
            nothing operator-identifying is logged client-side (FE-INV-019).
          </p>
        </header>
        <label className="block text-sm">
          <span className="block text-2xs uppercase tracking-wide text-ink-muted">Operator ID</span>
          <input
            type="email"
            required
            autoComplete="username"
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            className="mt-1 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-ink focus-visible:shadow-focus focus-visible:outline-none"
          />
        </label>
        <label className="block text-sm">
          <span className="block text-2xs uppercase tracking-wide text-ink-muted">Password</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-ink focus-visible:shadow-focus focus-visible:outline-none"
          />
        </label>
        <Button type="submit" variant="primary" size="lg" disabled={pending} className="w-full">
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </main>
  );
}
