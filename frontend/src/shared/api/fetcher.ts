/**
 * SYNAPSE Atlas Console — Orval HTTP fetcher.
 *
 * Every Orval-generated React Query hook delegates here. Centralised so
 * we can enforce the project's three contracts in one place:
 *
 *   1. **BFF cookie session** — `credentials: "include"` so the
 *      `synapse_session` HttpOnly cookie travels with every request
 *      (ADR-027). The browser never touches the JWT itself.
 *
 *   2. **CSRF double-submit** — on mutating methods, attach the latest
 *      `X-CSRF` token returned by `/auth/login` or `/auth/refresh`. The
 *      token lives in module-private memory; never stored in localStorage
 *      where XSS could read it.
 *
 *   3. **Canonical JSON for cache-stable payloads** — POSTs to /a2a and
 *      /api/v1/decisions go through `canonicalize()` (mirrors backend
 *      I-13 / ADR-021). The orval config wraps `submitDecision`'s body
 *      with this; other endpoints fall through to JSON.stringify.
 *
 * Errors:
 *   - Non-2xx responses throw an `ApiError` with the parsed body.
 *   - Network failures throw an `ApiError` with `kind: "network"`.
 *   - Aborts propagate through Orval's signal as a normal AbortError.
 */
import { canonicalize } from "@shared/canonical-json";

/** Endpoints that MUST send canonical JSON (KV-cache prefix stability). */
const CANONICAL_PATHS = ["/a2a", "/api/v1/decisions"] as const;

/** Mutating verbs that must include the CSRF header. */
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

let csrfToken: string | null = null;

/** Set after /auth/login resolves. The router also calls this on /auth/refresh. */
export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

/** Orval mutator signature. Generic over response payload. */
export interface SynapseFetcherConfig {
  url: string;
  method: string;
  params?: Record<string, unknown> | undefined;
  data?: unknown;
  responseType?: "json" | "text" | "blob" | "stream" | undefined;
  headers?: Record<string, string> | undefined;
  signal?: AbortSignal | undefined;
}

export class ApiError<T = unknown> extends Error {
  readonly kind: "http" | "network" | "abort";
  readonly status: number;
  readonly body: T | string | null;

  constructor(args: { kind: ApiError["kind"]; status: number; body: T | string | null; message: string }) {
    super(args.message);
    this.name = "ApiError";
    this.kind = args.kind;
    this.status = args.status;
    this.body = args.body;
  }
}

function buildUrl(url: string, params?: Record<string, unknown>): string {
  if (!params || Object.keys(params).length === 0) return url;
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) for (const x of v) search.append(k, String(x));
    else search.append(k, String(v));
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

function shouldCanonicalize(url: string): boolean {
  return CANONICAL_PATHS.some((p) => url.startsWith(p));
}

export async function synapseFetcher<T>(config: SynapseFetcherConfig): Promise<T> {
  const method = config.method.toUpperCase();
  const url = buildUrl(config.url, config.params);

  const headers = new Headers({
    Accept: "application/json",
    ...config.headers,
  });

  let body: BodyInit | undefined;
  if (config.data !== undefined && config.data !== null) {
    if (config.data instanceof FormData || config.data instanceof Blob) {
      body = config.data;
    } else {
      headers.set("Content-Type", "application/json");
      body = shouldCanonicalize(url)
        ? canonicalize(config.data)
        : JSON.stringify(config.data);
    }
  }

  if (MUTATING_METHODS.has(method) && csrfToken) {
    headers.set("X-CSRF", csrfToken);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body,
      credentials: "include",
      signal: config.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError({
      kind: "network",
      status: 0,
      body: null,
      message: `network error: ${err instanceof Error ? err.message : String(err)}`,
    });
  }

  // 204 No Content — Orval's typing tolerates undefined for void responses.
  if (response.status === 204) return undefined as unknown as T;

  const contentType = response.headers.get("Content-Type") ?? "";
  let parsed: unknown = null;
  if (contentType.includes("application/json")) {
    parsed = await response.json().catch(() => null);
  } else if (config.responseType === "text" || contentType.startsWith("text/")) {
    parsed = await response.text().catch(() => null);
  } else if (config.responseType === "blob") {
    parsed = await response.blob().catch(() => null);
  } else {
    parsed = await response.text().catch(() => null);
  }

  if (!response.ok) {
    throw new ApiError({
      kind: "http",
      status: response.status,
      body: parsed as T | string | null,
      message: `${method} ${url} failed (${response.status})`,
    });
  }

  return parsed as T;
}
