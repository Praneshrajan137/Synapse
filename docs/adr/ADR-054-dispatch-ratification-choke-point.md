# ADR-054: One dispatch ratification choke point - I-5/I-6 on every tier, and a Tier-4 twin veto

## Status
Accepted - **D1, D2 and D3 are implemented; D4 is the seam from task 8.1.** This ADR is
the operator record required by the `purpose-achievement-audit` spec (conflict CF-5),
written *before* the behaviour changed. Task 8.1 landed this ADR plus the reloadable
threshold seam (D4); task 8.5 landed the choke point (D1/D2); task 8.7 landed the
Tier-4 twin veto and the Pareto-front membership assertion (D3, R13.4/R13.5/R13.8).
The disagreement bound is committed in
`infrastructure/quality/twin-verdict-bounds.yaml` and is still **honestly wide**
(`measured: false`) pending an observed distribution - see Ratchet / deferred.
Supersedes nothing.
Amends the dispatch semantics described by [ADR-052](ADR-052-closing-the-agentic-loop.md)
(P3 actuation, P4 deliberation) and [ADR-053](ADR-053-autonomy-spine.md) (the loop the
operator console renders).

## Context
The `purpose-achievement-audit` requirements document establishes, by direct reading of
`orchestrator/consensus/protocol.py`, that **I-5 is enforced on one of two decision
routes**. `_fast_path` (Tier 1 and Tier 2, documented as ~80% of decisions) is
`_phase_collect -> max(proposals, key=utility_score) -> _build_decision ->
_phase_execute -> _phase_learn`. It calls neither `self._guardrails.validate_decision`
nor `self._hitl`. Both the confidence floor and every hard guardrail live only on
`_full_path` (`protocol.py:367-372`).

Three consequences, each read directly rather than inferred:

1. **The tier router decides whether I-5 applies.** I-5 is stated without qualification
   ("Confidence-gated execution - below threshold triggers HITL escalation",
   `CLAUDE.md:28`), and I-6 ("hard guardrails cannot be overridden") likewise. A
   low-confidence Tier 1 decision dispatches with no guardrail evaluation and no human.
   The Fast_Path exemption is recorded in no invariant table, no ADR, and no truth
   ledger - which is the reason this record exists rather than a note in a docstring.

2. **The contract that encodes I-5 and I-4 is not on the production path.**
   `orchestrator/guardrails/rules.py::execute_consensus` carries `@deal.pre`
   ("I-5 VIOLATION: Low-confidence decision not escalated to HITL") and `@deal.post`
   ("I-4 VIOLATION: Decision not logged to audit trail"). Its only callers are tests.
   A contract that no production caller traverses proves a property of the test suite.

3. **The Tier-4 twin verification is advisory.** `_phase_twin_verify`
   (`protocol.py:728-766`) requests a Monte-Carlo what-if from the twin and appends
   `twin=twin_verified` or `twin=twin_unavailable` to `audit_trace`, then returns the
   decision unchanged. There is no verdict value, no declared disagreement bound, and no
   branch in which a twin that contradicts the consensus prediction affects dispatch. The
   twin is consulted at the most consequential tier and cannot object.

The honest counter-reading, stated because it is the strongest argument for the status
quo: Tier 1 is budgeted `<100ms` RL-only (`CLAUDE.md:26`, ADR-032), so "trivial,
low-blast decisions skip deliberation" is a defensible design intent. It is defensible
as a *documented* exemption with an asserted blast-radius bound. Neither exists today,
and `GuardrailEngine.validate_decision` is a deterministic in-process rule engine
written specifically to fit the Tier 1-2 latency budget (`rules.py:1-8`) - so the
latency argument does not support the exemption that exists.

Separately, the confidence threshold is captured as a float at construction
(`rules.py:57`), sourced from `orchestrator/config.py:37` and injected once at
`orchestrator/inference/serve.py:98`. Changing the escalation boundary therefore
requires a process restart, which R5.4 rejects.

## Decision
One route from a built decision to a dispatched action, and the twin gets a veto.

