import { CouncilStrip } from "@ds/compounds/CouncilStrip";
import { DivergenceTrace } from "@ds/compounds/DivergenceTrace";
import { OutcomeBand } from "@ds/compounds/OutcomeBand";
import { ParetoParallel } from "@ds/compounds/ParetoParallel";
import { Pulse } from "@ds/compounds/Pulse";
import { ThresholdCountdown } from "@ds/compounds/ThresholdCountdown";
import { PARETO_OBJECTIVES } from "@lib/pareto";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

// jsdom cannot compute OKLCH / color-mix contrast, so the color-contrast rule
// is disabled here; perceptual contrast is verified separately by the design-
// system's APCA/WCAG oracle (design-system/color/tests). These checks catch the
// structural a11y faults that matter for the new SENSORIUM compounds: roles,
// names, listbox/option semantics, button labelling, etc.
const AXE_OPTS = { rules: { "color-contrast": { enabled: false } } } as const;

function paretoRow(values: number[]): Record<string, number> {
  const r: Record<string, number> = {};
  PARETO_OBJECTIVES.forEach((o, i) => {
    r[o] = values[i] ?? 0.5;
  });
  return r;
}

describe("a11y — new SENSORIUM compounds have no axe violations", () => {
  it("Pulse", async () => {
    const { container } = render(<Pulse rate={42} confidence={0.88} tierMix={{ tier_1: 8 }} />);
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });

  it("Pulse (no-signal honest state)", async () => {
    const { container } = render(<Pulse rate={0} confidence={null} />);
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });

  it("CouncilStrip (display-only + degraded states)", async () => {
    const { container } = render(
      <CouncilStrip
        states={{
          demand_prophet: { status: "healthy", active: true },
          pricing_oracle: { status: "degraded" },
          routing_navigator: { status: "unreachable" },
        }}
      />,
    );
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });

  it("ParetoParallel", async () => {
    const front = [
      paretoRow([0.9, 0.2, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
      paretoRow([0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7]),
    ];
    const { container } = render(<ParetoParallel front={front} />);
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });

  it("ParetoParallel (empty/fast-path state)", async () => {
    const { container } = render(<ParetoParallel front={[]} />);
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });

  it("ThresholdCountdown", async () => {
    const t0 = 1_000_000;
    const { container } = render(<ThresholdCountdown startedAtMs={t0} now={t0 + 120_000} />);
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });

  it("DivergenceTrace", async () => {
    const { container } = render(<DivergenceTrace series={[0.02, 0.05, 0.12, 0.08]} />);
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });

  it("OutcomeBand", async () => {
    const samples = Array.from({ length: 40 }, (_, i) => i);
    const { container } = render(<OutcomeBand samples={samples} unit="m" label="Delivery time" />);
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });
});
