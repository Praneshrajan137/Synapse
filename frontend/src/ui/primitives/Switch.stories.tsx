import type { Meta, StoryObj } from "@storybook/react";
import { Switch } from "./Switch";

const meta = {
  title: "Primitives/Switch",
  component: Switch,
  parameters: { layout: "centered" },
  args: { "aria-label": "Enable sound cues" },
} satisfies Meta<typeof Switch>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Off: Story = {};
export const On: Story = { args: { defaultChecked: true } };
export const Disabled: Story = { args: { disabled: true } };

export const Labelled: Story = {
  render: () => (
    <div
      style={{
        display: "flex",
        gap: 10,
        alignItems: "center",
        color: "var(--color-ink-primary)",
      }}
    >
      <Switch aria-label="Sound cues" />
      <span style={{ fontSize: 14 }}>Sound cues</span>
    </div>
  ),
};
