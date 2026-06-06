import type { Meta, StoryObj } from "@storybook/react";
import { OutcomeBand } from "./OutcomeBand";

// A right-skewed delivery-time sample (Monte-Carlo-ish).
const samples = Array.from({ length: 200 }, () => {
  const u = Math.random();
  return 6 + Math.round((-Math.log(1 - u) * 4 + Math.random() * 2) * 10) / 10;
});

const meta: Meta<typeof OutcomeBand> = {
  title: "Compounds/OutcomeBand",
  component: OutcomeBand,
  parameters: { layout: "padded", backgrounds: { default: "dark" } },
  args: { samples, unit: "m", label: "Delivery time" },
};
export default meta;
type Story = StoryObj<typeof OutcomeBand>;

export const Distribution: Story = {};
export const WithSLA: Story = { args: { threshold: 15 } };
export const TooFew: Story = { args: { samples: [8, 9, 10] } };
