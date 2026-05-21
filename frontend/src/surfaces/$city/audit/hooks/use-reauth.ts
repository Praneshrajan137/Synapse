/**
 * SYNAPSE Atlas Console — PII reauth hook.
 *
 * Wraps `POST /auth/reauth` (B3). On success, the BFF stamps an
 * `elevated_until` ISO timestamp on the session; the SPA flips a
 * URL param so the Audit Vault knows it can render PII.
 *
 * If the elevated window expires, the next render re-blurs PII.
 */
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError, synapseFetcher } from "@shared/api/fetcher";

interface SessionResponse {
  readonly authenticated: boolean;
  readonly persona: string | null;
  readonly expires_at: string | null;
  readonly elevated_until: string | null;
  readonly claims: Record<string, unknown>;
}

interface ReauthResponse {
  readonly status: string;
  readonly elevated_until: string;
}

export interface UseReauthResult {
  readonly elevated: boolean;
  readonly elevatedUntil: string | null;
  readonly reauth: (password: string) => Promise<void>;
  readonly busy: boolean;
  readonly error: string | null;
}

export function useReauth(): UseReauthResult {
  const session = useQuery({
    queryKey: ["auth-session"],
    queryFn: async ({ signal }) =>
      synapseFetcher<SessionResponse>({
        url: "/auth/session",
        method: "GET",
        signal,
      }),
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const mutation = useMutation({
    mutationFn: async (password: string) =>
      synapseFetcher<ReauthResponse>({
        url: "/auth/reauth",
        method: "POST",
        data: { password },
      }),
    onSuccess: () => session.refetch(),
  });

  const elevatedUntil = session.data?.elevated_until ?? null;
  const elevated =
    elevatedUntil !== null && Date.parse(elevatedUntil) > Date.now();

  return {
    elevated,
    elevatedUntil,
    reauth: async (password) => {
      await mutation.mutateAsync(password);
    },
    busy: mutation.isPending,
    error:
      mutation.error instanceof ApiError && mutation.error.status === 401
        ? "Reauth failed — wrong password."
        : null,
  };
}
