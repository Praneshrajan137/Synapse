import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders its text content", () => {
    render(<Badge tone="ok">Executed</Badge>);
    expect(screen.getByText("Executed")).toBeInTheDocument();
  });

  it("pairs color with a text label (status is never color-only)", () => {
    render(<Badge tone="stop">Escalated</Badge>);
    // The accessible content carries the meaning, not just the hue.
    expect(screen.getByText("Escalated")).toBeVisible();
  });

  it("renders an optional decorative dot hidden from assistive tech", () => {
    const { container } = render(
      <Badge tone="live" dot>
        Streaming
      </Badge>,
    );
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });

  it("has no accessibility violations across tones", async () => {
    const { container } = render(
      <div>
        <Badge tone="neutral">Neutral</Badge>
        <Badge tone="warn">Pending</Badge>
        <Badge tone="ok">Healthy</Badge>
        <Badge tone="stop">Failed</Badge>
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
