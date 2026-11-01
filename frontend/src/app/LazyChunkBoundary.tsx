import { type UniversalStateLabels, UniversalStateView } from "@ds/compounds/UniversalStateView";
import { log } from "@lib/log";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

/**
 * The failed-chunk state of every route-split surface (finding 92), rendered by `LazySurface`
 * around its Suspense boundary.
 *
 * `React.lazy` caches its import's rejection: once a surface's chunk has failed, every render of
 * that component rethrows the same error, so a remount cannot retry and a page reload is the
 * only recovery. Without this boundary the rejection reached React Router's default
 * "Unexpected Application Error!" page, which offers none.
 *
 * Two failures are told apart and neither is swallowed: each renders the ERROR universal state
 * (`role="alert"`, a Reload button) and is logged through the field-whitelisted `log()`.
 * - `chunk`: the browser could not fetch the code. After a deploy the old hashed chunk is gone,
 *   and `frontend/nginx.conf`'s `location /assets/` answers it `try_files $uri =404`. A dropped
 *   connection rejects the same way, so the copy says a newer build MAY have been deployed.
 * - `render`: anything else -- the surface threw while rendering, or its module threw while
 *   evaluating, so its import rejected with that error rather than with a fetch failure.
 */

/**
 * How a dynamic import that could not load rejects, per engine, plus the error Vite's preload
 * helper raises for a route's stylesheet. Matched against `Error.message`.
 */
const CHUNK_LOAD_FAILURE: readonly RegExp[] = [
  /Failed to fetch dynamically imported module/i, // Chromium
  /error loading dynamically imported module/i, // Firefox
  /Importing a module script failed/i, // WebKit
  /Unable to preload CSS/i, // Vite's preload helper
];

function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const { message } = error;
  return CHUNK_LOAD_FAILURE.some((pattern) => pattern.test(message));
}

/** sessionStorage key holding the epoch-ms time of the last automatic reload. */
export const PRELOAD_RELOAD_KEY = "synapse.preloadReloadAt";

/** Inside this window after an automatic reload, a new failure renders the boundary instead. */
export const PRELOAD_RELOAD_WINDOW_MS = 10_000;

interface PreloadReloadDeps {
  /** Where Vite dispatches `vite:preloadError`: the window. */
  readonly target: Pick<Window, "addEventListener" | "removeEventListener">;
  /** Called inside the guard's `try`: a browser that refuses storage throws on access. */
  readonly storage: () => Pick<Storage, "getItem" | "setItem">;
  readonly now: () => number;
  readonly reload: () => void;
}

/**
 * Reload once when a dynamic import fails, so a page opened before a deploy moves onto the
 * current build without a click. Vite's preload helper (`__vitePreload`, read in vite 5.4.8)
 * dispatches `vite:preloadError` on `window` whenever a dynamic import rejects: a chunk it
 * could not fetch, a stylesheet it could not preload, and also a module that threw while
 * evaluating -- for route chunks and the lazy map and graph canvases alike. A module that
 * throws is a bug, not a stale build: it costs one guarded reload, and then the boundary
 * renders it as a render failure.
 *
 * The event is never `preventDefault()`-ed, so the import still rejects and the boundary renders:
 * briefly while the reload is in flight, and for good when the guard holds. The guard holds when
 * the last automatic reload is under PRELOAD_RELOAD_WINDOW_MS old (the reloaded page failed too,
 * so another reload would loop), and when the stamp cannot be read or written, because an
 * unrecorded reload is an unguarded one. Returns the function that removes the listener.
 */
export function installPreloadReload(deps: PreloadReloadDeps): () => void {
  const onPreloadError = (): void => {
    const at = deps.now();
    try {
      const storage = deps.storage();
      const elapsed = at - Number(storage.getItem(PRELOAD_RELOAD_KEY));
      if (elapsed >= 0 && elapsed < PRELOAD_RELOAD_WINDOW_MS) return;
      storage.setItem(PRELOAD_RELOAD_KEY, String(at));
    } catch {
      return;
    }
    deps.reload();
  };
  deps.target.addEventListener("vite:preloadError", onPreloadError);
  return () => deps.target.removeEventListener("vite:preloadError", onPreloadError);
}

type SurfaceFailure = "chunk" | "render";

interface LazyChunkBoundaryProps {
  /** The surface's display name, as `LazySurface` received it; the failure copy names it. */
  readonly name: string;
  readonly children: ReactNode;
}

interface LazyChunkBoundaryState {
  readonly failure: SurfaceFailure | null;
}

export class LazyChunkBoundary extends Component<LazyChunkBoundaryProps, LazyChunkBoundaryState> {
  override state: LazyChunkBoundaryState = { failure: null };

  static getDerivedStateFromError(error: unknown): LazyChunkBoundaryState {
    return { failure: isChunkLoadError(error) ? "chunk" : "render" };
  }

  override componentDidCatch(error: unknown, info: ErrorInfo): void {
    log({
      kind: "error",
      error: isChunkLoadError(error) ? "lazy_chunk_load" : "lazy_surface_render",
      name: error instanceof Error ? error.name : typeof error,
      message: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack?.slice(0, 4_000) : undefined,
      path: window.location.pathname,
      component_stack: info.componentStack?.slice(0, 2_000) ?? undefined,
    });
  }

  override render(): ReactNode {
    const { failure } = this.state;
    if (failure === null) return this.props.children;
    return <SurfaceFailed name={this.props.name} failure={failure} />;
  }
}

interface SurfaceFailedProps {
  readonly name: string;
  readonly failure: SurfaceFailure;
}

function SurfaceFailed({ name, failure }: SurfaceFailedProps) {
  const { t } = useTranslation("common");
  const labels: UniversalStateLabels =
    failure === "chunk"
      ? {
          errorTitle: t("lazy.chunk_title"),
          errorDetail: t("lazy.chunk_detail", { surface: name }),
        }
      : {
          errorTitle: t("lazy.render_title", { surface: name }),
          errorDetail: t("lazy.render_detail"),
        };
  return (
    <UniversalStateView
      state="error"
      labels={labels}
      onRetry={reloadPage}
      retryLabel={t("lazy.reload")}
      className="m-6"
    >
      {null}
    </UniversalStateView>
  );
}

/** The operator's own reload is never guarded; only the automatic one is. */
function reloadPage(): void {
  window.location.reload();
}
