import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// Mock the two shared signals the hook threads into the resolver so we can
// exercise the wiring (defaults + overrides) without a QueryClient or a socket.
const postureState = vi.hoisted(() => ({
  value: { isError: false, data: { degraded: false } as { degraded: boolean } | undefined },
}));
const onlineState = vi.hoisted(() => ({ offline: false }));

vi.mock("@hooks/use-posture", () => ({
  usePosture: () => postureState.value,
}));
vi.mock("@hooks/use-online-status", () => ({
  useOnlineStatus: () => onlineState.offline,
}));

import { useDegradedPosture, useUniversalState } from "@hooks/use-universal-state";

afterEach(() => {
  postureState.value = { isError: false, data: { degraded: false } };
  onlineState.offline = false;
});

describe("useDegradedPosture", () => {
  it("treats a posture-fetch failure as degraded (posture unknown), never healthy", () => {
    postureState.value = { isError: true, data: undefined };
    const { result } = renderHook(() => useDegradedPosture());
    expect(result.current).toBe(true);
  });

  it("is degraded when the posture reports degraded, healthy otherwise", () => {
    postureState.value = { isError: false, data: { degraded: true } };
    expect(renderHook(() => useDegradedPosture()).result.current).toBe(true);
    postureState.value = { isError: false, data: { degraded: false } };
    expect(renderHook(() => useDegradedPosture()).result.current).toBe(false);
  });
});

describe("useUniversalState", () => {
  it("resolves populated when data is present and all signals are healthy", () => {
    const { result } = renderHook(() =>
      useUniversalState({ isLoading: false, isError: false, itemCount: 3 }),
    );
    expect(result.current).toBe("populated");
  });

  it("distinguishes empty (no data yet) from error (failed to load)", () => {
    expect(
      renderHook(() => useUniversalState({ isLoading: false, isError: false, itemCount: 0 }))
        .result.current,
    ).toBe("empty");
    expect(
      renderHook(() => useUniversalState({ isLoading: false, isError: true, itemCount: 0 }))
        .result.current,
    ).toBe("error");
  });

  it("prioritises offline (browser) over every data state", () => {
    onlineState.offline = true;
    const { result } = renderHook(() =>
      useUniversalState({ isLoading: true, isError: true, itemCount: 5 }),
    );
    expect(result.current).toBe("offline");
  });

  it("derives degraded from posture when online and not failed", () => {
    postureState.value = { isError: false, data: { degraded: true } };
    const { result } = renderHook(() =>
      useUniversalState({ isLoading: false, isError: false, itemCount: 5 }),
    );
    expect(result.current).toBe("degraded");
  });

  it("lets a surface override the offline/degraded signals explicitly", () => {
    onlineState.offline = true;
    postureState.value = { isError: true, data: undefined };
    const { result } = renderHook(() =>
      useUniversalState({
        isLoading: false,
        isError: false,
        itemCount: 2,
        isOffline: false,
        isDegraded: false,
      }),
    );
    expect(result.current).toBe("populated");
  });
});
