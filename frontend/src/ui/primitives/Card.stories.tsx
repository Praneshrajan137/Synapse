import { signal } from "@/ui/tokens";
import type { Meta, StoryObj } from "@storybook/react";
import { Card, CardBody, CardHeader, CardTitle } from "./Card";

const meta = {
  title: "Primitives/Card",
  component: Card,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Card>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <Card style={{ width: 320 }}>
      <CardHeader>
        <CardTitle>Decision tape</CardTitle>
      </CardHeader>
      <CardBody>
        <p style={{ color: "var(--color-ink-secondary)", fontSize: 14 }}>
          The append-only stream of orchestrator decisions.
        </p>
      </CardBody>
    </Card>
  ),
};

export const WithAccent: Story = {
  render: () => (
    <Card style={{ width: 320 }} accent={signal.think}>
      <CardHeader>
        <CardTitle>LLM reasoning</CardTitle>
      </CardHeader>
      <CardBody>
        <p style={{ color: "var(--color-ink-secondary)", fontSize: 14 }}>
          A panel marked with the reasoning signal accent.
        </p>
      </CardBody>
    </Card>
  ),
};

export const Tones: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 12 }}>
      {(["paper", "elevated", "membrane"] as const).map((tone) => (
        <Card key={tone} tone={tone} style={{ width: 140, height: 90 }}>
          <CardBody>
            <span style={{ color: "var(--color-ink-secondary)", fontSize: 13 }}>
              {tone}
            </span>
          </CardBody>
        </Card>
      ))}
    </div>
  ),
};
