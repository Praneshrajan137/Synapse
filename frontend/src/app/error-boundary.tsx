import { Button } from "@ds/primitives/Button";
import { Component, type ErrorInfo, type PropsWithChildren, type ReactNode } from "react";

interface State {
  readonly error: Error | null;
  readonly info: ErrorInfo | null;
}

export class ErrorBoundary extends Component<PropsWithChildren, State> {
  override state: State = { error: null, info: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    this.setState({ info });
    // Telemetry — best-effort, no PII, no third-party SaaS (I-1).
    if (typeof fetch === "function") {
      const endpoint = import.meta.env.VITE_TELEMETRY_ENDPOINT;
      if (endpoint) {
        void fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            kind: "error",
            name: error.name,
            message: error.message,
            stack: error.stack?.slice(0, 4_000),
            component_stack: info.componentStack?.slice(0, 2_000),
            ts: new Date().toISOString(),
          }),
        }).catch(() => {
          /* swallow telemetry failures */
        });
      }
    }
  }

  override render(): ReactNode {
    if (!this.state.error) return this.props.children;
    return (
      <div
        role="alert"
        className="mx-auto mt-16 max-w-2xl rounded-lg border border-confidence-risk/40 bg-surface p-6"
      >
        <h2 className="text-lg font-semibold text-confidence-risk">Console crashed</h2>
        <p className="mt-2 text-sm text-ink-muted">
          The interface hit an unrecoverable error. The audit trail is unaffected — every operator
          action is committed before optimistic UI updates (I-4).
        </p>
        <pre className="mt-4 max-h-64 overflow-auto rounded bg-surface-sunken p-3 text-2xs text-ink-muted">
          {this.state.error.name}: {this.state.error.message}
        </pre>
        <Button
          className="mt-4"
          variant="primary"
          onClick={() => {
            this.setState({ error: null, info: null });
            window.location.reload();
          }}
        >
          Reload console
        </Button>
      </div>
    );
  }
}
