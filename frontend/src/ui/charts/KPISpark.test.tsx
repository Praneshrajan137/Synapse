import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { KPISpark } from "./KPISpark";

describe("KPISpark", () => {
  it("renders a labelled sparkline", () => {
    render(<KPISpark data={[1, 2, 3, 2, 4]} label="Fill rate, last 24h" />);
    expect(screen.getByRole("img", { name: "Fill rate, last 24h" })).toBeInTheDocument();
  });

  it("draws a polyline for the series", () => {
    const { container } = render(<KPISpark data={[10, 20, 15, 30]} label="series" />);
    expect(container.querySelectorAll("polyline").length).toBeGreaterThan(0);
  });

  it("handles a flat series without dividing by zero", () => {
    const { container } = render(<KPISpark data={[5, 5, 5, 5]} label="flat" />);
    const line = container.querySelector("polyline");
    expect(line?.getAttribute("points")).not.toContain("NaN");
  });

  it("handles a single data point", () => {
    const { container } = render(<KPISpark data={[42]} label="single" />);
    expect(container.querySelector("polyline")?.getAttribute("points")).not.toContain(
      "NaN",
    );
  });

  it("renders a conformal band when provided", () => {
    const { container } = render(
      <KPISpark
        data={[10, 12, 11, 13]}
        band={{ lower: [8, 10, 9, 11], upper: [12, 14, 13, 15] }}
        label="banded"
      />,
    );
    expect(container.querySelector("path")).not.toBeNull();
  });

  it("degrades gracefully with empty data", () => {
    const { container } = render(<KPISpark data={[]} />);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <KPISpark data={[3, 6, 4, 8, 7]} label="On-time delivery trend" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
