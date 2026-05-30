import type { Meta, StoryObj } from "@storybook/react";
import { ThresholdCountdown } from "./ThresholdCountdown";

const T0 = 1_000_000_000_000;

const meta: Meta<typeof ThresholdCountdown> = {
  title: "Compounds/ThresholdCountdown",
  component: ThresholdCountdown,
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          "The spine of an escalation: the bounded HITL decision window (300 s default). " +
          "Makes the cost of NOT acting visible — calming overtrust (the machine isn't " +
          "waiting forever) and undertrust (there's a defined fallback). Stories pass a " +
          "fixed `now` so the rendered time is deterministic.",
      },
    },
  },
  args: { startedAtMs: T0, windowSeconds: 300 },
};
export default meta;

type Story = StoryObj<typeof ThresholdCountdown>;

/** Ample time — calm band. */
export const Calm: Story = { args: { now: T0 + 30_000 } };

/** Under half the window — warn band. */
export const Warn: Story = { args: { now: T0 + 200_000 } };

/** Final stretch — danger band. */
export const Danger: Story = { args: { now: T0 + 270_000 } };

/** Past the window — fallback engaged. */
export const Elapsed: Story = { args: { now: T0 + 320_000 } };

/** A non-default timeout policy. */
export const ExecuteLastKnownGood: Story = {
  args: { now: T0 + 120_000, fallback: "execute_last_known_good" },
};
