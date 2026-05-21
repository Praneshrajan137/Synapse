// SYNAPSE FE — Full Jitter retry policy.
// Mirrors ADR-016 (synapse_common.retry). FE applies it to HTTP 5xx and
// transient network errors. 429 is handled separately (honor Retry-After).
// 4xx (other) and 401 short-circuit.

export interface JitterRetryOptions {
  readonly maxAttempts?: number;
  readonly baseMs?: number;
  readonly capMs?: number;
  readonly random?: () => number;
}

const DEFAULTS = {
  maxAttempts: 5,
  baseMs: 200,
  capMs: 30_000,
} as const;

/** Full Jitter backoff: sleep = random_between(0, min(cap, base * 2^attempt)) */
export function fullJitterDelay(
  attempt: number,
  opts: JitterRetryOptions = {},
): number {
  const base = opts.baseMs ?? DEFAULTS.baseMs;
  const cap = opts.capMs ?? DEFAULTS.capMs;
  const rng = opts.random ?? Math.random;
  const exp = Math.min(cap, base * 2 ** attempt);
  return Math.floor(rng() * exp);
}

export interface RetryDecision {
  readonly retry: boolean;
  readonly delayMs: number;
}

/** Decide whether to retry an HTTP response or thrown error. */
export function decideRetry(args: {
  attempt: number;
  status?: number;
  retryAfterHeader?: string | null;
  isNetworkError?: boolean;
  options?: JitterRetryOptions;
}): RetryDecision {
  const { attempt, status, retryAfterHeader, isNetworkError, options } = args;
  const max = options?.maxAttempts ?? DEFAULTS.maxAttempts;
  if (attempt >= max - 1) return { retry: false, delayMs: 0 };

  // 429 — honor Retry-After, then backoff.
  if (status === 429) {
    const wait = parseRetryAfter(retryAfterHeader) ?? fullJitterDelay(attempt, options);
    return { retry: true, delayMs: wait };
  }
  // Transient: 502, 503, 504, and pure network failures.
  if (isNetworkError || (status !== undefined && status >= 500 && status < 600)) {
    return { retry: true, delayMs: fullJitterDelay(attempt, options) };
  }
  // 401 short-circuits to a refresh flow elsewhere; do not retry here.
  // Anything else: no retry.
  return { retry: false, delayMs: 0 };
}

function parseRetryAfter(header: string | null | undefined): number | null {
  if (!header) return null;
  const seconds = Number(header);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.floor(seconds * 1000);
  const date = Date.parse(header);
  if (Number.isFinite(date)) {
    const diff = date - Date.now();
    return diff > 0 ? diff : 0;
  }
  return null;
}

export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
      return;
    }
    const id = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      window.clearTimeout(id);
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
    }
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}
