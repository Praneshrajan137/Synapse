import type { Meta, StoryObj } from "@storybook/react";
import { Kbd } from "./Kbd";

const meta = {
  title: "Primitives/Kbd",
  component: Kbd,
  parameters: { layout: "centered" },
  args: { keys: ["⌘", "K"] },
} satisfies Meta<typeof Kbd>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Single: Story = { args: { keys: ["W"], label: "What-if" } };
export const Chord: Story = { args: { keys: ["⌘", "K"], label: "Command palette" } };

export const ShortcutList: Story = {
  render: () => (
    <div style={{ display: "grid", gap: 8, color: "var(--color-ink-secondary)" }}>
      {[
        { keys: ["⌘", "K"], desc: "Command palette" },
        { keys: ["W"], desc: "What-if on the twin" },
        { keys: ["F"], desc: "Focus mode" },
        { keys: ["Space"], desc: "Push-to-talk" },
      ].map(({ keys, desc }) => (
        <div key={desc} style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Kbd keys={keys} label={desc} />
          <span style={{ fontSize: 13 }}>{desc}</span>
        </div>
      ))}
    </div>
  ),
};
