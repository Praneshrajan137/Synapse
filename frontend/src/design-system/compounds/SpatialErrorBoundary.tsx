import { log } from "@lib/log";
import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * Local error boundary for a Spatial_Visualization (Req 7.5).
 *
 * A lazy-loaded viz chunk (deck.gl / MapLibre / Sigma) can fail to load or
 * throw while rendering. `Suspense` only covers the pending state, not a
 * rejected chunk or a render throw — so without a boundary the failure bubbles
 * to the app-level crash boundary and the operator is left with a blank canvas.
 *
 * This boundary keeps the failure local: it renders an explicit error state
 * with a keyboard-operable retry affordance that remounts the children (a fresh
 * import + render attempt) rather than reloading the whole Console. The scoped
 * error is recorded via the whitelisted telemetry helper (no PII).
 */

interface SpatialErrorBoundaryProps {
  /** Human label for the surface, e.g. "living map" — used in the error copy. */
  readonly label: string;
  /** Height (px) so the error block occupies the same footprint as the viz. */
  readonly height?: number;
  readonly className?: string;
  readonly children: ReactNode;
}

interface SpatialErrorBoundaryState {
  readonly error: Error | null;
  /** Bumped on retry to force a remount of the subtree. */
  readonly resetKey: number;
}

export class SpatialErrorBoundary extends Component<
  SpatialErrorBoundaryProps,
  SpatialErrorBoundaryState
> {
  override state: SpatialErrorBoundaryState = { error: null, resetKey: 0 };

  static getDerivedStateFromError(error: Error): Partial<SpatialErrorBoundaryState> {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    log({
      kind: "error",
      error: "spatial_render_boundary",
      name: error.name,
      message: error.message,
      component_stack: info.componentStack?.slice(0, 2_000) ?? undefined,
    });
  }

  private readonly handleRetry = () => {
    this.setState((s) => ({ error: null, resetKey: s.resetKey + 1 }));
  };

  override render(): ReactNode {
    const { label, height = 420, className, children } = this.props;

    if (this.state.error) {
      return (
        <div
          role="alert"
          aria-live="assertive"
          data-universal-state="error"
          className={`syn-card flex flex-col items-center justify-center gap-2 px-6 text-center ${className ?? ""}`}
          style={{ height }}
        >
          <span aria-hidden className="text-2xl text-confidence-risk">
            ⚠
          </span>
          <p className="text-sm font-semibold text-confidence-risk">The {label} failed to load</p>
          <p className="max-w-prose text-xs text-ink-muted">
            This is a load failure, not an empty result. The non-spatial summary below still lists
            the same data — retry to rebuild the visualization.
          </p>
          <button
            type="button"
            onClick={this.handleRetry}
            className="mt-1 h-8 rounded-md border border-border bg-surface-raised px-3 text-xs font-medium text-ink hover:bg-surface focus-visible:outline-none focus-visible:shadow-focus"
          >
            Retry
          </button>
        </div>
      );
    }

    // `key` remount on retry gives the lazy chunk a fresh import + render.
    return <div key={this.state.resetKey}>{children}</div>;
  }
}
