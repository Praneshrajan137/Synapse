import { AGENT_NAMES } from "@lib/agent-identity";
import type { Meta, StoryObj } from "@storybook/react";
import { CouncilStrip } from "./CouncilStrip";

const meta: Meta<typeof CouncilStrip> = {
  title: "Compounds/CouncilStrip",
  component: CouncilStrip,
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          "The eight specialist minds as an ambient presence row. Identity hue is " +
          "rationed — drained toward neutral at rest, full on activity (quiet by " +
          "default). Degradation is a designed, first-class state shown as a word, " +
          "never a fake green (honesty contract).",
      },
    },
  },
};
export default meta;

type Story = StoryObj<typeof CouncilStrip>;

/** All healthy and quiet — a calm council is near-monochrome. */
export const RestingHealthy: Story = {
  args: {
    states: Object.fromEntries(AGENT_NAMES.map((a) => [a, { status: "healthy" as const }])),
  },
};

/** A live decision in flight — three agents active and re-chroma'd. */
export const LiveDecision: Story = {
  args: {
    states: {
      demand_prophet: { status: "healthy", active: true, latencyP99Ms: 84, calibration90: 0.91 },
      pricing_oracle: { status: "healthy", active: true, latencyP99Ms: 120, calibration90: 0.88 },
      routing_navigator: { status: "healthy", active: true, latencyP99Ms: 64 },
      inventory_sentinel: { status: "healthy" },
      freshness_guardian: { status: "healthy" },
      disruption_shield: { status: "healthy" },
      supplier_trust: { status: "healthy" },
      sustainability_agent: { status: "healthy" },
    },
  },
};

/** Degraded + offline — honest failure states (P7). */
export const Degraded: Story = {
  args: {
    states: {
      demand_prophet: { status: "healthy", active: true },
      pricing_oracle: { status: "degraded", latencyP99Ms: 4200 },
      disruption_shield: { status: "unreachable" },
      routing_navigator: { status: "healthy" },
    },
  },
};

/** Unknown — no data yet; nothing is painted reassuringly green. */
export const Unknown: Story = {};

/** Interactive — clicking an agent fires onSelectAgent. */
export const Interactive: Story = {
  args: {
    states: Object.fromEntries(AGENT_NAMES.map((a) => [a, { status: "healthy" as const }])),
    selectedAgent: "freshness_guardian",
    onSelectAgent: () => undefined,
  },
};
