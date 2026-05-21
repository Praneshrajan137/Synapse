import type { Meta, StoryObj } from "@storybook/react";
import { Search } from "lucide-react";
import { Input } from "./Input";

const meta = {
  title: "Primitives/Input",
  component: Input,
  parameters: { layout: "centered" },
  args: { label: "Override reason" },
  decorators: [
    (Story) => (
      <div style={{ width: 280 }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Input>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: { placeholder: "Why is this decision approved?" },
};

export const WithHint: Story = {
  args: { hint: "Attached to the audit row's human_override.reason" },
};

export const Invalid: Story = {
  args: { invalid: true, hint: "A reason is required to submit an override" },
};

export const WithLeadingIcon: Story = {
  args: {
    label: "Search decisions",
    hideLabel: true,
    placeholder: "Search by id, store, SKU…",
    leading: <Search size={14} />,
  },
};
