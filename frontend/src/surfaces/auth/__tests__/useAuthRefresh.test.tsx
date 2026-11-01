import { useSessionStore } from "@state/session.store";
import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ADR-057: a preview grant carries no refresh cookie, so it renews with a fresh grant and
// records that grant's authority for the access badge; a signed-in session still renews
// through POST /api/v1/auth/refresh (FE-INV-023).

const apiMock = vi.hoisted(() => ({ refresh: vi.fn() }));
const requestPreviewGrantMock = vi.hoisted(() => vi.fn());
vi.mock("@hooks/use-synapse-api", () => ({ useSynapseApi: () => apiMock }));
vi.mock("../access-api", () => ({
  fetchAccessMode: vi.fn(),
  requestPreviewGrant: requestPreviewGrantMock,
}));

import { type OpenAuthority, useAccessStore } from "../access.store";
import { useAuthRefresh } from "../useAuthRefresh";

function Harness() {
  useAuthRefresh();
  return null;
}

/** A session whose renewal is due now: it expires inside the 60 s refresh buffer. */
function dueSession(role: "viewer" | "ops") {
  useSessionStore.setState({
    role,
    accessToken: "jwt.old",
    operatorTokenRef: "ref-old",
    tokenExpiresAt: Date.now() + 30_000,
    bootAuth: "settled",
  });
}

/** Renews a due preview session held at `held` against a gateway that now grants `granted`. */
async function renewPreview(held: OpenAuthority, granted: OpenAuthority): Promise<void> {
  useAccessStore.setState({ access: { kind: "open", authority: held } });
  dueSession(held === "act" ? "ops" : "viewer");
  requestPreviewGrantMock.mockResolvedValue({
    access_token: "jwt.renewed",
    token_type: "Bearer",
    expires_in: 3600,
    role: granted === "act" ? "ops" : "viewer",
    operator_token_ref: "ref-renewed",
    authority: granted,
  });
  render(<Harness />);
  await waitFor(() => {
    expect(useSessionStore.getState().accessToken).toBe("jwt.renewed");
  });
}

describe("useAuthRefresh (ADR-057)", () => {
  beforeEach(() => {
    apiMock.refresh.mockReset();
    requestPreviewGrantMock.mockReset();
  });

  it("renews an open-mode preview grant with a fresh grant, never the refresh cookie", async () => {
    useAccessStore.setState({ access: { kind: "open", authority: "view" } });
    dueSession("viewer");
    requestPreviewGrantMock.mockResolvedValue({
      access_token: "jwt.new",
      token_type: "Bearer",
      expires_in: 3600,
      role: "viewer",
      operator_token_ref: "ref-new",
      authority: "view",
    });
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().accessToken).toBe("jwt.new");
    });
    expect(useSessionStore.getState().operatorTokenRef).toBe("ref-new");
    expect(requestPreviewGrantMock).toHaveBeenCalledTimes(1);
    expect(apiMock.refresh).not.toHaveBeenCalled();
  });

  it("renews a signed-in session through the refresh cookie", async () => {
    useAccessStore.setState({ access: { kind: "authenticated" } });
    dueSession("ops");
    apiMock.refresh.mockResolvedValue({
      access_token: "jwt.rotated",
      token_type: "Bearer",
      expires_in: 900,
      role: "ops",
    });
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().accessToken).toBe("jwt.rotated");
    });
    expect(apiMock.refresh).toHaveBeenCalledTimes(1);
    expect(requestPreviewGrantMock).not.toHaveBeenCalled();
  });

  it("a refused preview renewal clears the session for boot access", async () => {
    useAccessStore.setState({ access: { kind: "open", authority: "view" } });
    dueSession("viewer");
    requestPreviewGrantMock.mockRejectedValue(new Error("retired"));
    render(<Harness />);
    await waitFor(() => {
      expect(useSessionStore.getState().role).toBe("anonymous");
    });
    expect(useSessionStore.getState().accessToken).toBeNull();
    expect(apiMock.refresh).not.toHaveBeenCalled();
  });

  it("a renewal that now grants act records act, so the badge says it can act", async () => {
    await renewPreview("view", "act");
    expect(useAccessStore.getState().access).toEqual({ kind: "open", authority: "act" });
    expect(useSessionStore.getState().role).toBe("ops");
  });

  it("a renewal that now grants view records view, so the badge says view only", async () => {
    await renewPreview("act", "view");
    expect(useAccessStore.getState().access).toEqual({ kind: "open", authority: "view" });
    expect(useSessionStore.getState().role).toBe("viewer");
  });
});
