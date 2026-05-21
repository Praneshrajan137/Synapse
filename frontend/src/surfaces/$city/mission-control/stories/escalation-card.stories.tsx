/**
 * SYNAPSE Atlas Console — Storybook · EscalationCard.
 *
 * Three states cover the surface contract:
 *   - Tier 2 cool: confidence above the urgency threshold.
 *   - Tier 4 critical: the AAA-contrast banner state — tagged
 *     `a11y-aaa` so the test-runner asserts 7:1 contrast (ADR-028).
 *   - Focused with violations: the keyboard-driven state.
 */
import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { EscalationCard } from "../components/escalation-card";
import type { Escalation } from "../model/escalation";

const meta: Meta<typeof EscalationCard> = {
  title: "Mission Control/EscalationCard",
  component: EscalationCard,
  args: {
    onApprove: fn(),
    onReject: fn(),
    onModify: fn(),
    onFocus: fn(),
  },
  parameters: {
    layout: "centered",
    a11y: { config: { rules: [{ id: "color-contrast", enabled: true }] } },
  },
};
export default meta;

type Story = StoryObj<typeof EscalationCard>;

const baseEscalation: Escalation = {
  type: "escalation",
  decision_id: "aaaa1111-aaaa-4aaa-aaaa-aaaa11111111",
  tier: "tier_2",
  confidence: 0.74,
  issued_at: new Date().toISOString(),
  timeout_seconds: 120,
  proposals: [],
  violations: [],
  recommended_action: { sku_id: "SKU-001", reorder: 280 },
};

export const Tier2Cool: Story = {
  args: { escalation: baseEscalation },
};

export const Tier4Critical: Story = {
  args: {
    escalation: {
      ...baseEscalation,
      decision_id: "cccc3333-cccc-4ccc-cccc-cccc33333333",
      tier: "tier_4",
      confidence: 0.31,
      timeout_seconds: 24,
      violations: [
        { code: "pricing_essential_cap_exceeded", severity: "critical" },
      ],
    },
  },
  tags: ["a11y-aaa"],
  parameters: {
    a11y: { config: { rules: [{ id: "color-contrast-enhanced", enabled: true }] } },
  },
};

export const FocusedWithViolations: Story = {
  args: {
    focused: true,
    escalation: {
      ...baseEscalation,
      tier: "tier_3",
      confidence: 0.42,
      violations: [
        { code: "freshness_below_4h", severity: "alert" },
        { code: "supplier_late_streak_3", severity: "warn" },
      ],
    },
  },
};
