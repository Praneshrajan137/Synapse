import { DegradedBanner } from "@ds/compounds/DegradedBanner";
import { ProvenanceChip } from "@ds/compounds/ProvenanceChip";
import { SyntheticBadge } from "@ds/compounds/SyntheticBadge";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
// i18next is a global; load with the same bootstrap the app uses so the
// "common" namespace is registered.
import "@i18n/index";

// ─── ProvenanceChip (FE-INV-034) ──────────────────────────────────────────

describe("ProvenanceChip", () => {
  it("discloses 'provenance unavailable' for a proposal with no provenance (Req 4.7)", () => {
    render(<ProvenanceChip provenance={null} />);
    const chip = screen.getByRole("img");
    expect(chip).toHaveTextContent(/provenance unavailable/i);
  });

  it("discloses 'provenance unavailable' when provenance is incomplete (Req 4.7)", () => {
    // model_version present but feature_source / confidence_basis missing.
    render(<ProvenanceChip provenance={{ model_version: "registry-v1.2.3" }} />);
    const chip = screen.getByRole("img");
    expect(chip).toHaveTextContent(/provenance unavailable/i);
  });

  it("a degraded output is unmissable — label + drained colour class", () => {
    render(
      <ProvenanceChip
        provenance={{
          model_version: "degraded",
          feature_source: "fallback",
          degraded: true,
          confidence_basis: "fallback_floor",
        }}
      />,
    );
    const chip = screen.getByRole("img");
    expect(chip).toHaveTextContent(/degraded/i);
    expect(chip.className).toMatch(/text-state-degraded/);
    // Non-colour channel (INV-CLR-011): the text label + the shape glyph.
    expect(chip.textContent).toContain("▲");
  });

  it("a real output shows the model version and basis detail", () => {
    render(
      <ProvenanceChip
        provenance={{
          model_version: "registry-v1.2.3",
          feature_source: "feast",
          degraded: false,
          confidence_basis: "conformal_interval",
        }}
      />,
    );
    const chip = screen.getByRole("img");
    expect(chip).toHaveTextContent("registry-v1.2.3");
    expect(chip.getAttribute("title")).toContain("conformal interval");
    expect(chip.className).not.toMatch(/text-state-degraded/);
  });
});

// ─── SyntheticBadge (FE-INV-036) ──────────────────────────────────────────

describe("SyntheticBadge", () => {
  it("carries text + dashed ring — never colour alone (INV-CLR-011)", () => {
    render(<SyntheticBadge />);
    const badge = screen.getByRole("img");
    expect(badge).toHaveTextContent(/demo/i);
    expect(badge.className).toMatch(/border-dashed/);
    expect(badge.className).toMatch(/text-state-synthetic/);
    expect(badge.getAttribute("aria-label")).toMatch(/synthetic/i);
  });
});

// ─── DegradedBanner (FE-INV-035) ──────────────────────────────────────────

const mockPosture = vi.hoisted(() => vi.fn());
vi.mock("@hooks/use-posture", () => ({ usePosture: mockPosture }));

describe("DegradedBanner", () => {
  beforeEach(() => {
    mockPosture.mockReset();
  });

  it("renders nothing when the posture is affirmatively healthy", () => {
    mockPosture.mockReturnValue({
      isSuccess: true,
      isPending: false,
      isError: false,
      data: { brownout: { bengaluru: "NONE" }, breakers: { ollama: "closed" }, degraded: false },
    });
    const { container } = render(<DegradedBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names the degradation when brownout/breakers report it", () => {
    mockPosture.mockReturnValue({
      isSuccess: true,
      isPending: false,
      isError: false,
      data: {
        brownout: { bengaluru: "SHED_T4", mumbai: "NONE" },
        breakers: { ollama: "open", postgres: "closed" },
        degraded: true,
      },
    });
    render(<DegradedBanner />);
    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent(/running degraded/i);
    expect(banner).toHaveTextContent(/bengaluru/i);
    expect(banner).toHaveTextContent(/SHED_T4/);
    expect(banner).toHaveTextContent(/ollama/i);
    // The healthy entries are NOT named — only what is degrading the system.
    expect(banner).not.toHaveTextContent(/postgres/);
  });

  it("a posture fetch failure renders 'unknown', never silently green", () => {
    mockPosture.mockReturnValue({
      isSuccess: false,
      isPending: false,
      isError: true,
      data: undefined,
    });
    render(<DegradedBanner />);
    expect(screen.getByRole("status")).toHaveTextContent(/posture unknown/i);
  });

  it("renders nothing only while the very first poll is in flight", () => {
    mockPosture.mockReturnValue({
      isSuccess: false,
      isPending: true,
      isError: false,
      data: undefined,
    });
    const { container } = render(<DegradedBanner />);
    expect(container).toBeEmptyDOMElement();
  });
});
