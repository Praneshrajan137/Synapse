import type { Meta, StoryObj } from "@storybook/react";
import { SyntheticBadge } from "./SyntheticBadge";

const meta: Meta<typeof SyntheticBadge> = {
  title: "Compounds/SyntheticBadge",
  component: SyntheticBadge,
};
export default meta;

type Story = StoryObj<typeof SyntheticBadge>;
export const Default: Story = {};
