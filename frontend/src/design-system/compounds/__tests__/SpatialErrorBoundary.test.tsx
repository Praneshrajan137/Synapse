import { SpatialErrorBoundary } from "@ds/compounds/SpatialErrorBoundary";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function Boom(): never {
  throw new Error("webgl chunk failed");
}

describe("SpatialErrorBoundary", () => {
  beforeEach(() => {
    // React logs the caught error to console.error; silence it for a clean run.
    vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children when they do not throw", () => {
    render(
      <SpatialErrorBoundary label="living map">
        <p>the canvas</p>
      </SpatialErrorBoundary>,
    );
    expect(screen.getByText("the canvas")).toBeInTheDocument();
  });

  it("renders an error state with a retry affordance instead of a blank canvas", () => {
    render(
      <SpatialErrorBoundary label="living map">
        <Boom />
      </SpatialErrorBoundary>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("data-universal-state", "error");
    expect(screen.getByText(/the living map failed to load/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("remounts the subtree when retry is activated (fresh render attempt)", async () => {
    let shouldThrow = true;
    function Flaky() {
      if (shouldThrow) throw new Error("first attempt fails");
      return <p>recovered canvas</p>;
    }

    render(
      <SpatialErrorBoundary label="supply network">
        <Flaky />
      </SpatialErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();

    shouldThrow = false;
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(screen.getByText("recovered canvas")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
