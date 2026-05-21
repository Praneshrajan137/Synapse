/**
 * SYNAPSE Atlas Console — spec compliance derivation.
 *
 * For each invariant / pre / post-condition declared in
 * `agents/<name>/spec.yaml` we derive a tri-state status (`pass | watch
 * | fail`) from observed metrics. S4 ships the model + a synthetic
 * provider that maps every check to `pass` until the Prometheus
 * derivation lands in S6 hardening.
 *
 * Critical-severity violations always render with the AAA-contrast
 * `safety-critical` palette per plan §12.
 */
import type {
  AgentInvariant,
  AgentPostcondition,
  AgentPrecondition,
  AgentSpec,
} from "virtual:atlas/agent-specs";

export type ComplianceStatus = "pass" | "watch" | "fail";

export interface ComplianceItem {
  readonly id: string;
  readonly description: string;
  readonly severity: "critical" | "high" | "medium" | "info";
  readonly kind: "invariant" | "precondition" | "postcondition";
  readonly status: ComplianceStatus;
  readonly note?: string | undefined;
}

export interface ComplianceSummary {
  readonly items: readonly ComplianceItem[];
  readonly counts: Readonly<Record<ComplianceStatus, number>>;
  /** True iff any item is failing — gates "Healthy" badges on the panel. */
  readonly hasFailures: boolean;
  /** True iff any failing item is severity=critical. */
  readonly hasCriticalFailures: boolean;
}

/** Provider hook for live status. S5+ wires this to /metrics + Prom. */
export type ComplianceProvider = (
  spec: AgentSpec,
  item: AgentInvariant | AgentPrecondition | AgentPostcondition,
  kind: ComplianceItem["kind"],
) => { status: ComplianceStatus; note?: string };

const DEFAULT_PROVIDER: ComplianceProvider = () => ({ status: "pass" });

export function deriveCompliance(
  spec: AgentSpec,
  provider: ComplianceProvider = DEFAULT_PROVIDER,
): ComplianceSummary {
  const items: ComplianceItem[] = [];

  for (const inv of spec.invariants ?? []) {
    const r = provider(spec, inv, "invariant");
    items.push({
      id: inv.id,
      description: inv.description,
      severity: inv.severity ?? "medium",
      kind: "invariant",
      status: r.status,
      ...(r.note !== undefined && { note: r.note }),
    });
  }
  for (const pre of spec.preconditions ?? []) {
    const r = provider(spec, pre, "precondition");
    items.push({
      id: pre.id,
      description: pre.description,
      severity: "info",
      kind: "precondition",
      status: r.status,
      ...(r.note !== undefined && { note: r.note }),
    });
  }
  for (const post of spec.postconditions ?? []) {
    const r = provider(spec, post, "postcondition");
    items.push({
      id: post.id,
      description: post.description,
      severity: "info",
      kind: "postcondition",
      status: r.status,
      ...(r.note !== undefined && { note: r.note }),
    });
  }

  const counts: Record<ComplianceStatus, number> = { pass: 0, watch: 0, fail: 0 };
  for (const it of items) counts[it.status] += 1;

  return {
    items,
    counts,
    hasFailures: counts.fail > 0,
    hasCriticalFailures: items.some(
      (i) => i.status === "fail" && i.severity === "critical",
    ),
  };
}
