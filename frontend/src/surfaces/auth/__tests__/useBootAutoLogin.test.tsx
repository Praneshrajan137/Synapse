import { useSessionStore } from "@state/session.store";
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Sprint 16: the boot auto-login — the console opens without a login wall,
// failures fall through to /login, and the attempt never loops.

const loginMock = vi.hoisted(() => vi.fn());
vi.mock("@hooks/use-synapse-api", () => ({
  useSynapseApi: () => ({ login: loginMock }),
}));

import { useBootAutoLogin } from "../useBootAutoLogin";

function Harness() {
  useBootAutoLogin();
  return null;
}

const ADMIN_RESPONSE = {
  access_token: "jwt.access.token",
  token_type: "Bearer" as const,
  expires_in: 900,
  role: "admin" as const,
  operator_token_ref: "vault:tok-admin1",
};

describe("useBootAutoLogin", () => {
  beforeEach(() => {
    loginMock.mockReset();
    useSessionStore.setState({
      role: "anonymous",
      operatorTokenRef: null,
      accessToken: null,
      tokenExpiresAt: null,
      bootAuth: "idle",
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("signs in silently as the demo admin and settles", async () => {
    loginMock.mockResolvedValue(ADMIN_RESPONSE);
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().role).toBe("admin");
    });
    const s = useSessionStore.getState();
    expect(s.accessToken).toBe("jwt.access.token");
    expect(s.bootAuth).toBe("settled");
    expect(loginMock).toHaveBeenCalledWith({
      operator_id: "admin@synapse.local",
      password: "admin_dev_2026!!",
    });
  });

  it("a failed attempt settles silently — RouteGuard falls through to /login", async () => {
    loginMock.mockRejectedValue(new Error("gateway down"));
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    expect(useSessionStore.getState().role).toBe("anonymous");
  });

  it("attempts exactly once even across re-renders (StrictMode latch)", async () => {
    loginMock.mockRejectedValue(new Error("nope"));
    const { rerender } = render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    rerender(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    expect(loginMock).toHaveBeenCalledTimes(1);
  });

  it("does nothing when a session already exists", async () => {
    useSessionStore.setState({ role: "ops", bootAuth: "idle" });
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("VITE_AUTO_LOGIN=false restores the login-first flow", async () => {
    vi.stubEnv("VITE_AUTO_LOGIN", "false");
    loginMock.mockResolvedValue(ADMIN_RESPONSE);
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    expect(loginMock).not.toHaveBeenCalled();
    expect(useSessionStore.getState().role).toBe("anonymous");
  });
});
