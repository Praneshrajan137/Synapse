import type { Meta, StoryObj } from "@storybook/react";
import { TierBadge } from "./TierBadge";

const meta: Meta<typeof TierBadge> = {
  title: "Compounds/TierBadge",
  component: TierBadge,
};
export default meta;

type Story = StoryObj<typeof TierBadge>;
export const Tier1: Story = { args: { tier: "tier_1" } };
export const Tier2: Story = { args: { tier: "tier_2" } };
export const Tier3: Story = { args: { tier: "tier_3" } };
export const Tier4: Story = { args: { tier: "tier_4" } };
