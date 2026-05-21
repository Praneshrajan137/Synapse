/**
 * SYNAPSE Atlas Console — Storybook · PhaseTimeline.
 *
 * Renders the 5-phase Visx timeline at three phase-reached values so
 * the dot-stroke / label / count semantics are visually regressable.
 */
import type { Meta, StoryObj } from "@storybook/react";

import { PhaseTimeline } from "../components/phase-timeline";

const meta: Meta<typeof PhaseTimeline> = {
  title: "Decision Trace/PhaseTimeline",
  component: PhaseTimeline,
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof PhaseTimeline>;

const baseMessages = [
  { phase: 1, role: "system", content: "Ingest order batch ORD-9981" },
  { phase: 2, role: "agent:demand_prophet", content: "Forecast 412 ± 38" },
  { phase: 2, role: "agent:inventory_sentinel", content: "Reorder 250 proposed" },
  { phase: 3, role: "system", content: "Debate round 1" },
  { phase: 3, role: "system", content: "Debate round 2" },
  { phase: 4, role: "system", content: "Pareto knee selected" },
  { phase: 5, role: "system", content: "Execution committed" },
];

export const ReachedPhase5: Story = {
  args: { phaseReached: 5, contextMessages: baseMessages },
};

export const StalledAtDebate: Story = {
  args: { phaseReached: 3, contextMessages: baseMessages.slice(0, 5) },
};

export const HeadOfPipeline: Story = {
  args: { phaseReached: 1, contextMessages: baseMessages.slice(0, 1) },
};
