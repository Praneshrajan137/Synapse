/**
 * SYNAPSE Atlas Console — agent detail drawer.
 *
 * Opens from `<AgentPanel>` "Details →" button. Shows the full
 * compliance checklist, the architecture record from spec.yaml, and a
 * link out to MLflow (Mumbai-prefixed per E-S6-07 when the active
 * city is Mumbai).
 */
import { memo } from "react";
import type { AgentSpec } from "virtual:atlas/agent-specs";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";

import type { ComplianceSummary } from "../model/compliance";
import { ComplianceChecklist } from "./compliance-checklist";
import { StateMachineViz } from "./state-machine-viz";

export interface AgentDetailDrawerProps {
  readonly spec: AgentSpec | null;
  readonly compliance: ComplianceSummary | null;
  readonly cityId: string;
  readonly onOpenChange: (open: boolean) => void;
}

const MLFLOW_BASE = "/mlflow";

function mlflowUrl(spec: AgentSpec, cityId: string): string {
  const prefix = cityId === "mumbai" ? "mumbai_" : "";
  return `${MLFLOW_BASE}/#/experiments?searchInput=${encodeURIComponent(`${prefix}${spec.agent_name}`)}`;
}

export const AgentDetailDrawer = memo(function AgentDetailDrawer({
  spec,
  compliance,
  cityId,
  onOpenChange,
}: AgentDetailDrawerProps) {
  return (
    <Dialog open={spec !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        {spec && compliance && (
          <>
            <DialogHeader>
              <DialogTitle>{spec.agent_name}</DialogTitle>
              <DialogDescription>
                v{spec.version}
                {spec.description ? ` · ${spec.description}` : ""}
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 lg:grid-cols-[200px_1fr]">
              <div className="flex flex-col items-center gap-2">
                <StateMachineViz spec={spec} width={200} height={200} />
                <a
                  href={mlflowUrl(spec, cityId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ops-xs text-primary underline-offset-2 hover:underline"
                >
                  Open in MLflow ↗
                </a>
              </div>
              <section className="flex flex-col gap-3">
                <h3 className="text-ops-base font-semibold">Spec compliance</h3>
                <ComplianceChecklist summary={compliance} />
                {spec.architecture && (
                  <>
                    <h3 className="text-ops-base font-semibold">Architecture</h3>
                    <pre className="max-h-40 overflow-auto rounded bg-muted p-2 text-ops-xs text-muted-fg">
                      {JSON.stringify(spec.architecture, null, 2)}
                    </pre>
                  </>
                )}
              </section>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
});
