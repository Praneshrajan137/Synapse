/**
 * SYNAPSE Atlas Console — `virtual:atlas/agent-specs` ambient types.
 *
 * The Vite plugin (`plugins/vite-plugin-agent-specs.ts`) emits a JSON
 * payload that mirrors `docs/specs/agent_spec_schema.json`. We hand-author
 * the type because (a) the JSON Schema is small and stable, and (b)
 * relying on a generated `.d.ts` would create a chicken-and-egg with
 * the build pipeline.
 *
 * Plan §5.5 / §7.1: the Agent Floor surface materialises one panel per
 * entry of `agentSpecs`. The runtime shape is `Object.freeze`d so we
 * type the array as `readonly`.
 */
declare module "virtual:atlas/agent-specs" {
  /** Severity tier per the schema. */
  export type AgentInvariantSeverity = "critical" | "high" | "medium";

  export interface AgentInvariant {
    readonly id: string;
    readonly description: string;
    readonly assertion: string;
    readonly severity?: AgentInvariantSeverity;
  }

  export interface AgentPrecondition {
    readonly id: string;
    readonly description: string;
    readonly check: string;
  }

  export interface AgentPostcondition {
    readonly id: string;
    readonly description: string;
    readonly check: string;
  }

  export interface AgentStateTransition {
    readonly from: string;
    readonly to: string;
    readonly trigger: string;
    readonly guard?: string;
    readonly timeout_seconds?: number;
  }

  export interface AgentStateMachine {
    readonly initial_state: string;
    readonly states: readonly string[];
    readonly transitions: readonly AgentStateTransition[];
  }

  export interface AgentMetamorphicRelation {
    readonly id: string;
    readonly description: string;
    readonly transform: string;
    readonly expected: string;
  }

  export interface AgentContract {
    readonly producer: string;
    readonly expectations: readonly string[];
  }

  export interface AgentSpec {
    readonly agent_name: string;
    readonly version: string;
    readonly description?: string;
    readonly architecture?: Readonly<Record<string, unknown>>;
    readonly invariants: readonly AgentInvariant[];
    readonly preconditions?: readonly AgentPrecondition[];
    readonly postconditions?: readonly AgentPostcondition[];
    readonly state_machine: AgentStateMachine;
    readonly metamorphic_relations?: readonly AgentMetamorphicRelation[];
    readonly contracts?: readonly AgentContract[];
  }

  export const agentSpecs: readonly AgentSpec[];
  export default agentSpecs;
}
