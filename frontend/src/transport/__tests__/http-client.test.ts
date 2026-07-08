import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { HttpError, NetworkError, type RateLimitError, type SchemaViolationError } from "../errors";
import { createHttpClient } from "../http-client";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function fetchMock(): ReturnType<typeof vi.fn> {
  const mock = vi.fn();
  vi.stubGlobal("fetch", mock);
  return mock;
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// FE-INV-006 + FE-INV-012: HTTP transport keeps JSON canonical and retries only
// at the explicitly idempotent boundary.
describe("createHttpClient", () => {
  it("builds canonical JSON requests with query, auth, and caller headers", async () => {
    const fetch = fetchMock();
    fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));
    const client = createHttpClient({
      baseUrl: "https://api.synapse.test///",
      getAccessToken: () => "access-token",
      defaultHeaders: { "X-Default": "default" },
    });

    const result = await client.post(
      "orders",
      { z: 3, a: 1 },
      {
        query: { city: "bengaluru", absent: undefined, page: 2, live: false },
        headers: { "X-Request-Id": "req-1" },
        schema: z.object({ ok: z.boolean() }),
      },
    );

    expect(result).toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.synapse.test/orders?city=bengaluru&page=2&live=false");
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1,"z":3}');
    expect(init.credentials).toBe("include");
    const headers = init.headers as Headers;
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(headers.get("X-Default")).toBe("default");
    expect(headers.get("X-Request-Id")).toBe("req-1");
  });

  it("returns undefined for 204 responses without parsing a body", async () => {
    const fetch = fetchMock();
    fetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

    await expect(client.get("/empty")).resolves.toBeUndefined();
  });

  it("runs the auth-expired hook once and then raises the 401", async () => {
    const fetch = fetchMock();
    const onAuthExpired = vi.fn();
    fetch.mockResolvedValueOnce(new Response("nope", { status: 401, statusText: "Unauthorized" }));
    const client = createHttpClient({
      baseUrl: "https://api.synapse.test",
      onAuthExpired,
    });

    await expect(client.get("/secure")).rejects.toBeInstanceOf(HttpError);
    expect(onAuthExpired).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("retries 429 for idempotent reads and preserves Retry-After on terminal writes", async () => {
    vi.useFakeTimers();
    const fetch = fetchMock();
    fetch
      .mockResolvedValueOnce(
        new Response("wait", {
          status: 429,
          statusText: "Too Many Requests",
          headers: { "Retry-After": "0" },
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ recovered: true }));
    const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

    const read = client.get("/limited");
    await vi.runAllTimersAsync();
    await expect(read).resolves.toEqual({ recovered: true });
    expect(fetch).toHaveBeenCalledTimes(2);

    fetch.mockReset();
    fetch.mockResolvedValueOnce(
      new Response("still limited", {
        status: 429,
        statusText: "Too Many Requests",
        headers: { "Retry-After": "2" },
      }),
    );

    await expect(client.post("/limited", { write: true })).rejects.toMatchObject({
      name: "RateLimitError",
      retryAfterMs: 2_000,
      bodyText: "still limited",
    } satisfies Partial<RateLimitError>);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("retries transient network failures for GET but not non-idempotent POST", async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0);
    const fetch = fetchMock();
    fetch
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(jsonResponse({ ok: 1 }));
    const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

    const read = client.get("/network");
    await vi.runAllTimersAsync();
    await expect(read).resolves.toEqual({ ok: 1 });
    expect(fetch).toHaveBeenCalledTimes(2);

    fetch.mockReset();
    fetch.mockRejectedValueOnce(new TypeError("offline"));
    await expect(client.post("/network", { mutate: true })).rejects.toBeInstanceOf(NetworkError);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("rejects schema-invalid responses before callers can consume them", async () => {
    const fetch = fetchMock();
    fetch.mockResolvedValueOnce(jsonResponse({ ok: "yes" }));
    const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

    await expect(
      client.get("/typed", { schema: z.object({ ok: z.boolean() }), schemaId: "typed.v1" }),
    ).rejects.toMatchObject({
      name: "SchemaViolationError",
      schemaId: "typed.v1",
    } satisfies Partial<SchemaViolationError>);
  });

  // Req 7.6 / FE-INV-026: a hung run must be rejected with a typed timeout, not
  // retried forever, once the deadline elapses.
  it("rejects a hung request with a typed TimeoutError when the deadline elapses", async () => {
    vi.useFakeTimers();
    const fetch = fetchMock();
    // A never-resolving fetch that only rejects when its signal aborts — the
    // shape of a genuinely hung request.
    fetch.mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        const signal = init.signal as AbortSignal;
        signal.addEventListener("abort", () => {
          reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
        });
      });
    });
    const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

    const run = client.post("/simulate", { n: 1 }, { idempotent: true, timeoutMs: 120_000 });
    const assertion = expect(run).rejects.toMatchObject({
      name: "TimeoutError",
      timeoutMs: 120_000,
    });
    await vi.advanceTimersByTimeAsync(120_000);
    await assertion;
    // A hung run is aborted, never retried into a second attempt.
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("does not time out a request that resolves within the deadline", async () => {
    vi.useFakeTimers();
    const fetch = fetchMock();
    fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));
    const client = createHttpClient({ baseUrl: "https://api.synapse.test" });

    const run = client.post(
      "/simulate",
      { n: 1 },
      { idempotent: true, timeoutMs: 120_000, schema: z.object({ ok: z.boolean() }) },
    );
    await vi.runAllTimersAsync();
    await expect(run).resolves.toEqual({ ok: true });
  });

  it("propagates a caller abort as an AbortError, not a TimeoutError", async () => {
    const fetch = fetchMock();
    fetch.mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        const signal = init.signal as AbortSignal;
        signal.addEventListener("abort", () => {
          reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
        });
      });
    });
    const client = createHttpClient({ baseUrl: "https://api.synapse.test" });
    const ac = new AbortController();

    const run = client.post(
      "/simulate",
      { n: 1 },
      { idempotent: true, timeoutMs: 120_000, signal: ac.signal },
    );
    const assertion = expect(run).rejects.toMatchObject({ name: "AbortError" });
    ac.abort();
    await assertion;
  });
});
