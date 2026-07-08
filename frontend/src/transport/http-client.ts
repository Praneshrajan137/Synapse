import { decideRetry, sleep } from "@lib/jitter-retry";
import { canonicalJson } from "@lib/json-canonical";
import { log } from "@lib/log";
import type { ZodSchema, ZodTypeAny, ZodTypeDef } from "zod";
import {
  HttpError,
  NetworkError,
  RateLimitError,
  SchemaViolationError,
  TimeoutError,
} from "./errors";

// Typed HTTP client.
// - Canonical JSON outbound (FE-INV-012 / I-8).
// - Full-Jitter retry on 5xx + network (FE-INV-006 / ADR-016).
// - Retry-After honored on 429 (ADR-017).
// - Bearer token injected from a getter (memory only — never localStorage).
// - Zod schema parse on response when provided (FE-INV-002 / I-3).

export interface HttpClientConfig {
  readonly baseUrl: string;
  readonly getAccessToken?: (() => string | null) | undefined;
  readonly onAuthExpired?: (() => Promise<void> | void) | undefined;
  readonly defaultHeaders?: Readonly<Record<string, string>> | undefined;
}

export interface RequestOptions<T> {
  readonly method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  readonly path: string;
  readonly query?: Readonly<Record<string, string | number | boolean | undefined>>;
  readonly body?: unknown;
  readonly headers?: Readonly<Record<string, string>>;
  readonly signal?: AbortSignal;
  // Output type must be `T`; the input type is left open so schemas with
  // `.default()`/transforms (input ≠ output) still satisfy the constraint.
  readonly schema?: ZodSchema<T, ZodTypeDef, unknown>;
  readonly idempotent?: boolean;
  readonly schemaId?: string;
  /**
   * Overall wall-clock deadline (ms) for the request, spanning every retry.
   * When the deadline elapses the in-flight fetch is aborted and a typed
   * `TimeoutError` is thrown so callers can reject a hung run rather than wait
   * forever (Req 7.6 — Twin Lab's ≤120s Tier-4 SLA). Omitted → no deadline.
   */
  readonly timeoutMs?: number;
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

  // Overall wall-clock deadline across every retry (Req 7.6). Each attempt gets
  // its own AbortController, linked to any caller-supplied signal, plus a timer
  // scoped to the remaining budget. A fired timer aborts the in-flight fetch
  // and surfaces a typed TimeoutError (distinct from a caller abort).
  const deadline = opts.timeoutMs != null ? Date.now() + opts.timeoutMs : null;

  let attempt = 0;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const controller = new AbortController();
    let timedOut = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const external = opts.signal;
    const onExternalAbort = () => controller.abort();
    if (external) {
      if (external.aborted) controller.abort();
      else external.addEventListener("abort", onExternalAbort, { once: true });
    }

    if (deadline != null) {
      const remaining = deadline - Date.now();
      if (remaining <= 0) {
        if (external) external.removeEventListener("abort", onExternalAbort);
        throw new TimeoutError(url, opts.timeoutMs as number);
      }
      timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, remaining);
    }

    try {
      const res = await fetch(url, {
        method,
        headers,
        body: bodyString ?? null,
        credentials: "include",
        signal: controller.signal,
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
      // A fired deadline surfaces as a typed TimeoutError, never as a retryable
      // network blip — a hung run must be rejected, not retried forever.
      if (timedOut) throw new TimeoutError(url, opts.timeoutMs as number);
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
    } finally {
      if (timer) clearTimeout(timer);
      if (external) external.removeEventListener("abort", onExternalAbort);
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
    const issues = result.error.issues.map((i) => ({ path: i.path, message: i.message }));
    // Fail-closed: emit a FIELD-WHITELISTED telemetry event and throw a typed
    // SchemaViolationError (FE-INV-002/030, Req 1.2 / 14.2). Consumers route
    // this to the `error` Universal_State; the unvalidated `raw` payload is
    // NEVER rendered and NEVER forwarded in telemetry (it may carry sensitive
    // data). Only the schema id, issue count, and the dotted field paths of
    // each violation leave the client — no field values, no raw body.
    emitSchemaViolationTelemetry(schemaId, issues);
    throw new SchemaViolationError(schemaId, issues, raw);
  }
  return result.data as T;
}

/**
 * Whitelisted schema-violation telemetry. Only these fields are forwarded:
 * `kind`, `error`, `schemaId`, `issueCount`, and `paths` (the dotted field
 * path of each issue). The raw payload and any field values are deliberately
 * excluded so no unvalidated/possibly-sensitive data escapes (Req 14.2).
 */
function emitSchemaViolationTelemetry(
  schemaId: string,
  issues: ReadonlyArray<{ path: ReadonlyArray<string | number>; message: string }>,
): void {
  try {
    log({
      kind: "error",
      error: "schema_violation",
      schemaId,
      issueCount: issues.length,
      paths: issues.map((i) => i.path.join(".")),
    });
  } catch {
    /* telemetry must never mask the original schema violation */
  }
}
