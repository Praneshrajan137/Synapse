/**
 * SYNAPSE Atlas Console — login route.
 *
 * Talks to the BFF (`POST /auth/login`). On success, the gateway returns
 * a Set-Cookie + the CSRF token; we stash the CSRF in
 * `setCsrfToken` (in-memory) and redirect to the requested-city home.
 *
 * Auth gating of other routes is enforced server-side by SessionMiddleware
 * (a 401 on protected paths). The router's `beforeLoad` for the city
 * layout sniffs `/auth/session` to redirect unauthenticated visitors
 * here.
 */
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";
import { ApiError, setCsrfToken, synapseFetcher } from "@shared/api/fetcher";

interface LoginResponse {
  readonly persona: string;
  readonly csrf_token: string;
  readonly expires_at: string;
  readonly claims: Record<string, unknown>;
}

export const Route = createFileRoute("/login")({
  component: LoginRoute,
});

function LoginRoute() {
  const { t } = useTranslation();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await synapseFetcher<LoginResponse>({
        url: "/auth/login",
        method: "POST",
        data: { username, password },
      });
      setCsrfToken(r.csrf_token);
      await router.navigate({ to: "/$city/", params: { city: "bengaluru" } });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t("auth.errors.invalid"));
      } else {
        setError(t("common.error"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm py-12">
      <Card>
        <CardHeader>
          <CardTitle>{t("auth.signIn")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-3" noValidate>
            <label className="block">
              <span className="mb-1 block text-ops-sm text-muted-fg">
                {t("auth.username")}
              </span>
              <input
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-md border border-border bg-bg px-3 py-2 text-ops-base text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-ops-sm text-muted-fg">
                {t("auth.password")}
              </span>
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-border bg-bg px-3 py-2 text-ops-base text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>

            {error && (
              <div role="alert" className="text-ops-sm text-safety-critical">
                {error}
              </div>
            )}

            <Button type="submit" disabled={busy} className="w-full">
              {busy ? t("common.loading") : t("auth.submit")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