**D1 - A single dispatch choke point.** `ConsensusProtocol` gains
`_ratify_and_dispatch(decision, *, tier, twin_verdict=None)`. Both `_fast_path` and
`_full_path` end by calling it, and it is the **only** caller of
`GuardrailEngine.validate_decision`, `HitlEscalator.escalate`,
`guardrails.rules.execute_consensus`, and `_phase_execute`. Order of operations:
validate -> apply the twin verdict -> escalate if not passed -> `execute_consensus`
(the `@deal.pre` I-5 / `@deal.post` I-4 contract, now on the production path) ->
`_phase_execute`. A BLOCK violation or a sub-threshold confidence withholds dispatch on
every tier and leaves `execution_confirmations` empty.

Rationale for a choke point rather than duplicated calls: copying the guardrail and HITL
calls into `_fast_path` creates a second enforcement site to keep in sync, and the class
of defect being corrected is precisely "an invariant enforced at some sites". One method
that every tier traverses makes the gap unrepresentable instead of currently-absent.

**D2 - I-5 and I-6 apply on Tier 1 and Tier 2.** This is a behaviour change, stated
plainly: decisions that dispatch today will escalate to a human instead. The expected
direction is a rise in Tier 1/Tier 2 escalation volume, bounded by the fraction of
fast-path decisions below `confidence_threshold`. `escalate` is unchanged - it awaits a
human future and executes nothing, which is the part the audit credits and the part that
makes the change fail-closed rather than fail-open.

**D3 - The Tier-4 twin verdict is consequential.** `_phase_twin_verify` returns a
`TwinVerdict` carrying the twin's predicted KPIs, the measured disagreement against the
consensus prediction, and an availability state. Disagreement beyond a declared bound
withholds dispatch or escalates; it is no longer recorded in `audit_trace` alone. An
unreachable or slow twin still degrades honestly to `twin_unavailable` and does **not**
veto (I-7: absence of a verdict is not a negative verdict, and a dead twin must not
become a global dispatch kill switch). The bound is committed configuration under
`infrastructure/quality/` (AD-13), never a literal in the protocol.

**D4 - The escalation boundary is reloadable, not construction-captured.** A
`ConfidenceThresholdProvider` protocol (`current()`, `reload()`) backed by
`orchestrator/config.py` replaces the captured float. `GuardrailEngine` reads
`current()` on **every** validation, so a configuration reload moves the boundary on
every tier with no process restart and no source-file change (R5.4). `reload()` builds a
**new** `OrchestratorConfig` instance and rebinds it; no existing settings object is
mutated, so no frozen model is written to. The threshold is read only by the rule engine
and never interpolated into an LLM system prompt, so the KV-cache stable prefix is
untouched (**I-13 unaffected**). A malformed environment makes `reload()` raise and
leaves the previous known-good value in force - it never substitutes a default, which
would silently lower the gate.

**D5 - Measurement discontinuity (the load-bearing consequence).** D1-D3 change **what
the system decides**, not merely how it records what it decided. Therefore:

> **Any uplift number measured before this ADR lands and any uplift number measured
> after it lands are not comparable, in either direction.** They are measurements of two
> different decision policies. A gain observed across the boundary is not evidence that
> this change helped, and a loss is not evidence that it hurt.

The powered baseline (`uplift.yml`, `MIN_POWERED_REPLICATES = 1000` replicates per arm)
**must be re-measured after** the choke point and the twin veto are both merged. Until
that re-measurement exists, `UPLIFT_FLOOR` stays where it is: `ratchet_to_measured`
admits a raise only against a `PoweredProof` built from an artifact regenerated in the
same job, and a pre-ADR artifact is not such a proof. Mechanically, the expected effect
of D2 is fewer dispatched fast-path actions and more escalations, which moves KPI
aggregates for reasons unrelated to decision quality - so a cross-boundary comparison
would be actively misleading rather than merely noisy.

## Consequences
**Easier.** I-5 and I-6 become unqualified facts about the running system rather than
facts about one route. The DbC contract encoding them sits on the production path, so
`module_liveness`'s "invariant symbol invoked only by tests" projection stops firing for
`execute_consensus`. There is exactly one place to read to learn what must be true
before an action dispatches, and exactly one place to change to alter it. The twin stops
being consulted decoratively at the tier where a wrong action costs the most. Operators
can move the escalation boundary by configuration during an incident.

