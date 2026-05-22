import type { Meta, StoryObj } from "@storybook/react";
import { ConfidenceChip } from "./ConfidenceChip";

const meta: Meta<typeof ConfidenceChip> = {
  title: "Compounds/ConfidenceChip",
  component: ConfidenceChip,
  args: { value: 0.85 },
};
export default meta;

type Story = StoryObj<typeof ConfidenceChip>;
export const Ok: Story = { args: { value: 0.95 } };
export const Warn: Story = { args: { value: 0.78 } };
export const Risk: Story = { args: { value: 0.55 } };
export const WithBand: Story = {
  args: { value: 0.78, band: { lower: 0.62, upper: 0.91 } },
};
