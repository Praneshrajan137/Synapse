/**
 * SYNAPSE Atlas Console — Storybook · AgentPanel.
 *
 * Three states: healthy, degraded, AAA-tagged critical-failure.
 */
import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";
import type { AgentSpec } from "virtual:atlas/agent-specs";

import { AgentPanel } from "../components/agent-panel";
import { type ComplianceSummary } from "../model/compliance";

const SPEC: AgentSpec = {
  agent_name: "demand_prophet",
  version: "1.0.0",
  description: "HGT + TFT hybrid for multi-horizon demand forecasting.",
  invariants: [
    {
      id: "INV-DP-001",
      description: "Every forecast includes conformal intervals",
      assertion: "lower_90 and upper_90 are not None",
      severity: "critical",
    },
    {
      id: "INV-DP-008",
      description: "Inference latency within Tier 2 SLA",
      assertion: "inference_latency_ms < 500",
      severity: "high",
    },
  ],
  preconditions: [],
  postconditions: [],
  state_machine: {
    initial_state: "IDLE",
    states: ["IDLE", "PROPOSING", "DEBATING", "EXECUTING", "LEARNING", "ERROR"],
    transitions: [
      { from: "IDLE", to: "PROPOSING", trigger: "request" },
      { from: "PROPOSING", to: "DEBATING", trigger: "submitted" },
      { from: "DEBATING", to: "EXECUTING", trigger: "consensus" },
      { from: "EXECUTING", to: "LEARNING", trigger: "executed" },
      { from: "LEARNING", to: "IDLE", trigger: "policy_updated" },
      { from: "PROPOSING", to: "ERROR", trigger: "exception" },
    ],
  },
};

const HEALTHY: ComplianceSummary = {
  items: SPEC.invariants.map((inv) => ({
    id: inv.id,
    description: inv.description,
    severity: inv.severity ?? "medium",
    kind: "invariant" as const,
    status: "pass" as const,
  })),
  counts: { pass: 2, watch: 0, fail: 0 },
  hasFailures: false,
  hasCriticalFailures: false,
};

const DEGRADED: ComplianceSummary = {
  items: [
    { ...HEALTHY.items[0]!, status: "watch" },
    { ...HEALTHY.items[1]! },
  ],
  counts: { pass: 1, watch: 1, fail: 0 },
  hasFailures: false,
  hasCriticalFailures: false,
};

const CRITICAL: ComplianceSummary = {
  items: [
    { ...HEALTHY.items[0]!, status: "fail" },
    { ...HEALTHY.items[1]!, status: "watch" },
  ],
  counts: { pass: 0, watch: 1, fail: 1 },
  hasFailures: true,
  hasCriticalFailures: true,
};

const meta: Meta<typeof AgentPanel> = {
  title: "Agent Floor/AgentPanel",
  component: AgentPanel,
  args: {
    spec: SPEC,
    rewardSeries: Array.from({ length: 50 }, (_, i) => 0.7 + 0.05 * Math.sin(i / 5)),
    latency: [
      { tier: "tier_1", p99_ms: 64 },
      { tier: "tier_2", p99_ms: 280 },
      { tier: "tier_3", p99_ms: 4_200 },
      { tier: "tier_4", p99_ms: null },
    ],
    onOpenDetails: fn(),
  },
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof AgentPanel>;

export const Healthy: Story = {
  args: { health: "ok", compliance: HEALTHY },
};

export const Degraded: Story = {
  args: { health: "warn", compliance: DEGRADED },
};

export const CriticalFailure: Story = {
  args: { health: "unreachable", compliance: CRITICAL },
  tags: ["a11y-aaa"],
  parameters: {
    a11y: { config: { rules: [{ id: "color-contrast-enhanced", enabled: true }] } },
  },
};
