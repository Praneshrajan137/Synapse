import type { Meta, StoryObj } from "@storybook/react";
import { TierBadge } from "./TierBadge";

const meta = {
  title: "Viz/TierBadge",
  component: TierBadge,
  parameters: { layout: "centered" },
  args: { tier: "tier_3" },
} satisfies Meta<typeof TierBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Tier1: Story = { args: { tier: "tier_1", showLatency: true } };
export const Tier2: Story = { args: { tier: "tier_2", showLatency: true } };
export const Tier3: Story = { args: { tier: "tier_3", showLatency: true } };
export const Tier4: Story = { args: { tier: "tier_4", showLatency: true } };

export const AllTiers: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 10 }}>
      <TierBadge tier="tier_1" showLatency />
      <TierBadge tier="tier_2" showLatency />
      <TierBadge tier="tier_3" showLatency />
      <TierBadge tier="tier_4" showLatency />
    </div>
  ),
};
