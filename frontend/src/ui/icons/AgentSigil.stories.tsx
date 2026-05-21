import { AGENT_NAMES } from "@/ui/tokens";
import type { Meta, StoryObj } from "@storybook/react";
import { AGENT_LABEL, AgentSigil } from "./AgentSigil";

const meta = {
  title: "Icons/AgentSigil",
  component: AgentSigil,
  parameters: { layout: "centered" },
  args: { agent: "demand_prophet", size: 48 },
} satisfies Meta<typeof AgentSigil>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Single: Story = {
  args: { agent: "demand_prophet", size: 64, title: "Demand Prophet" },
};

export const TheEight: Story = {
  render: () => (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: 28,
        padding: 16,
      }}
    >
      {AGENT_NAMES.map((agent) => (
        <div
          key={agent}
          style={{ display: "grid", justifyItems: "center", gap: 8, width: 120 }}
        >
          <AgentSigil agent={agent} size={52} title={AGENT_LABEL[agent]} />
          <span
            style={{
              fontSize: 11,
              color: "var(--color-ink-secondary)",
              textAlign: "center",
            }}
          >
            {AGENT_LABEL[agent]}
          </span>
        </div>
      ))}
    </div>
  ),
};

export const Sizes: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      {[16, 24, 32, 48, 64].map((size) => (
        <AgentSigil key={size} agent="routing_navigator" size={size} />
      ))}
    </div>
  ),
};
