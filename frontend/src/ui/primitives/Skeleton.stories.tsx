import type { Meta, StoryObj } from "@storybook/react";
import { Skeleton } from "./Skeleton";

const meta = {
  title: "Primitives/Skeleton",
  component: Skeleton,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Skeleton>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Line: Story = { args: { shape: "line", style: { width: 200 } } };
export const Circle: Story = { args: { shape: "circle", style: { width: 48 } } };

export const DecisionRowLoading: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 12, alignItems: "center", width: 320 }}>
      <Skeleton shape="circle" style={{ width: 32 }} />
      <div style={{ display: "grid", gap: 6, flex: 1 }}>
        <Skeleton shape="line" style={{ width: "70%" }} />
        <Skeleton shape="line" style={{ width: "40%" }} />
      </div>
    </div>
  ),
};
