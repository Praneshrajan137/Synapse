import { InitiatorBadge } from "@ds/compounds";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
// Bootstrap i18n with the same resources the app uses so t() resolves copy.
import "@i18n/index";

// ADR-053 — the three-way decision origin. The load-bearing guarantee is that
// an autonomous decision is visually + textually distinct from a demo pulse:
// conflating "the system decided on its own" with "staged traffic" is the exact
// lie the typed initiator replaces. Each variant carries a non-colour signal
// (label + glyph + border) so it survives CVD / grayscale (INV-CLR-011).

describe("InitiatorBadge", () => {
  it("labels an autonomous decision distinctly from a synthetic one", () => {
    const { unmount } = render(<InitiatorBadge initiator="autonomous" />);
    expect(screen.getByText("Autonomous")).toBeInTheDocument();
    unmount();
    render(<InitiatorBadge initiator="synthetic" />);
    expect(screen.getByText("Demo")).toBeInTheDocument();
    // Autonomous label must NOT appear for a synthetic pulse.
    expect(screen.queryByText("Autonomous")).not.toBeInTheDocument();
  });

  it("labels an operator decision", () => {
    render(<InitiatorBadge initiator="operator" />);
    expect(screen.getByText("Operator")).toBeInTheDocument();
  });

  it("carries an aria-label describing the origin (non-colour signal)", () => {
    render(<InitiatorBadge initiator="autonomous" />);
    const badge = screen.getByRole("img");
    expect(badge.getAttribute("aria-label") ?? "").toMatch(/autonomous|no human/i);
  });

  it("uses the accent (not the synthetic) token for autonomous", () => {
    const { container } = render(<InitiatorBadge initiator="autonomous" />);
    const el = container.querySelector("span[style]") as HTMLElement | null;
    // Autonomous borders with the brand/accent var; synthetic borders violet.
    expect(el?.style.borderColor).toContain("--syn-accent");
  });
});
