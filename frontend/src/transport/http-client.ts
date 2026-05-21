import { canonicalJson } from "@lib/json-canonical";
import { decideRetry, sleep } from "@lib/jitter-retry";
import { HttpError, NetworkError, RateLimitError, SchemaViolationError } from "./errors";
import type { ZodSchema, ZodTypeAny } from "zod";

// Typed HTTP client.
// - Canonical JSON outbound (FE-INV-012 / I-8).
// - Full-Jitter retry on 5xx + network (FE-INV-006 / ADR-016).
// - Retry-After honored on 429 (ADR-017).
// - Bearer token injected from a getter (memory only — never localStorage).
// - Zod schema parse on response when provided (FE-INV-002 / I-3).

export interface HttpClientConfig {
  readonly baseUrl: string;
  readonly getAccessToken?: () => string | null;
  readonly onAuthExpired?: () => Promise<void> | void;
  readonly defaultHeaders?: Readonly<Record<string, string>>;
}

export interface RequestOptions<T> {
  readonly method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  readonly path: string;
  readonly query?: Readonly<Record<string, string | number | boolean | undefined>>;
  readonly body?: unknown;
  readonly headers?: Readonly<Record<string, string>>;
  readonly signal?: AbortSignal;
  readonly schema?: ZodSchema<T>;
  readonly idempotent?: boolean;
  readonly schemaId?: string;
}

const RETRYABLE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "PUT", "DELETE"]);

export function createHttpClient(config: HttpClientConfig) {
  const base = config.baseUrl.replace(/\/+$/, "");
  return {
    request: <T = unknown>(opts: RequestOptions<T>) => request<T>(base, config, opts),
    get: <T = unknown>(path: string, opts: Omit<RequestOptions<T>, "method" | "path"> = {}) =>
      request<T>(base, config, { ...opts, method: "GET", path }),
    post: <T = unknown>(
      path: string,
      body?: unknown,
      opts: Omit<RequestOptions<T>, "method" | "path" | "body"> = {},
    ) => request<T>(base, config, { ...opts, method: "POST", path, body }),
  };
}

async function request<T>(
  base: string,
  config: HttpClientConfig,
  opts: RequestOptions<T>,
): Promise<T> {
  const url = buildUrl(base, opts.path, opts.query);
  const method = opts.method ?? "GET";
  const canRetry = opts.idempotent ?? RETRYABLE_METHODS.has(method);

  const headers = new Headers({
    Accept: "application/json",
    ...(config.defaultHeaders ?? {}),
    ...(opts.headers ?? {}),
  });

  let bodyString: string | undefined;
  if (opts.body !== undefined) {
    headers.set("Content-Type", "application/json");
    bodyString = canonicalJson(opts.body);
  }

  const token = config.getAccessToken?.();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let attempt = 0;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      const res = await fetch(url, {
        method,
        headers,
        body: bodyString,
        credentials: "include",
        signal: opts.signal,
      });

      if (res.status === 401) {
        await config.onAuthExpired?.();
        throw new HttpError(401, "Unauthorized", url);
      }

      if (res.status === 429) {
        const ra = res.headers.get("Retry-After");
        if (canRetry) {
          const decision = decideRetry({
            attempt,
            status: 429,
            retryAfterHeader: ra,
          });
          if (decision.retry) {
            await sleep(decision.delayMs, opts.signal);
            attempt += 1;
            continue;
          }
        }
        const bodyText = await safeText(res);
        const retryAfterMs = parseRetryAfterMs(ra);
        throw new RateLimitError(429, res.statusText, url, retryAfterMs, bodyText);
      }

      if (!res.ok) {
        if (canRetry) {
          const decision = decideRetry({ attempt, status: res.status });
          if (decision.retry) {
            await sleep(decision.delayMs, opts.signal);
            attempt += 1;
            continue;
          }
        }
        const bodyText = await safeText(res);
        throw new HttpError(res.status, res.statusText, url, bodyText);
      }

      if (res.status === 204) {
        return undefined as unknown as T;
      }

      const json = (await res.json()) as unknown;
      if (opts.schema) {
        return parseWithSchema(opts.schema, json, opts.schemaId ?? opts.path);
      }
      return json as T;
    } catch (err) {
      if (err instanceof HttpError || err instanceof SchemaViolationError) throw err;
      if ((err as Error)?.name === "AbortError") throw err;
      if (canRetry) {
        const decision = decideRetry({ attempt, isNetworkError: true });
        if (decision.retry) {
          await sleep(decision.delayMs, opts.signal);
          attempt += 1;
          continue;
        }
      }
      throw new NetworkError(url, err);
    }
  }
}

function buildUrl(
  base: string,
  path: string,
  query: Readonly<Record<string, string | number | boolean | undefined>> | undefined,
): string {
  const cleaned = path.startsWith("/") ? path : `/${path}`;
  if (!query) return `${base}${cleaned}`;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined) params.append(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${base}${cleaned}?${qs}` : `${base}${cleaned}`;
}

async function safeText(res: Response): Promise<string | undefined> {
  try {
    return await res.text();
  } catch {
    return undefined;
  }
}

function parseRetryAfterMs(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.floor(seconds * 1000);
  const ts = Date.parse(value);
  return Number.isFinite(ts) ? Math.max(0, ts - Date.now()) : null;
}

function parseWithSchema<T>(schema: ZodTypeAny, raw: unknown, schemaId: string): T {
  const result = schema.safeParse(raw);
  if (!result.success) {
    throw new SchemaViolationError(
      schemaId,
      result.error.issues.map((i) => ({ path: i.path, message: i.message })),
      raw,
    );
  }
  return result.data as T;
}
