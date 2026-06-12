import type { Meta, StoryObj } from "@storybook/react";
import { Badge } from "../primitives";
import { PageHeader } from "./PageHeader";

const meta: Meta<typeof PageHeader> = {
  title: "Compounds/PageHeader",
  component: PageHeader,
};
export default meta;

type Story = StoryObj<typeof PageHeader>;

export const Default: Story = {
  args: {
    title: "Decision Theater",
    subtitle: "Replay any consensus decision phase by phase, with the full audit anatomy.",
  },
};

export const Hero: Story = {
  args: {
    size: "hero",
    title: "Mission Control",
    subtitle: "Live KPI band, decision firehose, and the city's living map.",
    status: <Badge tone="success">Live</Badge>,
  },
};
