import { HttpError } from "./errors";

// Single-flight refresh: many concurrent calls hit 401 simultaneously, but
// we only fire one /refresh and replay the others against the new token.
// FE-INV-023 — JWT refresh recovers from 401 without page reload.

export interface RefreshGate {
  withRefreshRetry<T>(call: () => Promise<T>, refresh: () => Promise<void>): Promise<T>;
}

export function createRefreshGate(): RefreshGate {
  let inflight: Promise<void> | null = null;

  return {
    async withRefreshRetry<T>(call, refresh) {
      try {
        return await call();
      } catch (err) {
        if (!(err instanceof HttpError) || err.status !== 401) throw err;
        if (!inflight) {
          inflight = refresh().finally(() => {
            inflight = null;
          });
        }
        await inflight;
        // Single retry only — if it 401s again, propagate.
        return await call();
      }
    },
  };
}
