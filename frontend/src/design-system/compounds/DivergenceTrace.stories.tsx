import type { Meta, StoryObj } from "@storybook/react";
import { DivergenceTrace } from "./DivergenceTrace";

const meta: Meta<typeof DivergenceTrace> = {
  title: "Compounds/DivergenceTrace",
  component: DivergenceTrace,
  // Twin Lab renders the trace as its own card, `className="syn-card p-3"`
  // (src/surfaces/twin-lab/TwinLab.tsx:115), so its text sits on `surface`.
  parameters: { layout: "padded", backgrounds: { default: "surface" } },
};
export default meta;
type Story = StoryObj<typeof DivergenceTrace>;

export const Calm: Story = { args: { series: [0.02, 0.03, 0.025, 0.04, 0.03, 0.02, 0.035] } };
export const Drifting: Story = {
  args: { series: [0.02, 0.04, 0.06, 0.08, 0.11, 0.14, 0.13, 0.16] },
};
export const Empty: Story = { args: { series: [] } };
