import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { ConfidenceGauge } from "./ConfidenceGauge";

describe("ConfidenceGauge", () => {
  it("exposes a meter with the confidence value", () => {
    render(<ConfidenceGauge value={0.82} />);
    const meter = screen.getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuenow", "0.82");
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "1");
  });

  it("clamps out-of-range values into [0, 1]", () => {
    render(<ConfidenceGauge value={1.7} label="overshoot" />);
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "1");
  });

  it("renders the rounded percentage", () => {
    render(<ConfidenceGauge value={0.456} />);
    expect(screen.getByText("46")).toBeInTheDocument();
  });

  it("derives an accessible label when none is given", () => {
    render(<ConfidenceGauge value={0.9} />);
    expect(screen.getByRole("meter")).toHaveAccessibleName("Confidence 90 percent");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <ConfidenceGauge value={0.42} label="Decision confidence" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
