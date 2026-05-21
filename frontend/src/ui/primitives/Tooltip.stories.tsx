import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";
import { Tooltip, TooltipProvider } from "./Tooltip";

const meta = {
  title: "Primitives/Tooltip",
  component: Tooltip,
  parameters: { layout: "centered" },
  args: {
    content: "Replay this decision with full context",
    children: <Button variant="ghost">Replay</Button>,
  },
  decorators: [
    (Story) => (
      <TooltipProvider>
        <Story />
      </TooltipProvider>
    ),
  ],
} satisfies Meta<typeof Tooltip>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    content: "Replay this decision with full context",
    children: <Button variant="ghost">Replay</Button>,
  },
};

export const Sides: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 24 }}>
      {(["top", "bottom", "left", "right"] as const).map((side) => (
        <Tooltip key={side} side={side} content={`Tooltip on ${side}`}>
          <Button variant="secondary">{side}</Button>
        </Tooltip>
      ))}
    </div>
  ),
};
