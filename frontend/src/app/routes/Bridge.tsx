import { DecisionTape } from "@/ui/components/DecisionTape";
import { EscalationQueue } from "@/ui/components/EscalationQueue";
import { KPIRibbon } from "@/ui/components/KPIRibbon";
import { TierHistogram } from "@/ui/components/TierHistogram";
import { LivingMap } from "@/ui/viz/LivingMap";

/**
 * Bridge — the default surface. Situational awareness in one glance:
 * a KPI ribbon, the living store map, and the live decision tape with
 * the escalation queue and tier mix (plan section 5.1).
 */
export default function Bridge() {
  return (
    <div className="flex h-full flex-col">
      <KPIRibbon />
      <div className="flex min-h-0 flex-1">
        <LivingMap className="flex-1" />
        <aside className="flex w-[380px] shrink-0 flex-col border-l border-line-faint">
          <DecisionTape className="flex-1" />
          <EscalationQueue />
          <TierHistogram />
        </aside>
      </div>
    </div>
  );
}
