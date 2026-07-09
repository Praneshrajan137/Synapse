import { ErrorBoundary } from "@app/error-boundary";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Req 14.3 — an unhandled render error is caught at the boundary and a RECOVERY
// affordance is rendered; the operator is never left on a blank screen.

function Boom(): never {
  throw new Error("kaboom in render");
}

describe("ErrorBoundary — Req 14.3 render-crash recovery", () => {
  beforeEach(() => {
    // React logs the caught error to console.error; silence for a clean run.
    vi.spyOn(console, "error").mockImplementation(() => {});
    // The boundary reports a field-whitelisted telemetry beacon on catch.
    Object.defineProperty(navigator, "sendBeacon", {
      configurable: true,
      writable: true,
      value: vi.fn().mockReturnValue(true),
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children unchanged when nothing throws", () => {
    render(
      <ErrorBoundary>
        <p>healthy console</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("healthy console")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("catches a render error and renders a recovery affordance, not a blank screen", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    // An explicit alert region is shown (never a blank screen) ...
    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/console crashed/i);
    // ... surfacing the error detail ...
    expect(alert).toHaveTextContent(/kaboom in render/i);
    // ... and a keyboard-reachable recovery affordance.
    expect(screen.getByRole("button", { name: /reload console/i })).toBeInTheDocument();
  });
});
