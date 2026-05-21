import type { Meta, StoryObj } from "@storybook/react";
import { ConfidenceGauge } from "./ConfidenceGauge";

const meta = {
  title: "Viz/ConfidenceGauge",
  component: ConfidenceGauge,
  parameters: { layout: "centered" },
  args: { value: 0.82, size: 80 },
} satisfies Meta<typeof ConfidenceGauge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Confident: Story = { args: { value: 0.94 } };
export const Live: Story = { args: { value: 0.72 } };
export const Uncertain: Story = { args: { value: 0.52 } };
export const Escalating: Story = { args: { value: 0.31 } };

export const Band: Story = {
  name: "Across the confidence band",
  render: () => (
    <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
      {[0.97, 0.78, 0.6, 0.42, 0.18].map((v) => (
        <ConfidenceGauge key={v} value={v} size={72} />
      ))}
    </div>
  ),
};
