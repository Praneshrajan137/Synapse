import { z } from "zod";

/**
 * Minimal JWKS client (WS-4 §4c).
 *
 * Surfaces the backend's `/api/v1/auth/.well-known/jwks.json` to the
 * frontend so the FE has a concrete handle on the active key set when a
 * 401 occurs. Today the FE relies blindly on the access token; this
 * primitive gives us:
 *
 *   1. Visibility — on 401 we fetch the JWKS once and log the active key
 *      ids; if the kid we last saw is no longer present, the backend
 *      rotated and our cached token is genuinely invalid (not a network
 *      blip).
 *   2. A migration handle — future sprints can move to full client-side
 *      signature verification using one of the published JWK entries
 *      without touching the request path.
 *
 * Full signature verification is intentionally out-of-scope for this PR
 * — it would need an additional dependency (jose / @noble/jwts) and a
 * worker thread to keep the main loop free. Marked as a known follow-up.
 */

export const JwkSchema = z
  .object({
    kty: z.string(),
    kid: z.string().optional(),
    use: z.string().optional(),
    alg: z.string().optional(),
    n: z.string().optional(),
    e: z.string().optional(),
    x: z.string().optional(),
    y: z.string().optional(),
    crv: z.string().optional(),
  })
  .passthrough();

export const JwksResponseSchema = z.object({
  keys: z.array(JwkSchema),
});

export type Jwks = z.infer<typeof JwksResponseSchema>;

type CacheEntry = {
  fetchedAt: number;
  jwks: Jwks;
};

const TTL_MS = 5 * 60_000; // 5 minutes — matches refresh-token cadence.

const cache = new Map<string, CacheEntry>();

export async function fetchJwks(baseUrl: string): Promise<Jwks> {
  const url = `${baseUrl.replace(/\/+$/, "")}/api/v1/auth/.well-known/jwks.json`;
  const now = Date.now();
  const cached = cache.get(url);
  if (cached && now - cached.fetchedAt < TTL_MS) return cached.jwks;

  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    // Do not throw — JWKS is advisory. Return the prior cache if any.
    if (cached) return cached.jwks;
    return { keys: [] };
  }
  const raw = (await res.json()) as unknown;
  const parsed = JwksResponseSchema.safeParse(raw);
  if (!parsed.success) {
    if (cached) return cached.jwks;
    return { keys: [] };
  }
  cache.set(url, { fetchedAt: now, jwks: parsed.data });
  return parsed.data;
}

export function knownKids(jwks: Jwks): string[] {
  return jwks.keys.map((k) => k.kid).filter((k): k is string => Boolean(k));
}

export function invalidateJwksCache(): void {
  cache.clear();
}
