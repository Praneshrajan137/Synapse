import { Button } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { type Role, useSessionStore } from "@state/session.store";
import { HttpError } from "@transport/errors";
import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAccessStore } from "./access.store";

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
 *
 * ADR-057: while the gateway runs open, sign-in is dormant (the gateway answers
 * /api/v1/auth/login with 404), so this page says so instead of offering a form
 * that cannot work. No operator id or password is prefilled: the bundle is public.
 */
export function Login() {
  const api = useSynapseApi();
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useSessionStore((s) => s.setAuth);
  const currentRole = useSessionStore((s) => s.role);
  const access = useAccessStore((s) => s.access);
  const { t } = useTranslation("auth");
  const { t: tc } = useTranslation("common");

  const [operatorId, setOperatorId] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  // Sign-in errors are associated with the credential inputs (Req 9.7) so
  // assistive tech conveys the failure, in addition to the transient toast.
  const [error, setError] = useState<string | null>(null);
  const errorId = useId();
  const dormantId = useId();

  if (currentRole !== "anonymous") {
    return <Navigate to={DEFAULT_ROUTES[currentRole]} replace />;
  }

  if (access.kind === "resolving") {
    return (
      <output
        aria-live="polite"
        className="grid min-h-screen place-items-center bg-canvas text-sm text-ink-muted"
      >
        {tc("auth.signing_in")}
      </output>
    );
  }

  if (access.kind === "open") {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas p-6">
        <section
          aria-labelledby={dormantId}
          className="syn-card-raised w-full max-w-sm space-y-3 p-6"
        >
          <h1 id={dormantId} className="text-xl font-semibold text-ink">
            {t("login.dormant_title")}
          </h1>
          <p className="text-sm text-ink-muted">{t("login.dormant_body")}</p>
          <Link to="/" className="inline-block text-sm font-medium text-accent hover:underline">
            {t("login.dormant_open")}
          </Link>
        </section>
      </main>
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
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
      setError(message);
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
            aria-invalid={error !== null}
            aria-describedby={error ? errorId : undefined}
            className="mt-1 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-ink focus-visible:shadow-focus focus-visible:outline-none aria-[invalid=true]:border-signal-danger"
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
            aria-invalid={error !== null}
            aria-describedby={error ? errorId : undefined}
            className="mt-1 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-ink focus-visible:shadow-focus focus-visible:outline-none aria-[invalid=true]:border-signal-danger"
          />
        </label>
        {error && (
          <div id={errorId} role="alert" className="text-xs text-confidence-risk">
            {error}
          </div>
        )}
        <Button type="submit" variant="primary" size="lg" disabled={pending} className="w-full">
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </main>
  );
}
