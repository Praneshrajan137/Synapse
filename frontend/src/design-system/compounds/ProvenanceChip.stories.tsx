import type { Meta, StoryObj } from "@storybook/react";
import { ProvenanceChip } from "./ProvenanceChip";

const meta: Meta<typeof ProvenanceChip> = {
  title: "Compounds/ProvenanceChip",
  component: ProvenanceChip,
};
export default meta;

type Story = StoryObj<typeof ProvenanceChip>;

export const RealModel: Story = {
  args: {
    provenance: {
      model_version: "registry-v1.2.3",
      feature_source: "feast",
      degraded: false,
      confidence_basis: "conformal_interval",
    },
  },
};

export const Degraded: Story = {
  args: {
    provenance: {
      model_version: "degraded",
      feature_source: "fallback",
      degraded: true,
      confidence_basis: "fallback_floor",
    },
  },
};

export const PreAdr044: Story = { args: { provenance: null } };
