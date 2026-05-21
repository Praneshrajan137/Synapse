import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { Input } from "./Input";

describe("Input", () => {
  it("associates its label with the field", () => {
    render(<Input label="Override reason" />);
    expect(screen.getByLabelText("Override reason")).toBeInTheDocument();
  });

  it("keeps an accessible name when the label is visually hidden", () => {
    render(<Input label="Search decisions" hideLabel />);
    expect(screen.getByLabelText("Search decisions")).toBeInTheDocument();
  });

  it("accepts typed input", async () => {
    render(<Input label="Reason" />);
    const field = screen.getByLabelText("Reason");
    await userEvent.type(field, "supplier confirmed");
    expect(field).toHaveValue("supplier confirmed");
  });

  it("marks itself invalid and links the hint for screen readers", () => {
    render(<Input label="Reason" invalid hint="Reason is required" />);
    const field = screen.getByLabelText("Reason");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription("Reason is required");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Input label="Override reason" hint="Be specific" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
