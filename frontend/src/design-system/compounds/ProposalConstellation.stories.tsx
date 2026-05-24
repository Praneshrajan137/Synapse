import type { Meta, StoryObj } from "@storybook/react";
import {
  AGENT_NAMES,
  ProposalConstellation,
  type AgentName,
  type ProposalLike,
} from "./ProposalConstellation";

const meta: Meta<typeof ProposalConstellation> = {
  title: "Compounds/ProposalConstellation",
  component: ProposalConstellation,
  parameters: {
    layout: "centered",
    a11y: {
      // The viz is a `role="figure"` with an aria-label; nodes have aria-labels.
      // Decorative SVG edges and orchestrator core are aria-hidden.
      element: "#storybook-root",
    },
  },
  args: {
    proposals: AGENT_NAMES.map<ProposalLike>((agent, i) => ({
      agent_name: agent,
      utility_score: 0.45 + (i / AGENT_NAMES.length) * 0.5,
      confidence: 0.6 + (i % 3) * 0.13,
    })),
    debating: false,
  },
};
export default meta;

type Story = StoryObj<typeof ProposalConstellation>;

/** All 8 agents have arrived — the fully-resolved state. */
export const FullEight: Story = {};

/** Three early proposals — partial reveal during the proposal phase. */
export const ThreeEarly: Story = {
  args: {
    proposals: [
      { agent_name: "demand_prophet", utility_score: 0.71, confidence: 0.82 },
      { agent_name: "pricing_oracle", utility_score: 0.86, confidence: 0.91 },
      { agent_name: "routing_navigator", utility_score: 0.54, confidence: 0.66 },
    ],
  },
};

/** Debate phase — edges pulse to the orchestrator core. */
export const Debating: Story = {
  args: {
    debating: true,
  },
};

/** A specific agent is selected — focus ring + boxed shadow. */
export const SelectedPricingOracle: Story = {
  args: {
    selectedAgent: "pricing_oracle",
  },
};

/** Interactive: callback fires; Storybook actions panel captures it. */
export const Interactive: Story = {
  args: {
    onSelectAgent: (agent: AgentName) => {
      // eslint-disable-next-line no-console
      console.log("selected", agent);
    },
  },
};

/**
 * Reduced-motion preview. The user's OS setting (prefers-reduced-motion)
 * is what actually drives `framer-motion`'s `useReducedMotion()` hook;
 * this story documents the expected behaviour. Toggle "reduced motion"
 * in your browser dev tools' rendering panel to verify: animations
 * collapse to a duration:0 transition and the initial scale-in is
 * skipped entirely.
 */
export const ReducedMotionHint: Story = {
  name: "Reduced motion (OS-driven)",
  parameters: {
    docs: {
      description: {
        story:
          "Honours `prefers-reduced-motion: reduce`. Toggle in browser dev tools to preview. " +
          "The initial spring-in is skipped; the edge pulse is disabled; opacity changes are instant.",
      },
    },
  },
};

/** Empty state — no proposals yet, all nodes dimmed. */
export const Empty: Story = {
  args: {
    proposals: [],
  },
};
