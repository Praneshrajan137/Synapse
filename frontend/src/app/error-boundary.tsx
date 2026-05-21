import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * SYNAPSE Atlas Console — top-level error boundary.
 *
 * Renders a static, AAA-contrast fallback so an exploded surface never
 * blanks the screen mid-shift. Future S2 enhancement: forward to
 * GlitchTip via @opentelemetry instrumentation.
 */

interface ErrorBoundaryProps {
  readonly children: ReactNode;
  readonly fallback?: (error: Error, retry: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  readonly error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    // Structured-log to console — replaced by GlitchTip / OTel in S2.
    // eslint-disable-next-line no-console
    console.error("[atlas-console] uncaught error", { error, componentStack: info.componentStack });
  }

  private readonly retry = () => {
    this.setState({ error: null });
  };

  override render(): ReactNode {
    const { error } = this.state;
    if (error) {
      if (this.props.fallback) return this.props.fallback(error, this.retry);
      return (
        <div
          role="alert"
          aria-live="assertive"
          className="m-6 max-w-2xl rounded-lg border border-safety-critical/40 bg-card p-6 text-card-fg"
        >
          <h1 className="text-ops-xl font-semibold text-safety-critical">
            Atlas Console hit an unexpected error
          </h1>
          <p className="mt-2 text-ops-sm text-muted-fg">
            The console will keep streaming live data once you retry. The error has been logged
            with a request id you can share with on-call.
          </p>
          <pre className="mt-4 overflow-auto rounded bg-muted p-3 text-ops-xs text-muted-fg">
            {error.message}
          </pre>
          <button
            type="button"
            onClick={this.retry}
            className="mt-4 inline-flex h-9 items-center rounded-md bg-primary px-4 text-ops-sm font-medium text-primary-fg hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
