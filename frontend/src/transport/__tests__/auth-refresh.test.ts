import { describe, expect, it, vi } from "vitest";
import { createRefreshGate } from "@transport/auth-refresh";
import { HttpError } from "@transport/errors";

// FE-INV-023 — single-flight refresh recovers from 401 without page reload.
describe("createRefreshGate", () => {
  it("retries the call once after a successful refresh", async () => {
    const gate = createRefreshGate();
    const call = vi.fn();
    call
      .mockRejectedValueOnce(new HttpError(401, "Unauthorized", "/x"))
      .mockResolvedValueOnce({ ok: true });
    const refresh = vi.fn().mockResolvedValue(undefined);

    const result = await gate.withRefreshRetry(call, refresh);
    expect(result).toEqual({ ok: true });
    expect(call).toHaveBeenCalledTimes(2);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("propagates non-401 errors without refreshing", async () => {
    const gate = createRefreshGate();
    const call = vi.fn().mockRejectedValue(new HttpError(500, "boom", "/x"));
    const refresh = vi.fn();

    await expect(gate.withRefreshRetry(call, refresh)).rejects.toBeInstanceOf(HttpError);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("does not loop: a second 401 propagates", async () => {
    const gate = createRefreshGate();
    const call = vi
      .fn()
      .mockRejectedValueOnce(new HttpError(401, "Unauthorized", "/x"))
      .mockRejectedValueOnce(new HttpError(401, "Unauthorized", "/x"));
    const refresh = vi.fn().mockResolvedValue(undefined);

    await expect(gate.withRefreshRetry(call, refresh)).rejects.toBeInstanceOf(HttpError);
    expect(call).toHaveBeenCalledTimes(2);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("shares a single in-flight refresh across concurrent callers", async () => {
    const gate = createRefreshGate();
    let resolveRefresh!: () => void;
    const refresh = vi.fn().mockImplementation(
      () => new Promise<void>((res) => { resolveRefresh = res; }),
    );

    const callA = vi
      .fn()
      .mockRejectedValueOnce(new HttpError(401, "Unauthorized", "/a"))
      .mockResolvedValueOnce("A");
    const callB = vi
      .fn()
      .mockRejectedValueOnce(new HttpError(401, "Unauthorized", "/b"))
      .mockResolvedValueOnce("B");

    const a = gate.withRefreshRetry(callA, refresh);
    const b = gate.withRefreshRetry(callB, refresh);

    // Both should be waiting on the same refresh.
    await Promise.resolve();
    expect(refresh).toHaveBeenCalledTimes(1);

    resolveRefresh();
    await expect(a).resolves.toBe("A");
    await expect(b).resolves.toBe("B");
  });
});
