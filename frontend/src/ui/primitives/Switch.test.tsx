import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import { Switch } from "./Switch";

describe("Switch", () => {
  it("exposes a switch role", () => {
    render(<Switch aria-label="Sound" />);
    expect(screen.getByRole("switch", { name: "Sound" })).toBeInTheDocument();
  });

  it("toggles checked state on click", async () => {
    const onCheckedChange = vi.fn();
    render(<Switch aria-label="Sound" onCheckedChange={onCheckedChange} />);
    await userEvent.click(screen.getByRole("switch"));
    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });

  it("toggles with the keyboard", async () => {
    const onCheckedChange = vi.fn();
    render(<Switch aria-label="Sound" onCheckedChange={onCheckedChange} />);
    screen.getByRole("switch").focus();
    await userEvent.keyboard(" ");
    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });

  it("respects the disabled state", async () => {
    const onCheckedChange = vi.fn();
    render(<Switch aria-label="Sound" disabled onCheckedChange={onCheckedChange} />);
    await userEvent.click(screen.getByRole("switch"));
    expect(onCheckedChange).not.toHaveBeenCalled();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Switch aria-label="Enable sound cues" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
