import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders its label and defaults to type=button", () => {
    render(<Button>Approve</Button>);
    expect(screen.getByRole("button", { name: "Approve" })).toHaveAttribute(
      "type",
      "button",
    );
  });

  it("invokes onClick when activated", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Run</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("does not fire onClick while disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Run
      </Button>,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("renders as its child element when asChild is set", () => {
    render(
      <Button asChild variant="signal">
        <a href="/theater">Open Theater</a>
      </Button>,
    );
    expect(screen.getByRole("link", { name: "Open Theater" })).toBeInTheDocument();
  });

  it("is keyboard activatable", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Run</Button>);
    screen.getByRole("button").focus();
    await userEvent.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalled();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Button variant="danger">Reject decision</Button>);
    expect(await axe(container)).toHaveNoViolations();
  });
});
