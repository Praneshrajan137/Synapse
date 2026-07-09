import { BuildSHAChip } from "@ds/compounds/BuildSHAChip";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Req 8.6 / 14.4 — the deployed build SHA is surfaced in the Shell (this chip
// is mounted in the Shell header) so an operator can distinguish a stale cached
// UI from a current deploy. Under test the CD-injected env is absent, so the
// chip reports the local-build sentinel ("dev") — still visible and labelled.

describe("BuildSHAChip — Req 8.6/14.4 build-SHA visibility", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      writable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a labelled, visible build-version affordance", () => {
    render(<BuildSHAChip />);
    const chip = screen.getByRole("button", { name: /build version/i });
    expect(chip).toBeInTheDocument();
    // The sentinel SHA is visible as text (not hidden).
    expect(chip).toHaveTextContent("dev");
  });

  it("copies the build SHA to the clipboard when activated (screenshot-triageable)", async () => {
    render(<BuildSHAChip />);
    await userEvent.click(screen.getByRole("button", { name: /build version/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);
    expect(vi.mocked(navigator.clipboard.writeText).mock.calls[0]?.[0]).toMatch(/^sha=/);
  });
});
