import { signal } from "@/ui/tokens";
import type { Meta, StoryObj } from "@storybook/react";
import { KPISpark } from "./KPISpark";

const fillRate = [0.91, 0.93, 0.92, 0.95, 0.94, 0.96, 0.97, 0.95, 0.98];

const meta = {
  title: "Viz/KPISpark",
  component: KPISpark,
  parameters: { layout: "centered" },
  args: { data: fillRate },
} satisfies Meta<typeof KPISpark>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: { data: fillRate, label: "Fill rate, last 24h", width: 140, height: 40 },
};

export const WithConformalBand: Story = {
  args: {
    data: fillRate,
    band: {
      lower: fillRate.map((v) => v - 0.04),
      upper: fillRate.map((v) => v + 0.04),
    },
    label: "Forecast with 90% conformal band",
    width: 180,
    height: 56,
    color: signal.think,
  },
};

export const Inline: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
      <span style={{ color: "var(--color-ink-secondary)", fontSize: 13 }}>On-time %</span>
      <KPISpark
        data={[88, 90, 87, 92, 94, 93, 96]}
        label="On-time delivery"
        color={signal.ok}
      />
    </div>
  ),
};
