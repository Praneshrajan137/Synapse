import type { Meta, StoryObj } from "@storybook/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./Tabs";

const meta = {
  title: "Primitives/Tabs",
  component: Tabs,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Tabs>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <Tabs defaultValue="proposals" style={{ width: 360 }}>
      <TabsList>
        <TabsTrigger value="proposals">Proposals</TabsTrigger>
        <TabsTrigger value="context">Context</TabsTrigger>
        <TabsTrigger value="audit">Audit</TabsTrigger>
      </TabsList>
      <TabsContent value="proposals">
        <p style={{ color: "var(--color-ink-secondary)", fontSize: 14 }}>
          Ranked agent proposals for this decision.
        </p>
      </TabsContent>
      <TabsContent value="context">
        <p style={{ color: "var(--color-ink-secondary)", fontSize: 14 }}>
          The append-only context message tape.
        </p>
      </TabsContent>
      <TabsContent value="audit">
        <p style={{ color: "var(--color-ink-secondary)", fontSize: 14 }}>
          The immutable audit row and provenance trail.
        </p>
      </TabsContent>
    </Tabs>
  ),
};
