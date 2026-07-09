import { useSynapseApi } from "@hooks/use-synapse-api";
import { useSessionStore } from "@state/session.store";
import { renderHook } from "@testing-library/react";
import { HttpError } from "@transport/errors";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Req 12.2 / FE-INV-023 — a 401 on any wrapped API call triggers a SINGLE
// single-flight refresh + replay; a refresh failure OR a second 401 clears the
// session (RouteGuard then routes to /login without a full page reload).
//
// We mock the underlying typed client so `useSynapseApi` wraps a controllable
// base with its refresh gate + session-clearing proxy.

const mocks = vi.hoisted(() => ({
  listAgents: vi.fn(),
  refresh: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("@transport/synapse-api", () => ({
  createSynapseApi: () => ({
    listAgents: mocks.listAgents,
    refresh: mocks.refresh,
    login: mocks.login,
    logout: mocks.logout,
  }),
}));

function authenticate(): void {
  useSessionStore.getState().setAuth("ops", "access-token", "hvs.ref123", 900);
}

describe("useSynapseApi — Req 12.2 single-flight 401 recovery", () => {
  beforeEach(() => {
    mocks.listAgents.mockReset();
    mocks.refresh.mockReset();
    useSessionStore.getState().clearAuth();
    authenticate();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("refreshes once and replays the in-flight call on a single 401", async () => {
    mocks.listAgents
      .mockRejectedValueOnce(new HttpError(401, "Unauthorized", "/api/v1/agents"))
      .mockResolvedValueOnce({ agents: [] });
    mocks.refresh.mockResolvedValue({
      access_token: "rotated-token",
      token_type: "Bearer",
      expires_in: 900,
      role: "ops",
    });

    const { result } = renderHook(() => useSynapseApi());
    await expect(result.current.listAgents()).resolves.toEqual({ agents: [] });

    expect(mocks.refresh).toHaveBeenCalledTimes(1);
    expect(mocks.listAgents).toHaveBeenCalledTimes(2);
    // Session survived and the rotated token was applied — no clear.
    expect(useSessionStore.getState().role).toBe("ops");
    expect(useSessionStore.getState().accessToken).toBe("rotated-token");
  });

  it("clears the session (route to /login) when the refresh itself fails", async () => {
    mocks.listAgents.mockRejectedValue(new HttpError(401, "Unauthorized", "/api/v1/agents"));
    mocks.refresh.mockRejectedValue(new HttpError(401, "Unauthorized", "/api/v1/auth/refresh"));

    const { result } = renderHook(() => useSynapseApi());
    await expect(result.current.listAgents()).rejects.toThrow();

    expect(mocks.refresh).toHaveBeenCalledTimes(1);
    expect(useSessionStore.getState().role).toBe("anonymous");
    expect(useSessionStore.getState().accessToken).toBeNull();
  });

  it("clears the session when a SECOND 401 survives the refresh replay", async () => {
    mocks.listAgents
      .mockRejectedValueOnce(new HttpError(401, "Unauthorized", "/api/v1/agents"))
      .mockRejectedValueOnce(new HttpError(401, "Unauthorized", "/api/v1/agents"));
    mocks.refresh.mockResolvedValue({
      access_token: "rotated-token",
      token_type: "Bearer",
      expires_in: 900,
      role: "ops",
    });

    const { result } = renderHook(() => useSynapseApi());
    await expect(result.current.listAgents()).rejects.toBeInstanceOf(HttpError);

    expect(mocks.refresh).toHaveBeenCalledTimes(1);
    expect(mocks.listAgents).toHaveBeenCalledTimes(2);
    expect(useSessionStore.getState().role).toBe("anonymous");
  });

  it("does not refresh or clear on a non-401 error", async () => {
    mocks.listAgents.mockRejectedValue(new HttpError(500, "boom", "/api/v1/agents"));

    const { result } = renderHook(() => useSynapseApi());
    await expect(result.current.listAgents()).rejects.toBeInstanceOf(HttpError);

    expect(mocks.refresh).not.toHaveBeenCalled();
    expect(useSessionStore.getState().role).toBe("ops");
  });
});
