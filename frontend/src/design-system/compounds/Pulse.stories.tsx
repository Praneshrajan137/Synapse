import type { Meta, StoryObj } from "@storybook/react";
import { Pulse } from "./Pulse";

const meta: Meta<typeof Pulse> = {
  title: "Compounds/Pulse",
  component: Pulse,
  parameters: {
    layout: "centered",
    backgrounds: { default: "dark" },
    docs: {
      description: {
        component:
          "The Cortex's ambient heartbeat — the firehose as weather. Beat = decision " +
          "rate; colour temperature = aggregate confidence on the gate-anchored OKLCH " +
          "diverging scale with VSUP suppression; ring texture = tier mix. Quiet by " +
          "default; honours prefers-reduced-motion (the breath stops, numerals carry all).",
      },
    },
  },
  args: {
    rate: 42,
    confidence: 0.88,
    tierMix: { tier_1: 80, tier_2: 14, tier_3: 4, tier_4: 2 },
  },
};
export default meta;

type Story = StoryObj<typeof Pulse>;

/** Healthy autonomy — calm, cool, high confidence. The resting state. */
export const Autonomous: Story = {};

/** On the I-5 gate — confidence in the 0.70–0.80 escalation band. */
export const OnTheGate: Story = {
  args: { rate: 28, confidence: 0.74, tierMix: { tier_1: 40, tier_2: 30, tier_3: 20, tier_4: 10 } },
};

/** Low confidence — colour drains (VSUP), the system would escalate. */
export const NeedsReview: Story = {
  args: { rate: 16, confidence: 0.58, tierMix: { tier_1: 20, tier_2: 20, tier_3: 30, tier_4: 30 } },
};

/** Idle — no decisions in the window; slow breath, quiet ring. */
export const Idle: Story = {
  args: { rate: 0, confidence: 0.92, tierMix: {} },
};

/** No signal yet — honest empty state; never a fabricated confident glow (P7). */
export const NoSignal: Story = {
  args: { rate: 0, confidence: null, tierMix: {} },
};

/** Heavy deliberation — Tier-4-dominated mix under load. */
export const UnderLoad: Story = {
  args: {
    rate: 110,
    confidence: 0.81,
    tierMix: { tier_1: 30, tier_2: 25, tier_3: 25, tier_4: 20 },
  },
};

/** Light theme variant of the diverging scale. */
export const LightTheme: Story = {
  args: { theme: "light" },
  parameters: { backgrounds: { default: "light" } },
};
