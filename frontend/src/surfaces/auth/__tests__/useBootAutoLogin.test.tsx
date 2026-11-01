import { useSessionStore } from "@state/session.store";
import { act, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ADR-057 (finding 89): boot access. The console asks the gateway how to enter, takes a
// preview grant in open mode, takes nothing in authenticated mode, still opens when the
// gateway is unreachable, and tries again at most once per floor, so it never loops and never
// strands a visitor until a reload. No credential is involved at any step.

const fetchAccessModeMock = vi.hoisted(() => vi.fn());
const requestPreviewGrantMock = vi.hoisted(() => vi.fn());
vi.mock("../access-api", () => ({
  fetchAccessMode: fetchAccessModeMock,
  requestPreviewGrant: requestPreviewGrantMock,
}));

import { useAccessStore } from "../access.store";
import { REACQUIRE_FLOOR_MS, useBootAutoLogin } from "../useBootAutoLogin";

function Harness() {
  useBootAutoLogin();
  return null;
}

const VIEW_GRANT = {
  access_token: "jwt.preview.view",
  token_type: "Bearer" as const,
  expires_in: 3600,
  role: "viewer" as const,
  operator_token_ref: "ref-preview-view",
  authority: "view" as const,
};

const ACT_GRANT = {
  ...VIEW_GRANT,
  access_token: "jwt.preview.act",
  role: "ops" as const,
  operator_token_ref: "ref-preview-act",
  authority: "act" as const,
};

/** Lets resolved promises, store updates and effects settle without moving the fake clock. */
async function flush(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

/** Moves the fake clock forward, then lets whatever that released settle. */
async function elapse(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
  await flush();
}

describe("useBootAutoLogin (boot access, ADR-057)", () => {
  beforeEach(() => {
    fetchAccessModeMock.mockReset();
    requestPreviewGrantMock.mockReset();
    useSessionStore.setState({
      role: "anonymous",
      operatorTokenRef: null,
      accessToken: null,
      tokenExpiresAt: null,
      bootAuth: "idle",
    });
    useAccessStore.setState({ access: { kind: "resolving" } });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("open mode stores a view-only preview grant exactly as a sign-in token", async () => {
    fetchAccessModeMock.mockResolvedValue({ mode: "open", authority: "view" });
    requestPreviewGrantMock.mockResolvedValue(VIEW_GRANT);
    const before = Date.now();
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    const s = useSessionStore.getState();
    expect(s.role).toBe("viewer");
    expect(s.accessToken).toBe("jwt.preview.view");
    expect(s.operatorTokenRef).toBe("ref-preview-view");
    expect(s.tokenExpiresAt).toBeGreaterThanOrEqual(before + 3600 * 1000);
    expect(useAccessStore.getState().access).toEqual({ kind: "open", authority: "view" });
    expect(requestPreviewGrantMock).toHaveBeenCalledTimes(1);
  });

  it("open mode with act authority holds ops and never more", async () => {
    fetchAccessModeMock.mockResolvedValue({ mode: "open", authority: "act" });
    requestPreviewGrantMock.mockResolvedValue(ACT_GRANT);
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().role).toBe("ops");
    });
    expect(useAccessStore.getState().access).toEqual({ kind: "open", authority: "act" });
    expect(useSessionStore.getState().accessToken).toBe("jwt.preview.act");
  });

  it("authenticated mode takes no grant and leaves the visitor anonymous for /login", async () => {
    fetchAccessModeMock.mockResolvedValue({ mode: "authenticated", authority: null });
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    expect(useAccessStore.getState().access).toEqual({ kind: "authenticated" });
    expect(useSessionStore.getState().role).toBe("anonymous");
    expect(requestPreviewGrantMock).not.toHaveBeenCalled();
  });

  it("an unreachable gateway still opens the console and marks access unavailable", async () => {
    fetchAccessModeMock.mockRejectedValue(new Error("gateway down"));
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    expect(useAccessStore.getState().access).toEqual({ kind: "unavailable" });
    expect(useSessionStore.getState().role).toBe("anonymous");
    expect(requestPreviewGrantMock).not.toHaveBeenCalled();
  });

  it("a refused preview grant settles once and keeps the open posture it read", async () => {
    fetchAccessModeMock.mockResolvedValue({ mode: "open", authority: "view" });
    requestPreviewGrantMock.mockRejectedValue(new Error("refused"));
    const { rerender } = render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    rerender(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    expect(useSessionStore.getState().role).toBe("anonymous");
    expect(useAccessStore.getState().access).toEqual({ kind: "open", authority: "view" });
    expect(fetchAccessModeMock).toHaveBeenCalledTimes(1);
    expect(requestPreviewGrantMock).toHaveBeenCalledTimes(1);
  });

  it("a session holding an access token is left alone and nothing is asked", async () => {
    useSessionStore.setState({ role: "ops", accessToken: "live", bootAuth: "idle" });
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().bootAuth).toBe("settled");
    });
    expect(fetchAccessModeMock).not.toHaveBeenCalled();
    expect(requestPreviewGrantMock).not.toHaveBeenCalled();
    expect(useSessionStore.getState().role).toBe("ops");
  });

  // session.store.ts persists the role and the token ref, never the token, so each of the
  // next three sessions is what a reload leaves behind.

  it("a reloaded session, a role with no token, takes a fresh grant", async () => {
    useSessionStore.setState({ role: "ops", operatorTokenRef: "ref-before-reload" });
    fetchAccessModeMock.mockResolvedValue({ mode: "open", authority: "view" });
    requestPreviewGrantMock.mockResolvedValue(VIEW_GRANT);
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().accessToken).toBe("jwt.preview.view");
    });
    // The grant replaces the reloaded role: the gateway now opens at view, not ops.
    expect(useSessionStore.getState().role).toBe("viewer");
    expect(useSessionStore.getState().operatorTokenRef).toBe("ref-preview-view");
    // The open posture the access badge renders from.
    expect(useAccessStore.getState().access).toEqual({ kind: "open", authority: "view" });
    expect(fetchAccessModeMock).toHaveBeenCalledTimes(1);
    expect(requestPreviewGrantMock).toHaveBeenCalledTimes(1);
  });

  it("a reloaded signed-in session keeps its role for the refresh cookie", async () => {
    useSessionStore.setState({ role: "ops", operatorTokenRef: "ref-signed-in" });
    fetchAccessModeMock.mockResolvedValue({ mode: "authenticated", authority: null });
    render(<Harness />);
    await waitFor(() => {
      expect(useAccessStore.getState().access).toEqual({ kind: "authenticated" });
    });
    expect(useSessionStore.getState().bootAuth).toBe("settled");
    expect(useSessionStore.getState().role).toBe("ops");
    expect(useSessionStore.getState().operatorTokenRef).toBe("ref-signed-in");
    expect(requestPreviewGrantMock).not.toHaveBeenCalled();
  });

  it("a reloaded session keeps its role while the gateway cannot be reached", async () => {
    useSessionStore.setState({ role: "admin", operatorTokenRef: "ref-signed-in" });
    fetchAccessModeMock.mockRejectedValue(new Error("gateway down"));
    render(<Harness />);
    await waitFor(() => {
      expect(useAccessStore.getState().access).toEqual({ kind: "unavailable" });
    });
    expect(useSessionStore.getState().role).toBe("admin");
    expect(requestPreviewGrantMock).not.toHaveBeenCalled();
  });

  it("a session cleared after the floor re-reads the mode and takes a fresh grant", async () => {
    fetchAccessModeMock.mockResolvedValue({ mode: "open", authority: "view" });
    requestPreviewGrantMock.mockResolvedValue(VIEW_GRANT);
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().role).toBe("viewer");
    });
    const later = Date.now() + REACQUIRE_FLOOR_MS + 1;
    vi.spyOn(Date, "now").mockReturnValue(later);
    useSessionStore.getState().clearAuth();
    await waitFor(() => {
      expect(requestPreviewGrantMock).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(useSessionStore.getState().role).toBe("viewer");
    });
    expect(fetchAccessModeMock).toHaveBeenCalledTimes(2);
  });

  it("after activation a cleared preview session stays anonymous for /login", async () => {
    fetchAccessModeMock.mockResolvedValueOnce({ mode: "open", authority: "view" });
    requestPreviewGrantMock.mockResolvedValue(VIEW_GRANT);
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().role).toBe("viewer");
    });
    fetchAccessModeMock.mockResolvedValueOnce({ mode: "authenticated", authority: null });
    const later = Date.now() + REACQUIRE_FLOOR_MS + 1;
    vi.spyOn(Date, "now").mockReturnValue(later);
    useSessionStore.getState().clearAuth();
    await waitFor(() => {
      expect(useAccessStore.getState().access).toEqual({ kind: "authenticated" });
    });
    expect(useSessionStore.getState().role).toBe("anonymous");
    expect(requestPreviewGrantMock).toHaveBeenCalledTimes(1);
  });

  describe("the re-acquire floor, on a fake clock", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("a session cleared inside the floor is re-acquired as the floor ends", async () => {
      fetchAccessModeMock.mockResolvedValue({ mode: "open", authority: "view" });
      requestPreviewGrantMock.mockResolvedValue(VIEW_GRANT);
      render(<Harness />);
      await flush();
      expect(useSessionStore.getState().role).toBe("viewer");

      // The grant is lost ten seconds in, as a 401 just after a deploy restarts the gateway.
      await elapse(10_000);
      act(() => {
        useSessionStore.getState().clearAuth();
      });
      // Held by the floor: nothing asked yet, no splash, exactly one timer for the rest of it.
      expect(fetchAccessModeMock).toHaveBeenCalledTimes(1);
      expect(useSessionStore.getState().bootAuth).toBe("settled");
      expect(vi.getTimerCount()).toBe(1);

      // Every bootAuth the hook writes from here on: none while the floor holds (one timer,
      // not a poll), then the re-acquire's.
      const written: string[] = [];
      const unsubscribe = useSessionStore.subscribe((s) => {
        written.push(s.bootAuth);
      });
      await elapse(REACQUIRE_FLOOR_MS - 10_000 - 1);
      const writtenWhileHeld = written.length;
      expect(useSessionStore.getState().role).toBe("anonymous");
      expect(requestPreviewGrantMock).toHaveBeenCalledTimes(1);

      await elapse(1);
      unsubscribe();
      expect(writtenWhileHeld).toBe(0);
      expect(written.length).toBeGreaterThan(0);
      expect(fetchAccessModeMock).toHaveBeenCalledTimes(2);
      expect(requestPreviewGrantMock).toHaveBeenCalledTimes(2);
      expect(useSessionStore.getState().role).toBe("viewer");
      expect(useSessionStore.getState().accessToken).toBe("jwt.preview.view");
      expect(vi.getTimerCount()).toBe(0);
    });

    it("a clock set back restarts the floor instead of stretching it", async () => {
      fetchAccessModeMock.mockResolvedValue({ mode: "open", authority: "view" });
      requestPreviewGrantMock.mockResolvedValue(VIEW_GRANT);
      render(<Harness />);
      await flush();
      expect(useSessionStore.getState().role).toBe("viewer");

      // An hour back, then the grant is lost: the next attempt is one floor away, not an
      // hour and a floor.
      vi.setSystemTime(Date.now() - 3_600_000);
      act(() => {
        useSessionStore.getState().clearAuth();
      });
      await elapse(REACQUIRE_FLOOR_MS - 1);
      expect(requestPreviewGrantMock).toHaveBeenCalledTimes(1);

      await elapse(1);
      expect(requestPreviewGrantMock).toHaveBeenCalledTimes(2);
      expect(useSessionStore.getState().role).toBe("viewer");
    });

    it("an outage at boot is retried as the floor ends, behind the open console", async () => {
      fetchAccessModeMock.mockRejectedValueOnce(new Error("gateway down"));
      fetchAccessModeMock.mockResolvedValue({ mode: "open", authority: "view" });
      requestPreviewGrantMock.mockResolvedValue(VIEW_GRANT);
      render(<Harness />);
      await flush();
      expect(useAccessStore.getState().access).toEqual({ kind: "unavailable" });
      expect(useSessionStore.getState().role).toBe("anonymous");
      expect(useSessionStore.getState().bootAuth).toBe("settled");
      expect(vi.getTimerCount()).toBe(1);

      await elapse(REACQUIRE_FLOOR_MS - 1);
      expect(fetchAccessModeMock).toHaveBeenCalledTimes(1);

      // Every bootAuth the retry writes. The console is already open, so none is "pending".
      const written: string[] = [];
      const unsubscribe = useSessionStore.subscribe((s) => {
        written.push(s.bootAuth);
      });
      await elapse(1);
      unsubscribe();
      expect(fetchAccessModeMock).toHaveBeenCalledTimes(2);
      expect(useSessionStore.getState().role).toBe("viewer");
      expect(useSessionStore.getState().accessToken).toBe("jwt.preview.view");
      expect(useAccessStore.getState().access).toEqual({ kind: "open", authority: "view" });
      expect(written.length).toBeGreaterThan(0);
      expect(written).not.toContain("pending");
      expect(vi.getTimerCount()).toBe(0);
    });

    it("unmounting the console cancels the pending re-attempt", async () => {
      fetchAccessModeMock.mockRejectedValue(new Error("gateway down"));
      const { unmount } = render(<Harness />);
      await flush();
      expect(vi.getTimerCount()).toBe(1);

      unmount();
      expect(vi.getTimerCount()).toBe(0);
      await elapse(REACQUIRE_FLOOR_MS);
      expect(fetchAccessModeMock).toHaveBeenCalledTimes(1);
    });
  });
});
