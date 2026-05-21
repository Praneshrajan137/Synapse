import { Badge } from "../primitives/Badge";
import { TIER_DESCRIPTION, TIER_LABEL, TIER_SLA_MS, type Tier } from "@lib/confidence";
import { fmt } from "@lib/formatters";

interface TierBadgeProps {
  readonly tier: Tier;
  readonly title?: string;
}

const TONE: Record<Tier, "tier1" | "tier2" | "tier3" | "tier4"> = {
  tier_1: "tier1",
  tier_2: "tier2",
  tier_3: "tier3",
  tier_4: "tier4",
};

/**
 * Pill indicating which decision tier (1–4) produced a result, with the SLA
 * encoded in the tooltip. Anchored to orchestrator/consensus/tier_router.py.
 */
export function TierBadge({ tier, title }: TierBadgeProps) {
  const sla = TIER_SLA_MS[tier];
  return (
    <Badge
      tone={TONE[tier]}
      title={title ?? `${TIER_DESCRIPTION[tier]} • SLA ${fmt.durationMs(sla)}`}
      aria-label={`${TIER_LABEL[tier]}: ${TIER_DESCRIPTION[tier]}`}
    >
      {TIER_LABEL[tier]}
    </Badge>
  );
}
