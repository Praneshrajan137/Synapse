// Typed transport errors. The FE differentiates these in error boundaries
// and telemetry; never throws bare `Error`.

export class HttpError extends Error {
  override readonly name: string = "HttpError";
  constructor(
    readonly status: number,
    readonly statusText: string,
    readonly url: string,
    readonly bodyText?: string,
  ) {
    super(`${status} ${statusText} (${url})`);
  }
}

export class NetworkError extends Error {
  override readonly name = "NetworkError";
  constructor(
    readonly url: string,
    override readonly cause?: unknown,
  ) {
    super(`Network failure: ${url}`);
  }
}

export class SchemaViolationError extends Error {
  override readonly name = "SchemaViolationError";
  constructor(
    readonly schemaId: string,
    readonly issues: ReadonlyArray<{ path: ReadonlyArray<string | number>; message: string }>,
    readonly raw: unknown,
  ) {
    super(`Schema violation: ${schemaId} (${issues.length} issue(s))`);
  }
}

export class RateLimitError extends HttpError {
  override readonly name = "RateLimitError";
  constructor(
    status: number,
    statusText: string,
    url: string,
    readonly retryAfterMs: number | null,
    bodyText?: string,
  ) {
    super(status, statusText, url, bodyText);
  }
}
