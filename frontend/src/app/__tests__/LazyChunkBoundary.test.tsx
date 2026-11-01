import { installPreloadReload } from "@app/LazyChunkBoundary";
import { LazySurface } from "@app/LazySurface";
import { log } from "@lib/log";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ComponentType, type LazyExoticComponent, lazy } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
// i18next global bootstrap (registers the "common" namespace the failed state's copy uses).
import "@i18n/index";

// Finding 92: every route-split surface renders through LazySurface, whose LazyChunkBoundary
// turns a rejected lazy import into the ERROR universal state with a Reload button, because
// React.lazy caches the rejection and a reload is the only recovery left. The telemetry
// helper is mocked so each test can read how the failure was recorded.
vi.mock("@lib/log", () => ({ log: vi.fn() }));

/**
 * How a dynamic import rejects when its chunk is gone, per engine, plus the error Vite's
 * preload helper raises for a route's stylesheet. The boundary reads only the message.
 */
const CHUNK_LOAD_FAILURES = [
  // Chromium
  "Failed to fetch dynamically imported module: https://synapse.test/assets/Cockpit-3f9a.js",
  // Firefox
  "error loading dynamically imported module: https://synapse.test/assets/Cockpit-3f9a.js",
  // WebKit
  "Importing a module script failed.",
  // Vite's preload helper (vite 5.4.8 `__vitePreload`)
  "Unable to preload CSS for /assets/Cockpit-9d0e.css",
] as const;

/** A route-split surface whose import rejects with `error`, as `React.lazy` receives it. */
function surfaceWhoseImportRejects(error: Error): LazyExoticComponent<ComponentType> {
  return lazy<ComponentType>(() => Promise.reject(error));
}

function DecisionDetailThatThrows(): never {
  throw new TypeError("Cannot read properties of undefined (reading 'proposals')");
}

function SteeringSurface() {
  return <p>steering knobs</p>;
}

