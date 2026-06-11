import { CouncilStrip, processStateFor } from "@ds/compounds/CouncilStrip";
import { SyntheticBadge } from "@ds/compounds/SyntheticBadge";
import { ThemeToggle } from "@ds/compounds/ThemeToggle";
import { useThemeStore } from "@state/theme.store";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
// i18next global bootstrap (registers the "common" namespace).
import "@i18n/index";

// ─── Process-state grammar (ADR-044 / INV-CLR-017) ─────────────────────────

describe("processStateFor — honest derivation only", () => {
  it("maps the three derivable states", () => {
    expect(processStateFor({ status: "healthy", active: true })).toBe("acting");
    expect(processStateFor({ status: "healthy", active: false })).toBe("waiting");
    expect(processStateFor({ status: "healthy" })).toBe("waiting");
    expect(processStateFor({ status: "unreachable" })).toBe("interrupted");
  });

  it("never fabricates a process state for health states outside the grammar", () => {
    // thinking/debating need per-agent phase events the backend doesn't
    // push yet — degraded/unknown health must NOT masquerade as cognition.
    expect(processStateFor({ status: "degraded" })).toBeNull();
    expect(processStateFor({ status: "unknown" })).toBeNull();
  });
});

// ─── FE-INV-040: animation is never the sole channel ───────────────────────

describe("FE-INV-040 — reduced-motion fallbacks preserve the information", () => {
  it("CouncilStrip states are distinguishable by STATUS WORD, not animation", () => {
    render(
      <CouncilStrip
        states={{
          demand_prophet: { status: "healthy", active: true },
          routing_navigator: { status: "healthy", active: false },
          inventory_sentinel: { status: "unreachable" },
          freshness_guardian: { status: "degraded" },
        }}
      />,
    );
    // With every animation frozen (prefers-reduced-motion zeroes the motion
    // vars), the text still carries each state.
    expect(screen.getByLabelText(/Demand Prophet.*active in a live decision/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Routing Navigator: live/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Inventory Sentinel: offline/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Freshness Guardian: degraded/i)).toBeInTheDocument();
  });

  it("CouncilStrip exposes the process state as a data attribute (grammar hook)", () => {
    render(
      <CouncilStrip
        states={{
          demand_prophet: { status: "healthy", active: true },
          inventory_sentinel: { status: "unreachable" },
        }}
      />,
    );
    const acting = screen.getByLabelText(/Demand Prophet/i);
    const interrupted = screen.getByLabelText(/Inventory Sentinel/i);
    expect(acting.getAttribute("data-process-state")).toBe("acting");
    expect(interrupted.getAttribute("data-process-state")).toBe("interrupted");
  });

  it("SyntheticBadge stays legible with the pulse frozen (dashed ring + label)", () => {
    render(<SyntheticBadge />);
    const badge = screen.getByRole("img");
    // The animated class is decoration; the dashed border + the text label
    // carry the state when animation-duration is zeroed.
    expect(badge.className).toMatch(/border-dashed/);
    expect(badge).toHaveTextContent(/demo/i);
  });
});

// ─── ThemeToggle ────────────────────────────────────────────────────────────

describe("ThemeToggle", () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: "dark" });
    document.documentElement.removeAttribute("data-theme");
  });

  it("renders the three themes with the current one pressed", () => {
    render(<ThemeToggle />);
    expect(screen.getByLabelText(/dark theme/i)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText(/light theme/i)).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByLabelText(/high-contrast theme/i)).toHaveAttribute("aria-pressed", "false");
  });

  it("selecting a theme updates the store AND the document attribute", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByLabelText(/light theme/i));
    expect(useThemeStore.getState().theme).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("high-contrast is a first-class option, not hidden behind a cycle", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByLabelText(/high-contrast theme/i));
    expect(useThemeStore.getState().theme).toBe("hc");
    expect(document.documentElement.getAttribute("data-theme")).toBe("hc");
  });
});
