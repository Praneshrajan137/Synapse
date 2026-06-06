import { PARETO_OBJECTIVES } from "@lib/pareto";
import type { Meta, StoryObj } from "@storybook/react";
import { ParetoParallel } from "./ParetoParallel";

function row(values: number[]): Record<string, number> {
  const r: Record<string, number> = {};
  PARETO_OBJECTIVES.forEach((o, i) => {
    r[o] = values[i] ?? 0.5;
  });
  return r;
}

const meta: Meta<typeof ParetoParallel> = {
  title: "Compounds/ParetoParallel",
  component: ParetoParallel,
  parameters: {
    layout: "padded",
    backgrounds: { default: "dark" },
    docs: {
      description: {
        component:
          "The orchestrator's 8-objective consensus front as parallel coordinates. " +
          "Each axis is tinted by its owning agent's frozen hue; the knee point (the " +
          "chosen solution, recomputed client-side from front + weights) is bold; the " +
          "objective weights ride atop each axis as bars — the Steering lever made visible.",
      },
    },
  },
  args: {
    front: [
      row([0.9, 0.2, 0.5, 0.6, 0.5, 0.4, 0.5, 0.5]),
      row([0.75, 0.78, 0.72, 0.7, 0.74, 0.71, 0.73, 0.69]),
      row([0.2, 0.9, 0.4, 0.5, 0.6, 0.5, 0.5, 0.45]),
      row([0.5, 0.5, 0.9, 0.4, 0.5, 0.6, 0.5, 0.55]),
      row([0.55, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.92]),
    ],
    weights: {
      demand_accuracy: 1,
      route_efficiency: 1,
      inventory_fill_rate: 1.2,
      freshness_score: 1,
      pricing_revenue: 0.8,
      disruption_readiness: 1,
      supplier_reliability: 0.8,
      carbon_efficiency: 0.6,
    },
  },
};
export default meta;

type Story = StoryObj<typeof ParetoParallel>;

/** Default meta-RL weights — the balanced knee. */
export const DefaultWeights: Story = {};

/** Sustainability weighted hard — the knee shifts to the carbon-strong solution. */
export const CarbonWeighted: Story = {
  args: { weights: { carbon_efficiency: 4 } },
};

/** Route efficiency weighted hard — the knee shifts to the route-strong solution. */
export const RouteWeighted: Story = {
  args: { weights: { route_efficiency: 4 } },
};

/** Fast-path decision — no front recorded (honest empty state). */
export const NoFront: Story = {
  args: { front: [] },
};