describe("LazySurface's failed-chunk state (finding 92)", () => {
  beforeEach(() => {
    // React reports the error a boundary caught to console.error; silence it for a clean run.
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(log).mockClear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("a chunk that cannot load renders the newer-build state with a Reload button", async () => {
    for (const message of CHUNK_LOAD_FAILURES) {
      vi.mocked(log).mockClear();
      const Cockpit = surfaceWhoseImportRejects(new Error(message));
      const { unmount } = render(
        <LazySurface name="Override Cockpit">
          <Cockpit />
        </LazySurface>,
      );

      const alert = await screen.findByRole("alert");
      expect(alert, message).toHaveAttribute("data-universal-state", "error");
      expect(alert, message).toHaveTextContent("A newer build may have been deployed");
      expect(alert, message).toHaveTextContent("Override Cockpit could not download its code.");
      expect(within(alert).getByRole("button", { name: "Reload" })).toBeInTheDocument();
      expect(log, message).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "error", error: "lazy_chunk_load", message }),
      );
      unmount();
    }
  });

  it("the Reload button is keyboard-reachable and reloads the page", async () => {
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    const Cockpit = surfaceWhoseImportRejects(new Error(CHUNK_LOAD_FAILURES[0]));
    render(
      <LazySurface name="Override Cockpit">
        <Cockpit />
      </LazySurface>,
    );
    const button = await screen.findByRole("button", { name: "Reload" });
    const user = userEvent.setup();

    await user.tab();
    expect(button).toHaveFocus();
    expect(reload).not.toHaveBeenCalled();
    await user.click(button);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("an import rejecting for another reason is a render failure, not a stale build", async () => {
    const Ingress = surfaceWhoseImportRejects(new ReferenceError("process is not defined"));
    render(
      <LazySurface name="Ingress Console">
        <Ingress />
      </LazySurface>,
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveAttribute("data-universal-state", "error");
    expect(alert).toHaveTextContent("Ingress Console failed to render");
    expect(alert).not.toHaveTextContent("newer build");
    expect(log).toHaveBeenCalledWith(
      expect.objectContaining({ error: "lazy_surface_render", message: "process is not defined" }),
    );
  });

  it("a surface that throws while rendering gets an error state, not the stale-build copy", () => {
    render(
      <LazySurface name="Decision Detail">
        <DecisionDetailThatThrows />
      </LazySurface>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("data-universal-state", "error");
    expect(alert).toHaveTextContent("Decision Detail failed to render");
    expect(alert).toHaveTextContent("This is a failure, not an empty result.");
    expect(alert).not.toHaveTextContent("newer build");
    expect(within(alert).getByRole("button", { name: "Reload" })).toBeInTheDocument();
    expect(log).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "error",
        error: "lazy_surface_render",
        message: "Cannot read properties of undefined (reading 'proposals')",
      }),
    );
  });

  it("a failure caught on one surface does not follow the operator to the next", () => {
    const { rerender } = render(
      <LazySurface name="Decision Detail">
        <DecisionDetailThatThrows />
      </LazySurface>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();

    rerender(
      <LazySurface name="Audit Vault">
        <p>audit rows</p>
      </LazySurface>,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("audit rows")).toBeInTheDocument();
  });

  it("a surface whose import resolves renders itself, with no alert and no log", async () => {
    const Steering = lazy(() => Promise.resolve({ default: SteeringSurface }));
    render(
      <LazySurface name="Steering">
        <Steering />
      </LazySurface>,
    );

    expect(await screen.findByText("steering knobs")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(log).not.toHaveBeenCalled();
  });
});

describe("installPreloadReload, the vite:preloadError loop guard", () => {
  const T0 = 1_760_000_000_000;
  let clock = T0;
  const disposers: Array<() => void> = [];

  /** One page's listener, installed as main.tsx installs it, before the first render. */
  function installPage(
    reload: () => void,
    storage: () => Pick<Storage, "getItem" | "setItem">,
  ): () => void {
    const dispose = installPreloadReload({ target: window, storage, now: () => clock, reload });
    disposers.push(dispose);
    return dispose;
  }

  /** What Vite's preload helper does when a dynamic import rejects. */
  function failAnImport(): void {
    window.dispatchEvent(new Event("vite:preloadError", { cancelable: true }));
  }

  beforeEach(() => {
    clock = T0;
    window.sessionStorage.clear();
  });
  afterEach(() => {
    for (const dispose of disposers.splice(0)) dispose();
    window.sessionStorage.clear();
  });

  it("reloads once on a failed import, and not again within 10 s", () => {
    const reload = vi.fn();
    installPage(reload, () => window.sessionStorage);

    failAnImport();
    clock = T0 + 9_999;
    failAnImport();

    expect(reload).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.getItem("synapse.preloadReloadAt")).toBe(String(T0));
  });

  it("the stamp outlives the reload, so the reloaded page's own failure does not reload", () => {
    const reload = vi.fn();
    const firstPage = installPage(reload, () => window.sessionStorage);
    failAnImport();
    expect(reload).toHaveBeenCalledTimes(1);

    // The reload unloads the first page's listener; the tab's sessionStorage survives it, and
    // the reloaded page installs its own listener before its first render.
    firstPage();
    clock = T0 + 2_000;
    installPage(reload, () => window.sessionStorage);
    failAnImport();

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("reloads again once 10 s have passed, since a later deploy is a new failure", () => {
    const reload = vi.fn();
    installPage(reload, () => window.sessionStorage);

    failAnImport();
    clock = T0 + 10_000;
    failAnImport();

    expect(reload).toHaveBeenCalledTimes(2);
    expect(window.sessionStorage.getItem("synapse.preloadReloadAt")).toBe(String(T0 + 10_000));
  });

  it("does not reload when the stamp cannot be written: an unrecorded reload is unguarded", () => {
    const reload = vi.fn();
    const refusing: Pick<Storage, "getItem" | "setItem"> = {
      getItem: () => null,
      setItem: () => {
        throw new DOMException("The quota has been exceeded.", "QuotaExceededError");
      },
    };
    installPage(reload, () => refusing);

    failAnImport();

    expect(reload).not.toHaveBeenCalled();
  });

  it("does not reload when sessionStorage itself cannot be reached", () => {
    const reload = vi.fn();
    installPage(reload, () => {
      throw new DOMException("The operation is insecure.", "SecurityError");
    });

    failAnImport();

    expect(reload).not.toHaveBeenCalled();
  });

  it("stops listening once disposed", () => {
    const reload = vi.fn();
    const dispose = installPage(reload, () => window.sessionStorage);
    dispose();

    failAnImport();

    expect(reload).not.toHaveBeenCalled();
  });
});
