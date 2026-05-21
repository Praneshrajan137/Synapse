import type { Meta, StoryObj } from "@storybook/react";
import { Badge } from "./Badge";

const meta = {
  title: "Primitives/Badge",
  component: Badge,
  parameters: { layout: "centered" },
  args: { children: "Executed" },
} satisfies Meta<typeof Badge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Neutral: Story = { args: { tone: "neutral", children: "Pending" } };
export const Live: Story = { args: { tone: "live", children: "Streaming", dot: true } };
export const Ok: Story = { args: { tone: "ok", children: "Healthy", dot: true } };
export const Warn: Story = { args: { tone: "warn", children: "Escalating", dot: true } };
export const Stop: Story = { args: { tone: "stop", children: "Escalated", dot: true } };

export const AllTones: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      <Badge tone="neutral">Neutral</Badge>
      <Badge tone="live" dot>
        Live
      </Badge>
      <Badge tone="think" dot>
        Reasoning
      </Badge>
      <Badge tone="warn" dot>
        Attention
      </Badge>
      <Badge tone="stop" dot>
        Escalated
      </Badge>
      <Badge tone="ok" dot>
        Executed
      </Badge>
      <Badge tone="trace" dot>
        Audited
      </Badge>
    </div>
  ),
};