**Harder / cost.** Fast-path latency gains a deterministic rule-engine evaluation (no
LLM, no I/O - it was built for this budget, but the Tier-1 `<100ms` budget assertion
must be re-checked once the choke point lands). Escalation volume rises and the HITL
queue must absorb it; a Tier 1 decision can now wait on a human, which it never did.
The twin becomes partially load-bearing at Tier 4, which raises the cost of an
unavailable twin from "an honest note" to "no veto available" - the degradation is
honest but the operator must be able to see it. And the uplift baseline must be re-run,
which is a scheduled CI cost, not a local one (I-0).

**Unchanged.** `make_canonical_row` is not touched (I-4, byte-pinned).
`HitlEscalator.escalate` still only awaits a human future. The essential-price cap stays
a CLIP, not a veto. No new Kafka topic and no new consumer. No paid dependency (I-1).
The KV-cache stable prefix (I-13) is unaffected: nothing in D1-D4 changes what enters a
system prompt.

## Alternatives Rejected
- **Document the Fast_Path exemption instead of closing it.** Add the exemption to the
  invariant table and assert a blast-radius bound on Tier 1 actions. Cheapest option and
  it would make the documentation honest. Rejected because the bound is the hard part:
  "trivial" is not a property of a tier, it is a property of an action, and Tier 1
  carries per-SKU reorder actions that genuinely mutate the world (ADR-052 P3). An
  exemption that cannot state its own bound is not an exemption, it is a gap with a
  citation.
- **Duplicate the guardrail and HITL calls into `_fast_path`.** Smaller diff, no new
  method, no change to `_full_path`. Rejected: it creates a second enforcement site, and
  a whole class of audit finding in this repository is "the second site drifted".
- **Enforce the confidence floor in `HitlEscalator` instead of `GuardrailEngine`.**
  Superficially tidier - the escalator would own escalation end to end. Rejected: the
  escalator performs no confidence comparison today and the floor is one of five
  `HARD_GUARDRAILS` entries; splitting one rule out of the rule engine would put I-5 and
  I-6 in two places to satisfy an aesthetic preference.
- **Make the twin veto absolute (an unavailable twin blocks Tier 4).** Maximally
  conservative. Rejected under I-7 and operational reality: absence of a verdict is not
  a negative verdict, and a twin outage would become a full Tier-4 outage. Unavailable
  degrades and is visible; disagreement vetoes.
- **Hot-reload the threshold by mutating the existing settings object.** Fewer
  allocations. Rejected: it writes to a shared configuration instance that other
  components read concurrently, and the repository's Pydantic discipline is to build a
  new instance rather than mutate one. `reload()` rebinding a freshly constructed
  `OrchestratorConfig` is atomic from a reader's perspective and mutates nothing.
- **Land the behaviour change and re-baseline uplift in the same PR.** Rejected: the
  powered run is a scheduled 1000-replicate-per-arm job (CF-4) and cannot sit on the PR
  path. The honest sequence is: record the discontinuity (this ADR), land the behaviour,
  then re-measure.

## Ratchet / deferred
- Task 8.5 landed `_ratify_and_dispatch`; task 8.7 landed `TwinVerdict` and the
  Pareto-front membership assertion. D1-D3 are now properties of the running system.
- The Tier-4 disagreement bound is a committed configuration value; the first value is
  set from an observed disagreement distribution, not guessed. Until it is measured, the
  veto is configured wide - `max_relative_disagreement: 1.00` with `measured: false`,
  which fires only on an order-of-magnitude contradiction. Tightening it is a reviewed
  data edit against a CI/GCP-measured distribution, never a source change.
- The Tier-1 `<100ms` budget (ADR-032) is re-asserted against the choke point once it
  lands.
- The post-ADR powered uplift re-measurement is the gate on any `UPLIFT_FLOOR` raise
  (C60, `ratchet_to_measured`). No number measured before this ADR may be carried across.
