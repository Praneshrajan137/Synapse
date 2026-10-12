# Requirements Document

> **Purpose Achievement Audit** — an evidence-grounded finding set, not a feature plan.

## Introduction

This is an **audit spec**. It is not a feature request. Every requirement below is a
finding derived from reading this repository under invariant **I-0**
(`.kiro/steering/local-compute-budget.md`): no code was executed. All evidence is
direct file reading, `grep`, and static reachability tracing. Where a conclusion
would require compute, it is recorded as *not verified locally — requires CI*, and
that gap is itself reported as a finding rather than hidden.

### The reconstructed purpose

Five readings of purpose, separated deliberately so that existing features do not
get to define purpose retroactively:

| Reading | Statement | Source |
| --- | --- | --- |
| **Declared** | "Supply Yield Network with Autonomous Planning, Sensing & Execution" — quick-commerce (dark-store, 10-minute delivery) supply-chain optimization by a multi-agent RL system with LLM orchestration, at **$0 total cost**. | `CLAUDE.md:4-10` |
| **Implied** | A system whose claims about itself are *mechanically* true. "Any number stated in docs must be derivable from a gate"; "if a fact is worth discovering twice, it is worth a gate". Sprints 11-20 are almost entirely this. | `.kiro/steering/claude-rules-authority.md`, `CLAUDE.md:15-17` |
| **Implemented** | A governed, auditable, honestly-degrading multi-agent **decision apparatus** that closes a perceive-decide-act-learn loop over a **SimPy simulation**, plus an operator console for supervision. Decision *quality* is not measured anywhere. | `orchestrator/consensus/protocol.py`, `digital_twin/world/runtime.py`, `frontend/src/surfaces/` |
| **User-perceived** | An operator opening the console asks one question: *can I trust this autonomous system right now, and what did it decide and why?* Sprints 15-19 are answers to exactly that. | `ADR-047`, `ADR-053`, `frontend/src/surfaces/operations/` |
| **Highest-value** | Make **bounded autonomous decision-making trustworthy**: decisions that are (a) *demonstrably better than a transparent baseline*, and (b) *provably accountable*. (b) is the instrument; (a) is the reason the system exists. | Synthesis |

**The load-bearing asymmetry this audit found.** The project has invested
extraordinary, genuine effort in (b) accountability — 53 registered mechanical
checks, an append-only byte-pinned hash chain, an AST substance gate, tri-state
outcome scoring, honest-degradation discipline that is better than most production
systems. It has invested almost nothing *verified* in (a) decision quality. And
(b) rests on a foundation that is not enforced: the check registry that certifies
accountability has **no CI call site**.

So the honest one-line verdict is: **SYNAPSE has built a credible apparatus for
proving things about itself, has not yet run that apparatus as a gate, and has not
yet used it to prove the one thing its purpose depends on — that its decisions are
better than a simple alternative on data that is not its own simulation.**

### Scope and limits of this audit

- **Method.** Static reading only. No test was run, no container built, no
  workflow executed. Sixteen files were read in full or in cited ranges; four
  read-only sub-agents performed breadth analysis; every substantive claim below
  carries a `file:line`.
- **Evidence order used.** direct observation > traced reachability > static
  inference > documentation assertion. Code existence is never treated as
  capability; a passing test is never treated as a working system; an ADR is never
  treated as an implementation.
- **What this audit cannot establish.** Whether any test actually passes; the live
  `verify_claims` counts; whether GitHub branch protection marks any job a
  *required* check (that state lives in GitHub settings, not this repo); the
  runtime behaviour of any deployed container; whether CI-only gates
  (`training-smoke`, mutation, coverage) currently pass. Each is flagged at the
  requirement that depends on it.
- **What this audit deliberately does not do.** It does not invent obligations the
  project never took on. Several items that look like defects are honest,
  documented, in-source trade-offs (the `ExternalFeedSource` stub, the SKIP
  reporting discipline, the `sustainability_agent` no-op). Those are credited in
  the **PRESERVE** section, not charged as failures. Where a criticism of mine
  survived a check for relevance but the project never owed the obligation, it is
  filed under *unjustified perfectionism* and explicitly excluded from the
  priority buckets that matter.
- **Falsification discipline.** Each requirement names what would prove its
  finding false. Findings that were attacked and survived are marked
  **[falsification attempted]**; findings not yet attackable without compute are
  marked **[unchallenged]** so their confidence is not overstated.

## Glossary

- **Atlas_Console**: the React operator frontend under `frontend/src/`.
- **Audit_Chain**: the SHA-256 prev-hash chain over `audit_consensus` rows, built by
  `orchestrator/audit/hash_chain.py::make_canonical_row` + `hash_payload_for_row`.
- **Check_Registry**: the 53 checks registered via `@register` in
  `scripts/audit/verify_claims.py`, reported as `PASS/FAIL/PARTIAL/SKIP/TOTAL`.
- **CI_Pipeline**: the GitHub Actions workflows under `.github/workflows/`.
- **Consensus_Protocol**: `orchestrator/consensus/protocol.py::ConsensusProtocol`.
- **Fast_Path**: `ConsensusProtocol._fast_path`, the Tier 1 / Tier 2 route
  (`protocol.py:287-305`).
- **Full_Path**: `ConsensusProtocol._full_path`, the Tier 3 / Tier 4 route
  (`protocol.py:309-376`).
- **Guardrail_Engine**: `orchestrator/guardrails/rules.py::GuardrailEngine`.
- **HITL_Gate**: the confidence-floor check plus
  `orchestrator/hitl/escalation.py::HitlEscalator.escalate`.
- **Effectiveness_Harness**: the documented in-browser driver
  `window.__atlasHarness` on which the Atlas console effectiveness and resilience
  measurements depend.
- **Model_Registry**: `packages/synapse_common/model_registry.py::ModelRegistry`.
- **Published_Checkpoint_Registry**: `infrastructure/ml/published_checkpoints.json`.
- **Sensor_Loop**: `orchestrator/sensor/`'s `SensorLoop`, which perceives the world
  and convenes consensus with no external POST.
- **Truth_Ledger**: `docs/state/CURRENT.md`, declared "the single source of truth
  for what is actually wired together in this repository".
- **Uplift_Harness**: the `uplift/` package plus `python -m uplift.cli`, the
  closed-loop counterfactual experiment comparing a Consensus_Arm to a Baseline_Arm.
- **Uplift_Gate**: check C60, `scripts/audit/uplift_truth.py`.
- **World_Runtime**: `digital_twin/world/runtime.py::WorldRuntime`, the standing
  clock-advanced SimPy world.

### Verdict vocabulary

Each requirement closes with one of: *demonstrably achieved · bounded scope ·
substantially achieved · partially achieved · superficially achieved · implemented
but not integrated · integrated but not validated · validated only under limited
conditions · plausible but unverified · contradicted by evidence · not achieved ·
not verifiable locally.*

---

## Requirements

### Requirement 1: The honesty meter is not a gate

**User Story:** As the operator relying on `make verify-claims` as this project's
honesty meter, I want the Check_Registry to be able to fail a build, so that a
claim which silently stops being true stops a merge instead of stopping nothing.

**The claim as made.** "The `make verify-claims` target turns each row below into
an executable check. The summary at the bottom (`PASS x / FAIL y`) is the project's
honesty meter" (`docs/state/CURRENT.md:13`). The rules authority states "Claims are
mechanical. Any number stated in docs must be derivable from a gate"
(`.kiro/steering/claude-rules-authority.md`).

**The verified reality.** `scripts/audit/verify_claims.py` is invoked by **no
workflow**. Its only direct call site is `Makefile:16`. The single path by which CI
executes it is a subprocess inside `scripts/audit/doc_truth.py:196-215`, which uses
`proc.returncode` only to build an error string and **discards it as a gate signal**.
The exit code semantics are correct in isolation — `return 1 if fail_n else 0`
(`verify_claims.py:1886`) — but nothing consumes them. Consequence: of the 53
registered checks, **26 have no enforcement path at all** (C2-C16, C19-C23,
C26-C32, C34-C36, C42-C50, C52, C58-C61); the remainder are enforced only because
their underlying script is *separately* named in `ci.yml` (`substance_truth`
`ci.yml:123`, `training_truth`/`serving_truth`/`confidence_basis_truth` `:131-133`,
`doc_truth` `:139`).

The one indirect coupling that does exist is narrow and stated precisely:
`doc_truth._claim_readme_headline_counts` (`doc_truth.py:235`) executes the suite and
compares the counts to the `README.md:24` headline, so a check flipping PASS->FAIL
turns CI red **because the counts drifted**, not because a FAIL was detected. Two
checks flipping in opposite directions leave the counts identical and stay invisible.
And `doc_truth.evaluate()` returns `ok` if *any* claim is ok (`doc_truth.py:296-304`),
so a skip of the counts claim — including a timeout on the 900s subprocess
(`doc_truth.py:150`) — is masked by the unrelated spec-threshold claim passing.

**The divergence.** The doctrine is "claims are mechanical". The mechanism exists,
is well engineered, and is not wired to consequence. The registry is
documentation-grade, not gate-grade.

**Why it matters to core purpose.** Accountability is half of the highest-value
purpose, and the Check_Registry *is* the accountability apparatus. Every downstream
finding in this document (Requirements 7, 8, 10) is a specific instance of drift
that an enforced registry would have caught at the commit that introduced it. This
is the earliest correctable cause in the audit.

#### Acceptance Criteria

1. WHEN a commit is pushed to `main` and any registered check in the Check_Registry
   returns `FAIL`, THE CI_Pipeline SHALL record a failed conclusion for that commit
   derived from the exit status of a step that executed the Check_Registry, and SHALL
   NOT derive that conclusion from a comparison of counts stated in a document.
2. WHEN a single registered check is deliberately mutated in a scratch branch to
   return `FAIL` while every other check is unchanged, THE CI_Pipeline SHALL record a
   failed conclusion on the head commit of that branch and its log SHALL report the
   mutated check identifier with a status distinct from `PASS`, `PARTIAL`, and `SKIP`.
3. WHEN two registered checks are deliberately mutated in a scratch branch such that
   one flips `PASS`->`FAIL` and another flips `FAIL`->`PASS`, leaving the `PASS`,
   `FAIL`, `PARTIAL`, `SKIP`, and `TOTAL` counts and the `README.md` headline line
   unchanged, THE CI_Pipeline SHALL record a failed conclusion and its log SHALL name
   the newly failing check identifier.
4. IF the Check_Registry execution exceeds its time budget, is terminated by a signal,
   emits a summary that cannot be parsed, or cannot be started, THEN THE CI_Pipeline
   SHALL record a failed conclusion for that commit.
5. WHEN a commit whose changed file paths are all Markdown is pushed to `main`, THE
   CI_Pipeline SHALL produce a run for that commit containing a step that executed the
   Check_Registry.
6. IF a Check_Registry execution is suppressed by the recursion guard, executes zero
   checks, or returns a result set in which every check is `SKIP`, THEN THE gating step
   SHALL record a non-passing result, and no other claim evaluated in that same step
   SHALL supply a passing result for the step.
7. THE gating step SHALL execute every identifier registered in the Check_Registry,
   and IF the set of executed identifiers differs from the set of registered
   identifiers, THEN THE gating step SHALL record a non-passing result naming each
   registered identifier that was not executed.
8. WHEN a pull request targeting `main` contains a registered check returning `FAIL`,
   THE CI_Pipeline SHALL record a failed conclusion for that pull request's head
   commit, and THE gating step SHALL carry no `continue-on-error` setting and no
   construct that discards its exit status.

**Verdict: implemented but not integrated.** The registry is real, thoughtfully
designed (see PRESERVE), and unenforced.

**Falsification.** *What would prove this false:* a workflow step invoking
`verify_claims` whose exit code gates the job, or a GitHub required-check named
`verify-claims`. *Attempted:* grepped all 14 workflow files for `verify_claims`,
`verify-claims`, and `make verify` — only `doc_truth`'s internal subprocess. **[falsification attempted]**
*Residual uncertainty:* required-check configuration is not in this repo
(Requirement 14).

---

### Requirement 2: The uplift gate certifies what its own input denies

**User Story:** As a stakeholder asking "are SYNAPSE's decisions better than a
simple policy?", I want the Uplift_Gate to answer from a completed, powered
experiment, so that the answer is evidence rather than a tautology.

**The claim as made.** C60 "makes the SYNAPSE *decision-integrity uplift*
mechanically visible ... None of [the other gates] proves it is *intelligent* — that
its four-tier consensus decisions actually beat a transparent baseline policy on
business KPIs. The `uplift` harness runs that closed-loop counterfactual experiment
and persists a headline uplift number; this gate is the ratchet that stops a proven
gain from silently rotting away" (`scripts/audit/uplift_truth.py:1-11`). The
`core-purpose-uplift` spec was written specifically to close this gap and reports
**47 of 47 tasks complete**.

**The verified reality.** Four independent facts, each read directly:

1. `uplift/uplift_floor.py:47` — `UPLIFT_FLOOR: float = 0.0`.
2. `artifacts/uplift/result.json` — the committed gate input is
   `{"headline_uplift": 0.0, "incomplete": true, "fidelity": {"confidence":
   "unknown", "within_fidelity_bound": null, "kl_divergence": null}}`.
3. `scripts/audit/uplift_truth.py::read_measured_uplift` reads **only**
   `headline_uplift`. It never consults `incomplete`, never consults fidelity. The
   comparison is `0.0 < 0.0` -> false -> `EXIT_PASS`.
4. No workflow regenerates the artifact: `uplift.cli` and `artifacts/uplift` appear
   in no file under `.github/workflows/`.

The honest predicate that would reject this **exists and is unreachable**:
`uplift/uplift_floor.py:204::is_proven_uplift` and `:247::ratchet_to_measured` are
imported only by `tests/uplift/test_uplift_floor_data_gate.py`,
`test_uplift_floor_monotonic_ratchet_property.py`, and
`test_proven_uplift_predicate_property.py`. No production or gate caller.

**The divergence.** The gate reports PASS on an artifact that self-declares
`incomplete: true` with fidelity `unknown`. The floor makes "beats the baseline"
mean "is at least zero". The predicate written to prevent exactly this is tested and
uncalled. The `core-purpose-uplift` spec's own Requirement 3 named this tautology as
the thing to remove; the tautology is still what CI evaluates.

**Why it matters to core purpose.** This is the single question the whole system
exists to answer. Every other gate in the repository could be green and SYNAPSE
would still have no evidence that a four-tier multi-agent consensus beats a
par-level reorder rule. The apparatus for proving it is genuinely built
(`uplift/consensus_arm.py:666::build_consensus_arm` is real, substantial, and
reachable from `uplift/cli.py:144`) — it has simply never been *run to completion
and recorded*.

#### Acceptance Criteria

1. IF the artifact the Uplift_Gate evaluates carries `incomplete` as `true`, omits the
   `incomplete` field, or carries a non-boolean `incomplete` value, THEN THE
   Uplift_Gate SHALL exit with `EXIT_UNAVAILABLE` (`2`) and SHALL print the reason it
   treated the measurement as unavailable.
2. IF the artifact records no integral replicates-per-arm value under any key in
   `_REPLICATE_KEYS`, or records a value below `MIN_POWERED_REPLICATES` (`1000`), THEN
   THE Uplift_Gate SHALL exit with `EXIT_UNAVAILABLE` (`2`) and SHALL print the
   recorded count and the required count.
3. WHEN the Uplift_Harness completes both arms at `MIN_POWERED_REPLICATES` replicates
   per arm, THE Uplift_Harness SHALL write an artifact carrying `incomplete: false`, a
   finite numeric `headline_uplift`, a numeric `kl_divergence`, a boolean
   `within_fidelity_bound`, the replicates-per-arm count, and a provenance record
   naming the run identifier, the source revision, the seed set, and the arm
   identifiers.
4. THE Uplift_Gate SHALL derive its verdict from `is_proven_uplift`, SHALL exit
   non-zero when `within_fidelity_bound` is `null` or `false` irrespective of the
   headline magnitude, and WHEN `is_proven_uplift` is replaced in a scratch branch by a
   stub returning the opposite verdict, THE exit code the gate produces SHALL change.
5. WHEN the same seed set is replayed through the Uplift_Harness in two separate
   operating-system processes, THE Uplift_Harness SHALL produce byte-identical arm KPI
   aggregates.
6. WHEN the Consensus_Arm is replaced in a scratch branch by a copy of the
   Baseline_Arm so the two arms are identical, THE Uplift_Harness at
   `MIN_POWERED_REPLICATES` replicates per arm SHALL report a headline uplift whose
   95% interval contains zero, and THE Uplift_Gate SHALL NOT report a proven gain.
7. THE CI_Pipeline SHALL regenerate the uplift artifact by running the Uplift_Harness
   in the same job that evaluates the Uplift_Gate, and IF the harness cannot run, THEN
   that job SHALL record a non-passing result.
8. IF the artifact the Uplift_Gate evaluates was read from version control, or carries
   a provenance record whose revision, seed set, or arm identifiers differ from the run
   performed in the evaluating job, THEN THE Uplift_Gate SHALL exit with
   `EXIT_UNAVAILABLE` (`2`).
9. WHERE the Uplift_Gate exits with any code other than `EXIT_PASS` (`0`), THE
   published `PASS` count for the Check_Registry SHALL exclude the Uplift_Gate's check.
10. WHEN `UPLIFT_FLOOR` is raised above `0.0`, THE raise SHALL be admitted only through
    `ratchet_to_measured` against a `PoweredProof` built from an artifact regenerated
    in the same job, and IF no such proof is present, THEN THE raise SHALL be rejected.

**Verdict: contradicted by evidence.** Not merely unproven: the gate reports PASS
on an input that states the measurement did not complete.

**Falsification.** *What would prove this false:* a completed uplift artifact with
`incomplete: false` and a non-zero floor, or a workflow that regenerates it.
*Attempted:* read the artifact, the gate, the floor, and grepped all workflows for
the harness entry point. **[falsification attempted]** *Note in the project's
favour:* `UPLIFT_FLOOR = 0.0` is honestly pinned at zero by
`tests/uplift/test_uplift_floor_data_gate.py:56` and the task list openly deferred
the bump to an operator step — the zero is disclosed, not disguised. The finding is
that a disclosed-vacuous gate is still reported inside a "49 PASS" headline.

---

### Requirement 3: No trained model has been published, and a task claiming otherwise is marked complete

**User Story:** As a stakeholder asking whether the agents are intelligent rather
than merely wired, I want at least one real trained model resolvable at $0, so that
"8/8 agents load a model" describes a model and not a code path.

**The claim as made.** `core-purpose-uplift` task 9.1, marked `[x]`: "Replace the
`__placeholder__` entry in `infrastructure/ml/published_checkpoints.json` — Write
the real `demand_prophet_hgt_tft` registry entry (repo, sha, coverage, `final_crps`,
`trained_at`, `rows`) ... and confirm the serving path loads it so the flagship
serves non-degraded output." C39 is reported as "8/8 wired — every agent loads a
model via ModelRegistry" (`docs/state/CURRENT.md:80`).

**The verified reality.** `infrastructure/ml/published_checkpoints.json:2` is
unchanged: `"__placeholder__": { "status": "unpublished", ... }` with an
`"entry_shape_do_not_commit_as_truth"` template. The co-located test asserts the
placeholder state, not the claimed entry:
`tests/verify/test_published_checkpoint_registry.py:96-110` is named
`test_committed_registry_is_an_honest_placeholder_and_c43_skips` and asserts
`probe.status == "skip"`. The serving-path proof
(`test_populated_record_loads_through_serving_path_non_degraded`, `:141-165`) builds
a checkpoint in `tmp_path` via `_publish_locally`, so it validates the *transport
and adapter*, not a published model. C46 therefore SKIPs.

C39's claim is narrower than it reads: `scripts/audit/serving_truth.py` is an **AST**
check that each `serve.py` constructs `ModelRegistry().load(...)`
(`verify_claims.py:1038`). "8/8 wired" means eight call sites exist.

**The divergence.** A task claiming to land a registry entry is checked complete
against an unchanged placeholder file. The gap between "the serving path is real"
(true, and a genuine achievement) and "a real model serves" (false) is collapsed in
the sprint narrative.

**Why it matters to core purpose.** Decision quality (purpose half (a)) cannot
exceed model quality plus policy quality. With no published model, every
non-degraded claim rests on smoke artifacts produced inside CI. This also blocks
Requirement 2: an uplift number measured with untrained policies bounds what the
uplift number can mean, whichever way it comes out.

#### Acceptance Criteria

1. WHILE the Published_Checkpoint_Registry contains no entry other than
   `__placeholder__`, THE Check_Registry SHALL report the published-checkpoint check as
   `SKIP` under the identifier that check is registered with, and THE CI_Pipeline run
   summary SHALL list that `SKIP` as an unproven claim.
2. WHEN an operator publishes a checkpoint and records it in the
   Published_Checkpoint_Registry, THE Model_Registry SHALL resolve that checkpoint
   through the production serving path and return an object whose `degraded` attribute
   is `false` and whose version string contains the recorded sha.
3. IF the published sidecar's held-out `coverage_p90` is below the agent's declared
   floor, THEN THE published-checkpoint check SHALL exit non-zero and SHALL report the
   measured value and the floor.
4. IF the artifact resolved from the Published_Checkpoint_Registry was produced by a
   smoke run, THEN THE published-checkpoint check SHALL exit non-zero, and THE reported
   detail SHALL distinguish a smoke artifact from an absent artifact.
5. WHILE no checkpoint is published, THE inference pipeline of the flagship agent SHALL
   report `degraded = true` in the provenance of every response, and THE Atlas_Console
   SHALL render that degradation on every surface that displays the agent's output.
6. WHEN a task record asserts that a Published_Checkpoint_Registry entry was landed, THE
   task-completion check SHALL read the registry file, and IF that file holds no
   validated non-placeholder entry, THEN THE check SHALL fail naming the task record.
7. IF a recorded registry entry names a sha that cannot be fetched from the declared
   zero-cost serving source, THEN THE published-checkpoint check SHALL exit non-zero and
   SHALL NOT resolve a locally built checkpoint in its place.
8. WHERE the serving-path proof constructs its checkpoint in a temporary directory, THE
   proof SHALL be reported as validating the transport and adapter, and SHALL NOT be
   counted as evidence that a checkpoint is published.
9. WHEN a registry entry records a `final_crps` value, THE published-checkpoint check
   SHALL recompute that value from the published sidecar's held-out predictions, and IF
   the recomputed value differs beyond the declared tolerance, THEN THE check SHALL exit
   non-zero.

**Verdict: not achieved** for the published model; **demonstrably achieved** for the
serving path and for honest degradation in its absence.

**Falsification.** *What would prove this false:* a non-placeholder entry in the
registry, or a passing C46. *Attempted:* read the registry file and both its tests.
**[falsification attempted]**

---

### Requirement 4: The closed autonomy loop has only ever run on its own simulation

**User Story:** As a stakeholder deciding whether SYNAPSE optimizes a supply chain,
I want at least one decision driven by non-synthetic demand, so that "autonomous
supply-chain optimization" is distinguishable from "an agent controlling a
simulation of itself".

**The claim as made.** ADR-052 "closes the perceive->decide->act->learn loop"; the
autonomy is "proven end-to-end (world depletes -> sensor fires consensus with no POST
-> execute replenishes the world)" (`CLAUDE.md`, ADR-052 summary). A pluggable
`WorldSource` seam is described as "`SimWorldSource` now, `ExternalFeedSource` (real
demand feed) later — same sensor->consensus->actuation loop downstream".

**The verified reality.** The loop is real and it is entirely endogenous:

| Element | Evidence | Nature |
| --- | --- | --- |
| World | `digital_twin/world/runtime.py:74` wraps `SupplyChainSimulation` (SimPy) | simulation |
| Demand | seeded Poisson `SimWorldSource`, `packages/synapse_common/world/source.py:88-105` | synthetic |
| Sim RNG | `digital_twin/simulation/engine.py:102` `np.random.default_rng(seed)` | seeded |
| Initial inventory | `engine.py:334` `{f"sku_{i}": 100.0 for i in range(10)}` | literal |
| Feature history | `data/<city>/demand_history.csv` from `scripts/generate_city.py:437` (seeded RNG, file header reads "Generate synthetic ...") | synthetic |
| Real feed | `packages/synapse_common/world/source.py:108::ExternalFeedSource` — `poll_arrivals` logs `external_feed_not_wired` and `return []` (`:119-126`) | stub |
| Synthetic flag | `packages/synapse_common/world/models.py:91` — `WorldState.is_synthetic` pinned true | self-declared |

Real operator orders *do* reach Kafka (`api/routers/orders.py:37`), but the only
consumer that would turn them into features
(`data_fabric/feast/stream_materialization.py:74`) has no service in
`docker/docker-compose.gcp.yml`, and `infrastructure/kafka/topics.json:29` records
agent consumption of the orders topic as `consumers_planned` — design intent, which
`CLAUDE.md` itself distinguishes from enforced `consumers`. There is no path by
which non-synthetic demand reaches a decision.

**The divergence.** None in the code, which labels itself accurately at every
layer. The divergence is in the *narrative*: "autonomous supply-chain optimization"
and "proven end-to-end" read as claims about a supply chain. They are true claims
about a simulation. `is_synthetic = true` is the code telling the truth that the
sprint summary rounds off.

**Why it matters to core purpose.** "Works in the SimPy twin" and "works on
realistic data" are different claims, and only the second is the declared purpose.
A seeded Poisson arrival process with ten SKUs and literal initial inventory cannot
exhibit the distributional behaviour — demand seasonality, supplier correlation,
fat-tailed disruption — that the agents are designed to handle. An uplift number
measured in this world measures the agents against the simulator's own generative
assumptions.

#### Acceptance Criteria

1. WHEN a demand record that did not originate from a seeded generator is published to
   the orders ingress topic, THE World_Runtime SHALL incorporate that record into the
   state returned by `perceive()` within one clock step, and THE incorporated quantity
   SHALL equal the published quantity.
2. WHILE the World_Runtime is driven by a source that is not a seeded generator, THE
   World_Runtime SHALL report `is_synthetic = false` in every perceived state it returns.
3. WHILE the World_Runtime reports `is_synthetic = true`, THE Atlas_Console SHALL label
   every aggregate derived from that state as synthetic-sourced on the surface that
   displays that aggregate.
4. WHEN the Sensor_Loop convenes a decision from perceived state whose `is_synthetic` is
   `false`, THE audit record for that decision SHALL carry a data-provenance value
   distinct from the value carried by a simulation-sourced decision.
5. IF an external feed is configured and unreachable, THEN THE World_Runtime SHALL report
   a degraded state, SHALL substitute zero arrivals, and SHALL NOT advance demand from a
   seeded generator.
6. WHEN the same non-synthetic input trace is replayed, THE Sensor_Loop SHALL convene the
   same set of decision identifiers in the same order.
7. WHERE a Kafka topic is recorded as having agent consumers rather than planned
   consumers, THE deployed stack SHALL contain a service that consumes that topic, and IF
   no such service exists, THEN THE topic-consumer check SHALL fail naming the topic.
8. THE feed-provenance check SHALL classify every `WorldSource` implementation as seeded,
   external, or stub, and IF an implementation returns an empty arrival list
   unconditionally, THEN THE check SHALL classify it as a stub and THE CI_Pipeline SHALL
   NOT report the loop as externally driven.
9. WHEN the World_Runtime is driven by a source that is not a seeded generator, THE
   initial inventory SHALL be read from that source, and IF the source supplies no
   inventory, THEN THE World_Runtime SHALL report a degraded state rather than substitute
   a literal default.

**Verdict: validated only under limited conditions.** The loop closes; it closes
around a seeded simulation, and the code says so.

**Falsification.** *What would prove this false:* an implemented `poll_arrivals` on
a non-simulated source, or a running stream-materialization service.
*Attempted:* read `ExternalFeedSource` in full, grepped compose for the
materialization service, checked the topic registry's consumer field.
**[falsification attempted]**

---

### Requirement 5: I-5 confidence gating does not apply to Tier 1 and Tier 2 decisions

**User Story:** As an operator trusting that low-confidence actions reach me before
they execute, I want the confidence gate to apply on every decision route, so that
tier selection cannot be a route around human oversight.

**The claim as made.** I-5 is stated without qualification: "Confidence-gated
execution — below threshold triggers HITL escalation" (`CLAUDE.md:28`);
"Confidence-gated execution (HITL escalation below threshold)" enforced by
`orchestrator/hitl/escalation.py` (`14_invariants.md:10`). The DbC contract encodes
it as a precondition: "I-5 VIOLATION: Low-confidence decision not escalated to
HITL" (`orchestrator/guardrails/rules.py:139-142`).

**The verified reality.** Read directly at `orchestrator/consensus/protocol.py:287-305`.
`_fast_path` is: `_phase_collect` -> `max(proposals, key=utility_score)` ->
`_build_decision` -> `_phase_execute` -> `_phase_learn`. It **never calls**
`self._guardrails.validate_decision` and **never calls** `self._hitl`. Both the
confidence floor and every hard guardrail live only on the Full_Path
(`protocol.py:366-372`).

Corollaries, each read directly:
- The confidence threshold is `0.7`, and it lives in the Guardrail_Engine, not in
  the escalator: `rules.py:56` `confidence_threshold: float = 0.7`, sourced from
  `orchestrator/config.py:37` and injected at `orchestrator/inference/serve.py:98`.
  `escalation.py` performs no confidence comparison at all.
- The DbC contract that encodes I-5 (`rules.py:139-150::execute_consensus`) is
  called **only from tests**. It is not on the production path.
- The essential-price cap is a **clip, not a veto**: `rules.py:94` mutates
  `pa["multiplier"] = 1.3` and the decision still passes (`rules.py:81-82`, since
  the message contains "clipped"). This is a deliberate, documented design and is
  consistent with I-6 as written — noted for completeness, not charged as a defect.
- A declared guardrail has no implementation: `privacy_boundary` with enforcement
  `BLOCK` (`rules.py:41-44`) has no check function; it exists in the dictionary only.

On the Full_Path the gate is genuinely blocking and genuinely fail-closed: when
`validate_decision` returns false, `_phase_execute` is never called, so there is no
dispatch and no audit row, and `escalate` (`escalation.py:71-141`) only awaits a
human future — no branch executes the action after escalating.

**The divergence.** An unqualified invariant is enforced on one of two routes. The
tier router therefore decides whether I-5 applies. Tier 1 is `<100ms RL-only`
(`CLAUDE.md:26`) so the design intent is plausibly "trivial, low-blast decisions" —
but that bound is nowhere asserted, and a low-confidence Tier 1 decision executes
without a human and without a guardrail check.

**Why it matters to core purpose.** Bounded autonomy is the product. The bound is
I-5. An invariant that holds on some routes is a different guarantee from the one
documented, and the difference is exactly the class of decision most likely to be
high-volume.

#### Acceptance Criteria

1. WHEN a decision routed to the Fast_Path carries a confidence strictly below
   `confidence_threshold` (`0.7` as configured), THE Consensus_Protocol SHALL escalate
   that decision through the HITL_Gate, THE audit row for that decision identifier
   SHALL carry `escalated = true`, and THE count of dispatched actions for that
   decision identifier SHALL be zero.
2. WHEN a decision violates a guardrail whose declared enforcement is `BLOCK`, THE
   Consensus_Protocol SHALL withhold dispatch on Tier 1, Tier 2, Tier 3, and Tier 4
   alike, and THE audit row for that decision SHALL carry an absent or empty
   `execution_confirmations` value.
3. IF a guardrail is declared with enforcement `BLOCK` and the Guardrail_Engine exposes
   no check function for it, THEN THE Guardrail_Engine SHALL reject its configuration at
   startup and SHALL name that guardrail.
4. WHEN `confidence_threshold` is changed in configuration and the configuration is
   reloaded, THE Consensus_Protocol SHALL escalate at the new threshold on every tier
   without a process restart and without a change to any source file.
5. WHEN an escalation reaches `hitl_timeout_seconds` (`300.0`) under a
   `hitl_timeout_action` whose name implies execution, THE Consensus_Protocol SHALL
   either dispatch exactly one action matching the named fallback and record it in
   `execution_confirmations`, or record in `human_override` that no action was taken —
   and SHALL NOT record an action name in `human_override` for which
   `execution_confirmations` holds no corresponding entry.
6. WHEN a replay corpus of at least 200 decisions containing at least 50 decisions
   below `confidence_threshold` and at least 10 decisions per tier is executed, THE
   audit trail SHALL contain no dispatched decision whose confidence is below the
   threshold and whose `escalated` value is `false`.
7. WHEN the tier router assigns a decision whose confidence is below
   `confidence_threshold` to Tier 1 or to Tier 2, THE Consensus_Protocol SHALL evaluate
   that decision through the Guardrail_Engine before any dispatch.
8. WHEN an escalation reaches its configured timeout, THE HITL_Gate SHALL resolve that
   escalation and SHALL retain no pending entry for that decision identifier.
9. WHILE two escalations are outstanding at the same time, THE HITL_Gate SHALL accept a
   human response addressed to either decision identifier, and WHEN one escalation is
   resolved, THE Consensus_Protocol SHALL dispatch no action for the other.

**Verdict: partially followed** (Full_Path) / **bypassed unacknowledged**
(Fast_Path). The Fast_Path exemption is not recorded in `CLAUDE.md`, in
`14_invariants.md`, or in the Truth_Ledger.

**Falsification.** *What would prove this false:* a guardrail or HITL call inside
`_fast_path`, or a tier router that cannot route low-confidence work to Tier 1/2.
*Attempted:* read `_fast_path` and `_full_path` in full and traced every
`validate_decision` / `_hitl` call site. **[falsification attempted]**
*Secondary finding:* `HitlTimeoutAction.EXECUTE_TIER1` and
`EXECUTE_LAST_KNOWN_GOOD` (`escalation.py:129-137`) write
`human_override = {"action": "timeout_<name>"}` and execute nothing. Safe by
default, but the enum names promise behaviour that does not exist, and the audit row
records an action name for an action never taken — an I-7 wording risk.

---

### Requirement 6: The Audit_Chain is written and anchored but never verified

**User Story:** As an auditor relying on tamper evidence, I want the hash chain
walked and its result acted on, so that "audit immutability" means detection and not
just construction.

**The claim as made.** I-4 "Audit log immutability" (`14_invariants.md:9`);
ADR-033 lists `scripts/synapse_cli/audit_verify.py` as a component; `CLAUDE.md`
Sprint 9 claims "audit chained-hash + verifier CLI + daily anchor". C47 asserts
every deploy is verified end-to-end, and the deploy workflow contains an
audit-verify step.

**The verified reality.** Every verification call site is dead or advisory:

- `Makefile:592` and `.github/workflows/cd-gcp.yml:542` both run
  `python -m orchestrator.audit.cli verify`. **`orchestrator/audit/cli.py` does not
  exist** — confirmed by file search. Both call sites also swallow the exit code
  (`|| echo "synapse audit verify not available yet"` and
  `|| echo 'WARN: audit verify returned non-zero ...'`). So the deploy step cannot
  fail and never ran the verifier it names.
- `scripts/synapse_cli/audit_verify.py:48::verify_chain` is a real implementation
  with a `main` at `:92`, wired to no console-script entry point and invoked by no
  workflow.
- `.github/workflows/publish-audit-anchor.yml` signs anchor **files** with cosign. It
  does not walk the chain.
- `orchestrator/audit/anchorer.py:63::anchor_today` has no scheduled caller.
- The only verification that runs in production is **per-row** recompute:
  `api/routers/decisions.py:321::verify_row_hash`, which powers the console's
  `chain_verified` tri-state. A per-row recompute cannot detect a deleted row or a
  re-linked segment.

**And the verifier that does exist cannot detect the tamper classes an append-only
ledger exists to prevent.** Read directly, the whole of the per-row check in
`verify_chain` is `scripts/synapse_cli/audit_verify.py:71`:

```python
expected = hash_payload_for_row(row.prev_hash or prev_hash, _to_canonical(row))
```

It validates each row against the row's **own stored** `prev_hash`, falling back to
the walked `prev_hash` only when the stored value is null. The walked value is
reassigned from each row's `current_hash` at `:78` and **no comparison ever consumes
it**: nothing asserts that `row.prev_hash` equals the `current_hash` of the row that
actually precedes it in the ordered walk. Consequences:

- **A deleted row is undetectable.** The successor's stored `prev_hash` still
  recomputes against itself consistently, so removing a row from the middle of the
  chain produces a walk with zero breaks.
- **A re-linked segment is undetectable.** An attacker who deletes a row and
  rewrites the successor's `prev_hash` — recomputing that row's `current_hash` to
  match — produces a chain this verifier passes.
- **An adjacent reorder is undetectable** for the same reason: each row is
  self-consistent, and walk order is never checked against the stored links.
- **What the verifier does detect is per-row payload tampering** — the same class the
  per-row recompute at `api/routers/decisions.py:321` already covers.

Two further gaps in the same walk: rows with a null `current_hash` are skipped and
counted as `legacy` rather than treated as breaks (`:68-70`), with no
post-migration boundary distinguishing pre-chain rows from rows that should have
been chained; and a chain of zero rows prints `checked=0 ... breaks=0` and returns
`0`, so an empty or fully-truncated table is reported as a pass.

The write side, by contrast, is genuinely strong (see PRESERVE): no `UPDATE` or
`DELETE` against `audit_consensus` anywhere in the codebase; `synapse_app` has
UPDATE/DELETE revoked (`infrastructure/postgres/02_sprint4_consensus.sql:47,56`);
outcomes went into a separate append-only table rather than mutating the chained row;
`make_canonical_row` is byte-pinned by a literal-digest test with an independent
recompute oracle (`packages/tests/test_audit_chain.py:39,60,73-96`).

The two legitimate mutations found are both correct: `audit_outbox` is deliberately
granted UPDATE (`03_sprint7_outbox.sql:60`) and is a queue, not a ledger; and the
DPDPA erasure `DELETE FROM audit_decisions` (`packages/synapse_common/dpdpa.py:138`)
runs under the privileged erasure role by design (E-S9-10).

**The divergence.** Not an absent detector — `verify_chain` exists
(`scripts/synapse_cli/audit_verify.py:48`). Two failures compound: nothing invokes it,
and it validates each row against that row's own stored `prev_hash` rather than the
walked predecessor's `current_hash`, leaving it blind to deletion, re-linking, and
reorder. The class it does catch is already covered by the per-row recompute at
`api/routers/decisions.py:321`, so wiring it up unchanged adds no detection capability
the system does not already have.

**Why it matters to core purpose.** Accountability is purpose half (b). An
append-only chain whose integrity is never checked provides the *shape* of an audit
guarantee. Detection is the guarantee.

#### Acceptance Criteria

1. WHEN the payload bytes of a row in the middle of a scratch Audit_Chain are
   altered, THE chain verifier SHALL exit non-zero and SHALL name that row as the
   first divergence.
2. WHEN a row is deleted from the middle of a scratch Audit_Chain, THE chain verifier
   SHALL compare each row's stored `prev_hash` against the `current_hash` of the row
   that precedes that row in the ordered walk, SHALL exit non-zero, and SHALL name
   the successor of the deleted row as the break.
3. WHEN a row is deleted from a scratch Audit_Chain and its successor's `prev_hash`
   and `current_hash` are rewritten so that the successor recomputes consistently
   against its own stored `prev_hash`, THE chain verifier SHALL exit non-zero on the
   linkage between that successor and the row preceding it in the ordered walk.
4. WHEN two adjacent rows of a scratch Audit_Chain are exchanged in walk order while
   the stored bytes of both rows are unchanged, THE chain verifier SHALL exit
   non-zero and SHALL name the earlier of the two positions, having compared each
   row's stored `prev_hash` against the walked predecessor's `current_hash`.
5. WHEN the trailing rows of a scratch Audit_Chain are removed so that the walk ends
   before the independently recorded head hash, THE chain verifier SHALL exit
   non-zero and SHALL report the recorded head hash as unreachable.
6. WHEN the Audit_Chain is intact, THE chain verifier SHALL exit zero and SHALL
   report the count of rows walked.
7. WHEN pre-chain rows carrying null hash values are present, THE chain verifier
   SHALL report their count separately from the count of verified rows and SHALL NOT
   include them in the verified count.
8. IF a row created after the recorded chain-migration boundary carries a null
   `prev_hash` or a null `current_hash`, THEN THE chain verifier SHALL treat that row
   as a break and SHALL exit non-zero.
9. WHEN the chain verifier walks a set containing zero rows, THE chain verifier SHALL
   report that no rows were verified and SHALL NOT report the chain as verified.
10. WHILE rows are being appended during a verification run, THE chain verifier SHALL
    walk the row set fixed by a snapshot taken at the start of the run and SHALL
    report that snapshot's upper boundary.
11. IF no anchor exists for the Audit_Chain, or the newest anchor is older than the
    declared anchor freshness bound, THEN THE anchor check SHALL report the chain as
    unverifiable and SHALL NOT report it as verified.
12. WHEN an anchor is published, THE anchor SHALL commit to the chain head hash such
    that a party holding only that anchor detects a subsequent rewrite of any row at
    or before the anchored head.
13. WHERE a workflow step or Makefile target invokes the chain verifier, THE step
    SHALL exit with the verifier's exit code and SHALL contain no construct that
    discards it, and THE verifier SHALL exit non-zero when the walk exceeds its
    declared row-count bound or its declared wall-clock bound.
14. WHEN the CI_Pipeline evaluates the repository, THE command-path check SHALL
    resolve every module path and console-script name named in an audit-verification
    step of a workflow or of the Makefile, and SHALL fail naming each path that does
    not resolve and each such step whose exit status is discarded.
15. THE per-row hash recompute that powers the console's `chain_verified` tri-state
    SHALL be reported as row-level integrity only, and THE Atlas_Console SHALL NOT
    present it as evidence that no row was deleted and no chain segment was
    re-linked.

**Verdict: integrated but not validated** for the chain wiring — the verifier is
built and no call site consumes it; **contradicted by evidence** for the verifier's
linkage-detection capability — the implementation that exists is structurally unable
to detect row deletion, re-linking, or reorder; **demonstrably achieved** for
append-only enforcement and canonical-row pinning.

**Falsification.** *What would prove this false:* an existing
`orchestrator/audit/cli.py`, an exit-code-consuming verify step, or a scheduled
verifier. *Attempted:* file search for the module (absent), grep for
`verify_chain`/`audit_verify`/`orchestrator.audit.cli` across the repo (four hits, all
covered above). **[falsification attempted]**

---

### Requirement 7: Documented quality numbers are not derivable from live blocking gates

**User Story:** As a reader of `CLAUDE.md` trusting its doctrine that every stated
number maps to a gate, I want each quality number to be enforced at the value
stated, so that the doctrine holds for the numbers most likely to rot.

**The claim as made.** "Claims are mechanical. Any number stated in docs must be
derivable from a gate" (rules authority). Specific numbers: coverage "target **84%**
line+branch combined on every package" (`CLAUDE.md:45`); "Mutation survival: <15%
rewards, <10% guardrails/audit. Frontend Stryker `break: 26`" (`:46`); KV-cache
`0.70` floor and tier-routing `80%` floor (`:206-207`).

**The verified reality.** One of these is genuinely pinned; the rest are not.

| Number | Doc | Gate reality | Blocking? |
| --- | --- | --- | --- |
| Spec coverage **99** | `CLAUDE.md:47` | `ci.yml:173 --threshold 99`, pinned by `doc_truth._claim_spec_threshold` (`doc_truth.py:76-104`) | **yes — genuinely mechanical** |
| Price cap **1.3x** | `14_invariants.md:10` | `packages/synapse_common/models.py:281`, pinned by `orchestrator/tests/test_guardrails.py:122,144-161` | **yes — genuinely mechanical** |
| Coverage **84%** | `CLAUDE.md:45` | Enforced floors in `infrastructure/quality/coverage-floors.yaml`: `synapse_common 83.5`, `orchestrator 30.0`, `supplier_trust 3.0`, and **`0.0` for nine packages**. `84.0` appears only as an unenforced `target:` field. C28 asserts floors `>= 0` (`verify_claims.py:759-763`), so `0.0` satisfies it | gate runs; asserts nothing |
| Stryker `break` | `CLAUDE.md:46` says **26**; `frontend/stryker.conf.json:46` is **50**; `frontend.yml:433` step label says **85** | C16 compares against `STRYKER_BREAK_NOW = 26` (`verify_claims.py:358`), so a regression 50->26 passes | job is `if: pull_request \|\| refs/tags/v` — never on push to `main` |
| Mutation **<15% / <10%** | `CLAUDE.md:46` | values match `mutation.yml:88,117,135,242,249,255,264` | full sweep `if: github.event_name != 'pull_request'`; PR job path-filtered — **nothing runs on push to `main`** |
| KV-cache **0.70** | `CLAUDE.md:207` | no assertion found anywhere in `scripts/**` or `.github/workflows/**` | **no gate** |
| Tier-routing **80%** | `CLAUDE.md:207` | no assertion found | **no gate** |
| KL divergence **0.1** | `CLAUDE.md`, `14_invariants.md:16` | C34 checks only the substrings `DIGITAL_TWIN_KL_DIVERGENCE`, `.set(`, `update_live_state` (`verify_claims.py:919-945`); the number `0.1` is asserted only by a runtime Prometheus alert | wiring gated, number not |
| `--cov-fail-under=64` | `docs/state/CURRENT.md:31` | `ci.yml:155` is `--cov-fail-under=0` | describes a value that no longer exists |

**The divergence.** The doctrine holds for two numbers and fails for six. Two
distinct failure modes: a gate that runs but asserts a floor of zero (coverage), and
a number with no gate at all (KV-cache, tier-routing). A third, subtler mode: a
ratchet constant frozen below the shipped configuration (Stryker), which converts the
gate from a floor into a ceiling-shaped no-op.

**Why it matters to core purpose.** Not directly — none of these numbers is the
purpose. It matters because the *doctrine* is what makes every other claim in the
repository readable. If "there is a gate for that" is true two times in eight, the
reader cannot use the doctrine to triage, and the honesty apparatus loses its
compression value.

#### Acceptance Criteria

1. WHEN a package's measured line+branch coverage falls below the floor recorded for that
   package, THE coverage gate SHALL exit non-zero and SHALL name the package, its
   measured value, and its recorded floor.
2. THE coverage floor recorded for every gated package SHALL be greater than zero, and IF
   a gated package carries a zero floor, THEN THE coverage gate SHALL exit non-zero
   naming that package.
3. WHEN the frontend mutation score falls below the `break` value configured in
   `frontend/stryker.conf.json`, THE CI_Pipeline SHALL record a failed conclusion for a
   push to `main`.
4. IF a recorded mutation, coverage, or uplift threshold is committed at a value below
   its previously committed value, THEN THE ratchet check SHALL fail naming the threshold,
   the previous value, and the proposed value.
5. WHEN a governance document states a numeric quality threshold, THE narrative-truth gate
   SHALL locate that number in a gate that executes, and IF the two values differ, THEN
   THE narrative-truth gate SHALL fail naming the document line and the gate.
6. WHEN the measured KV-cache hit rate falls below its documented floor, THE CI_Pipeline
   SHALL record a failed conclusion, and IF no executing job measures that hit rate, THEN
   THE narrative-truth gate SHALL fail.
7. WHEN the measured tier-routing accuracy over the golden traces falls below its
   documented floor, THE CI_Pipeline SHALL record a failed conclusion, and IF no executing
   job measures that accuracy, THEN THE narrative-truth gate SHALL fail.
8. THE ratchet constant a check compares a measurement against SHALL equal the
   corresponding value in the shipped configuration file, and IF the two differ, THEN THE
   check SHALL fail naming both files and both values.
9. WHERE a coverage floor is recorded as zero with a note deferring its measurement to
   CI, THE first run that measures that package SHALL write the measured floor, and IF the
   floor remains zero after a run that measured that package, THEN THE coverage gate SHALL
   exit non-zero naming the package.
10. WHEN a governance document states the value of a command-line flag used by a workflow
    step, THE narrative-truth gate SHALL compare the stated value against the value in the
    workflow file and SHALL fail naming both when they differ.

**Verdict: followed only in appearance** for coverage and mutation;
**not achieved** for KV-cache and tier-routing; **demonstrably achieved** for
spec-coverage `99` and the `1.3x` price cap.

**Falsification.** *What would prove this false:* a non-zero floor per package, or a
KV-cache / tier-routing assertion. *Attempted:* read the floors file, the C28 check
body, `stryker.conf.json`, all mutation triggers, and grepped for hit-rate and
routing-accuracy assertions across scripts and workflows. **[falsification attempted]**
*Not verified locally — requires CI:* whether the coverage job currently passes; the
CI-measured coverage of the nine zero-floor packages is unknown from this machine.
The workflow that would supply it is `ci.yml::quality-gates`.

---

### Requirement 8: Console effectiveness is measured by a harness that does not exist

**User Story:** As an operator whose effectiveness the console claims to have
measured, I want the measurement to come from a driver that exists, so that a scorecard
is a measurement rather than a committed constant.

**The claim as made.** `atlas-console-effectiveness` reports **77 of 77 tasks
complete**, including task 3.2 "record steps, time-to-complete, and error/dead-end
rate", task 4.1 "accumulate this job's measured row for the Effectiveness_Scorecard",
and task 15.1 "compute [interruption precision] over the seeded scenarios". The
workflow calls the ratchet "the REAL effectiveness signal"
(`.github/workflows/frontend.yml:284-286`).

**The verified reality.** The Effectiveness_Harness does not exist. Greps for
`runTaskCompletion`, `driveResilience`, `driveFault`, `seedScenario`, and `failWebGL`
across `frontend/spec/**/*.ts` return **no matches**; `window.__atlasHarness` is
referenced only by the e2e specs that probe for it and skip. Consequences, each read
directly:

- `frontend/tests/e2e/task-completion.jtbd.spec.ts:349` —
  `test.skip(true, "Task_Completion harness ... not wired yet")`. Everything after it
  (steps, latency, dead-end rate, terminal outcome, audit-row-first ordering) never
  executes.
- The same skip pattern at `reconnect-replay.resilience.spec.ts:143-146`,
  `fault-transition.resilience.spec.ts:245`, `firehose-stress.resilience.spec.ts:74`,
  `scale-virtualization.resilience.spec.ts:75`,
  `spatial-visualization.spec.ts:268-273`, `a11y/assistive-tech-flow.spec.ts:165`.
- Because `measuredRows` is populated only after the harness call, `emitScorecard()`
  writes `rows: []`, and `compareScorecard` skips any job absent from the fresh
  scorecard — **zero per-job comparisons**.
- The one remaining metric is a literal on both sides:
  `frontend/src/lib/interruption-precision.ts:82-100` hand-authors four
  `{warranted: true|false}` objects, so `seededInterruptionPrecision()` is `0.75` by
  construction; the same array is duplicated in the spec at `:236-241`; and
  `frontend/spec/effectiveness/scorecard.baseline.json:37` records `0.75`. Baseline
  equals fresh, unconditionally.
- The committed baseline is not a measurement: all five jobs carry identical
  `steps: 20`, `latencyMs: 15000`, `errorRate: 0`
  (`scorecard.baseline.json:6-35`) — authored ceilings.
- The workflow swallows the result: `frontend.yml:288`
  `pnpm test:e2e ... task-completion.jtbd resilience.spec || true`, and
  `frontend.yml:163` for the broader e2e job.
- The nightly real-stack job is green for the same reason:
  `frontend/spec/effectiveness/real-stack-fidelity.ts:376` — "A real-stack SKIP is
  informational (not comparable), never a divergence."

Related: `FE-INV-056` ("Operator Jobs-To-Be-Done reach the correct terminal
outcome") is registered `status: enforced`
(`frontend/spec/fe_invariants.yaml:1014`) with its sole test being the skipping
suite, and `frontend/spec/check_fe_invariants.py:48-50` validates only that the
listed files `.exists()`.

**The divergence.** This is the audit's clearest I-7 breach in effect. `CLAUDE.md`
is explicit: "A SKIP is not a PASS. Absence of proof is never a pass." Here a
universal SKIP, wrapped in `|| true`, is presented as "the REAL effectiveness
signal", and a ratchet comparing a hardcoded constant to itself is the gate. The
individual mechanisms are honestly commented — the `|| true` carries a RATCHET note,
the proxy ceiling is recorded on every report — but the aggregate reads as a
measurement that has never measured.

**Why it matters to core purpose.** The user-perceived purpose is operator trust,
and this is the only apparatus that would evidence it. It also propagates: 77 tasks
were marked complete against it, so the spec's own completion signal is
uninformative about whether the console works for a human.

#### Acceptance Criteria

1. WHEN the effectiveness suite runs, THE Effectiveness_Harness SHALL become reachable
   in the browser context within its declared timeout, and THE emitted scorecard SHALL
   contain exactly one row per declared Job_To_Be_Done — five rows for the five jobs
   declared in `frontend/spec/effectiveness/scorecard.baseline.json`.
2. THE `steps`, `latencyMs`, and `errorRate` value of each emitted scorecard row SHALL
   be captured during the run that emitted that scorecard, and IF the
   Effectiveness_Harness is unreachable or emits no row for a declared job, THEN THE
   effectiveness job SHALL record a failed result rather than emit a scorecard carrying
   fewer rows.
3. WHEN the ratchet compares the emitted scorecard against the committed baseline, THE
   count of per-job comparisons performed SHALL equal the count of declared
   Job_To_Be_Done, THE reported completion count SHALL equal the count of rows measured
   in that same run, and IF a declared job is absent from the emitted scorecard, THEN
   THE ratchet SHALL fail naming that job rather than skip it.
4. WHEN the ratchet job runs, THE effectiveness suite SHALL additionally execute a
   mutated variant that adds one navigation step to each Job_To_Be_Done path, THE
   ratchet SHALL fail on that variant naming each affected job, and IF the mutated
   variant passes the ratchet, THEN THE CI_Pipeline SHALL record a failed conclusion.
5. THE `interruptionPrecision` value SHALL be computed from interruptions raised during
   an executed run, SHALL differ by at least `0.01` between two seeds that raise
   different interruption sets, and IF the value is reproducible from a committed list
   of warranted and unwarranted interruptions without executing a run, THEN THE
   effectiveness job SHALL record a failed result.
6. IF a Job_To_Be_Done, a resilience scenario, or a real-stack fidelity comparison is
   skipped, THEN THE effectiveness job SHALL record that skip as a divergence and SHALL
   NOT record it as informational or as a pass.
7. WHERE a frontend invariant is registered with status `enforced`, THE registry checker
   SHALL observe at least one executed, non-skipped assertion attributable to that
   invariant, and SHALL reject both the existence of the named test file and an
   all-skipped run of that file as sufficient.
8. WHEN the effectiveness suite finishes, THE emitted scorecard SHALL report the count
   of executed scenarios and the count of skipped scenarios, and IF the executed count
   is zero, THEN THE effectiveness job SHALL record a failed result.
9. THE `Task_Completion_Tests + Resilience_Scenarios` step of the `e2e-harness` job and
   every step of the `e2e` and `effectiveness-ratchet` jobs SHALL exit with the exit
   status of the command each runs, and IF any of those steps carries `|| true` or
   `continue-on-error`, THEN THE workflow-shape check SHALL fail naming
   `.github/workflows/frontend.yml` and that step.
10. THE committed baseline SHALL record, for each row, the `harnessVersion`, the `seed`,
    and the timestamp of the run that produced that row, SHALL retain the
    `proxyCeiling` statement, and IF every row carries an identical `steps` value and an
    identical `latencyMs` value, THEN THE baseline check SHALL fail the baseline as an
    authored ceiling rather than accept it as a measurement.

**Verdict: superficially achieved.** The scaffolding is extensive and real; the
measurement it exists to produce has never been produced.

**Falsification.** *What would prove this false:* any implementation of
`window.__atlasHarness`, or a non-empty measured scorecard. *Attempted:* grepped for
all five harness method names across the frontend spec tree, read the skip branches
in six e2e specs, read both the baseline and the precision module.
**[falsification attempted]** *Note in the project's favour:* the
`proxyCeiling` statement in `scorecard.baseline.json:38` explicitly says the metric
"does NOT establish human comprehension. Real effectiveness requires real-user
(RITE) testing with 3-5 operators." That is exactly the right disclosure, and it is
present. The finding is that the disclosure sits beside a gate described as the real
signal.

---

### Requirement 9: Gates are satisfiable by source-text markers, and one gate's test mocks the gate

**User Story:** As a reviewer trusting a gate's verdict, I want the gate to observe
behaviour rather than vocabulary, so that "8 of 8 converted" cannot be earned by
adding a string.

**The claim as made.** C57 is described as proving the agentic loop: "the autonomy
is proven end-to-end" with an "anti-regression gate (5 structural loop invariants +
the stub-execute ratchet 6->0)". The `agency-loop-completion` spec reports 45 of 45
tasks complete.

**The verified reality.**

1. **The detector is a substring match.** `scripts/audit/agency_truth.py:143-147`:
   an agent counts as converted iff its handler source contains one of the literals
   `"WorldAction"`, `"self._actuator"`, `"self._kafka.produce"`.
2. **The task list instructed writing the marker.** `agency-loop-completion`
   `tasks.md` task 7.6 says, verbatim, to return `"diverged"` with empty
   `world_effects` "while still performing an honest `self._kafka.produce`
   event-source **so the gate marks it converted**". The shipped code carries the
   instruction as a comment:
   `agents/sustainability_agent/a2a/handler.py:167` — "(the gate's converted marker,
   R8.6)".
3. **In the deployed stack that marker has no effect.** The produce is guarded by
   `if self._kafka is not None` (`handler.py:172`), and the server constructs the
   handler with no producer:
   `agents/sustainability_agent/inference/serve.py:107`
   `SustainabilityAgentA2AHandler(_pipeline)`. So `kafka_published` is always
   `False` and `execute()` is, as deployed, a constant dict.
4. **The gate does not enforce the count it reports.**
   `agency_truth.py:290-315`: `ok = all(c.ok for c in checks) and len(stubs) <= max_stubs`,
   where `real_actuation` requires only `len(converted) >= 1`. `converted_count` is
   reported and unused. An agent matching neither the stub pattern nor an actuation
   marker lands in neither list and cannot trip the ratchet.
5. **The test for the count mocks the mechanism.**
   `packages/tests/test_agency_truth_gate.py:313-322`,
   `test_c57_fails_on_under_eight_converted`, monkeypatches `agency_truth.evaluate`
   to return `ok=False`. It proves that `verify_claims` propagates a false verdict.
   It does not demonstrate that a seven-converted repository produces `ok=False`.

Six agents *do* genuinely mutate world state — `actuate_items` ->
`packages/synapse_common/world/actuation.py:129::actuator.apply`, at
`demand_prophet/a2a/handler.py:178`, `disruption_shield:198`,
`freshness_guardian:182`, `inventory_sentinel:121`, `pricing_oracle:203`,
`routing_navigator:169`. A seventh (`supplier_trust`) is event-only and *is* wired
with a producer (`supplier_trust/inference/serve.py:123`). So the true deployed
picture is **6 real-mutation, 1 event-only, 1 inert** — not the 8/8 the headline
carries. A parallel wiring gap: five of the six mutating agents' servers pass no
`kafka_producer` (only `inventory_sentinel` and `supplier_trust` do), so their world
mutation is real and their event-sourcing is not.

**The divergence.** The behaviour is honestly labelled at the unit level
(`status: "diverged"`, `reason: "no_carbon_lever"`, empty `world_effects` — this is
*good*, and it is credited in PRESERVE). The divergence is at the gate level: a
check that certifies conversion by vocabulary, in a codebase where the task list
told the implementation which vocabulary to use, is not an independent oracle. This
is the definitional case of writing code to satisfy a gate.

**Why it matters to core purpose.** The agency gate is what stands between "governed
decision pipeline" and "autonomous agent system" — ADR-052's own framing of the
distinction. If the gate can be satisfied lexically, it cannot hold that line.

#### Acceptance Criteria

1. WHEN an agent's `execute()` is invoked against a live World_Runtime, THE agency check
   SHALL classify that agent as actuating only if the state returned by `perceive()`
   differs between before and after the call.
2. IF an agent's handler carries an actuation marker, the agent reports `executed`, and the
   state returned by `perceive()` is unchanged across the call, THEN THE agency check SHALL
   classify that agent as a stub and SHALL name it.
3. WHEN the count of agents classified as actuating falls below the recorded baseline, THE
   Check_Registry SHALL fail and SHALL name each agent that regressed.
4. WHEN an agent is present whose `execute()` matches neither the stub pattern nor an
   actuation marker, THE agency check SHALL assign that agent an explicit classification and
   SHALL NOT omit it from every reported list.
5. WHEN one previously-actuating agent is reverted to a constant return in a scratch copy of
   the repository tree, THE Check_Registry SHALL fail, and THE test that demonstrates this
   SHALL replace no function of the agency evaluator.
6. WHERE an agent's `execute()` reports a published event, THE deployed server for that
   agent SHALL supply the producer that publication requires, and IF the producer is absent,
   THEN THE agent SHALL report the publication as not performed.
7. THE agency check SHALL derive each classification from the statements reachable from the
   invoked `execute()` path, and WHERE an actuation marker appears only in a comment, a
   docstring, or a branch that cannot execute, THE agency check SHALL NOT classify that agent
   as actuating.
8. THE converted-agent count the agency check reports SHALL be the count it compares against
   its baseline, and IF the reported count is not the enforced count, THEN THE check SHALL
   fail.
9. IF a handler file discovered by the agency check cannot be parsed, THEN THE check SHALL
   fail naming that file and SHALL NOT omit that agent from its classification.

**Verdict: followed only in appearance** for the gate; **substantially achieved**
for the underlying actuation (six agents genuinely change the world).

**Falsification.** *What would prove this false:* a behavioural probe in
`agency_truth`, or a test that constructs a seven-converted tree. *Attempted:* read
the detector, the `ok` computation, the C57 test, the task instruction, the
sustainability handler and its server wiring. **[falsification attempted]**
*What survives attack and deserves credit:*
`orchestrator/tests/test_real_actuation_e2e.py:70` is a genuine behavioural proof —
real `WorldRuntime`, real handler `execute()`, only the HTTP hop shimmed, asserting
`after.demand_rate != before.demand_rate` from `perceive()`. That is the independent
oracle the gate lacks; it exists and is simply not what C57 consults.

---

### Requirement 10: The declared single source of truth has drifted from the registry it describes

**User Story:** As a newcomer told that `docs/state/CURRENT.md` is what is actually
wired, I want its rows and counts to be generated from the checks, so that reading it
is faster than re-deriving the truth.

**The claim as made.** "This document is the **single source of truth** for what is
actually wired together in this repository, as opposed to what `CLAUDE.md` or sprint
summaries assert is wired ... No claim recorded here without a `file:line` citation
or a `git`/`curl` command that proves it" (`docs/state/CURRENT.md:6,11`).

**The verified reality.**

- **Count drift.** `CURRENT.md:78` reports "Total mechanical checks: **48**" with
  "PASS: 47 / FAIL: 0 / SKIP: 1". The registry has **53** registered checks
  (`@register` from `verify_claims.py:76` to `:1741`), and `README.md:24` reports
  "49 PASS / 0 FAIL / 0 PARTIAL / 4 SKIP / 53 TOTAL". Only the README headline is
  mechanically pinned (`doc_truth.py:235`); the Truth_Ledger's own summary is pinned
  by nothing.
- **Status drift, in the pessimistic direction.** Rows C1-C6, C8-C13, C16-C21 still
  read **FAIL** with a "(Resolved by WS-n)" note, while the corresponding checks
  assert the resolved state. Concretely, `CURRENT.md:33` says `"break": null ...
  FAIL`, but `frontend/stryker.conf.json:46` is `"break": 50`. The status column is
  not derived from the checks it claims to define.
- **Identifier collision.** The doc's substance rows are off by three from the
  registry: doc `C42` (runtime substance, `CURRENT.md:59`) is code **C45**
  (`verify_claims.py:1083`); doc `C43` (published checkpoint, `:60`) is code **C46**
  (`:1148`); and code `C43` is a different check entirely (all 8 agents expose
  `POST /a2a`, `:1220`). `CURRENT.md:6` states a de-confliction happened — it was
  applied to the code and not to the table.
- **A wrong identifier in the code.** The C46 check returns `cid="C43"` on its
  ImportError/SKIP branch (`verify_claims.py:1163`) while registered as C46
  (`:1148`), so an import failure is reported under another check's number.
- **Rows with no check:** C1, C10, C17, C18, C25, C53. **Checks with no row:** C43,
  C44, C45, C46, C56.

**The divergence.** A hand-maintained ledger describing a machine-readable registry.
Both over- and under-states reality, which is the signature of manual maintenance
rather than of bias.

**Why it matters to core purpose.** `CLAUDE.md`'s own stated reason for this ledger
is that "re-deriving a known fact is the single most expensive recurring line in this
repo". A drifted ledger reintroduces exactly that cost, and this audit paid it.

#### Acceptance Criteria

1. WHEN the Check_Registry is executed, THE Truth_Ledger's summary counts SHALL equal the
   counts that execution reported, and IF any category differs, THEN THE ledger check SHALL
   fail naming each drifted category, the ledger value, and the executed value.
2. IF a check identifier is registered with no corresponding Truth_Ledger row, THEN THE
   ledger check SHALL fail and SHALL name the identifier.
3. IF a Truth_Ledger row cites a check identifier that is not registered, THEN THE ledger
   check SHALL fail and SHALL name the row.
4. THE status recorded on a Truth_Ledger row SHALL equal the status the check with that
   identifier returned in the same execution, and IF they differ, THEN THE ledger check SHALL
   fail naming the row and both statuses.
5. THE identifier a check reports SHALL equal the identifier it is registered under on every
   return path, including import-failure and exception paths, and IF they differ, THEN THE
   Check_Registry SHALL coerce that result to `FAIL` naming both identifiers.
6. WHEN a check is registered in a change that adds no corresponding Truth_Ledger row, THE
   ledger check SHALL fail naming the identifier.
7. THE Truth_Ledger's check matrix and summary SHALL be generated from a Check_Registry
   execution, and IF the committed file differs from the generated output, THEN THE ledger
   check SHALL fail and SHALL print the difference.
8. THE subject a Truth_Ledger row describes SHALL be the subject of the check registered
   under that row's identifier, and IF a row's identifier and subject correspond to different
   registered checks, THEN THE ledger check SHALL fail naming both.
9. THE `README.md` headline counts and the Truth_Ledger summary counts SHALL equal the counts
   of the same Check_Registry execution, and IF any pair differs, THEN THE narrative-truth
   gate SHALL fail naming each document.

**Verdict: partially achieved.** The ledger's method is right and its maintenance
has lapsed; the lapse is structural, not clerical, because nothing generates it.

**Falsification.** *What would prove this false:* a generator or a gate binding the
ledger to the registry. *Attempted:* counted `@register` occurrences, compared every
row to every check, and grepped for a ledger generator. **[falsification attempted]**
*Not verified locally — requires CI:* the live counts. The workflow that would
supply them is `ci.yml::quality-gates` once Requirement 1 is satisfied.

---

### Requirement 11: The blocking surface of CI is narrower than the gate inventory suggests

**User Story:** As a contributor reading a green check mark, I want to know which
gates actually ran, so that green means the same thing on a pull request and on
`main`.

**The claim as made.** `CLAUDE.md` presents the gate registry, the mutation
thresholds, the training-smoke gates, and the frontend effectiveness gates as the
enforcement boundary. The rules authority states heavy work "runs on CI/CD".

**The verified reality.** Read from `.github/workflows/` directly. No `if: false`
exists anywhere — the mechanisms below are all explicit conditions or
`continue-on-error`, and most carry an honest in-file label.

| Mechanism | Location | Effect |
| --- | --- | --- |
| `continue-on-error: true` | `ci.yml:309` (`v4-compliance` job) | `make verify-v4-compliance` cannot fail a build |
| `continue-on-error: true` | `ci.yml:73` (MyPy strict on `agents/`) | honestly labelled "informational, target=blocking" with a TODO |
| `\|\| true` | `ci.yml:96` (license audit) | honestly labelled ADVISORY; the real I-1 gate at `:96-107` is blocking |
| `\|\| echo` | `ci.yml:177` (contract tests) | a collection failure is swallowed |
| `if: github.event_name != 'pull_request'` | `mutation.yml:29` | full mutation sweep never runs on a PR |
| `if: github.event_name == 'pull_request'` | `mutation.yml:150` | fast mutation gate never runs on push to `main`. **Combined: no mutation gate runs on a merge commit** |
| `if:` main/develop/sprint-* | `ci.yml:350` (`training-smoke`) | C38/C40/C45 — the runtime substance gates — never run on a PR |
| `if:` main/develop/sprint-* | `ci.yml:243` (`sprint6-verify`) | skipped on PRs |
| `if: pull_request \|\| refs/tags/v` | `frontend.yml:140,191,259,315,358,421` | e2e, visual, effectiveness harness, ratchet, Lighthouse, Stryker — none run on push to `main` |
| `\|\| true` | `frontend.yml:163,288` | e2e and effectiveness suites cannot fail |
| budgets at WARN | `frontend.yml:374` | mobile Lighthouse budgets non-blocking as shipped |
| `paths-ignore: ["**.md","docs/**","plans/**","notebooks/**"]` | `ci.yml:3-11` | **the narrative-truth gate `doc_truth` does not run on doc-only pushes** — precisely the commits most likely to drift the narrative |
| exit code swallowed | `cd-gcp.yml:542` | the audit-verify deploy step (Requirement 6) |
| `continue-on-error: true` | `integration.yml:177` | real-stack e2e; the fidelity reporter owns pass/fail, and reports SKIP as non-divergence (Requirement 8) |

The genuinely blocking set on every PR and push is: lint, mypy strict on
`orchestrator/`, schema validation, **I-1 paid-API grep** (`ci.yml:96-107` —
scoped to every Python tree, real), I-2 reward isolation, `substance_truth`,
`training_truth`, `serving_truth`, `confidence_basis_truth`, `doc_truth`, the unit
test run, the per-package coverage gate (asserting zero on nine packages, per
Requirement 7), spec coverage at `--threshold 99`, `uplift-verify`
(`pytest tests/uplift tests/verify`), and the chromatic colour gates.

**The divergence.** Each individual condition is defensible and most are documented
with a reason (E-S12-12, E-S12-14, flake avoidance, cost control). The aggregate is
not visible anywhere: no document states which gates a merge to `main` actually
runs. A reader summing `CLAUDE.md`'s gate inventory will substantially overestimate
it.

**Why it matters to core purpose.** The enforcement boundary is what makes the
honesty claims load-bearing. Sprints 11-13 were explicitly about making that
boundary honest. The boundary is now honest per-mechanism and unstated in aggregate.

#### Acceptance Criteria

1. THE repository SHALL contain a generated record naming, for a push to `main`, for a pull
   request, and for a tag, every workflow job and step that executes and whether each
   propagates its exit status.
2. WHEN a gate's trigger condition changes such that it no longer executes on a push to
   `main`, THE gate-surface check SHALL fail unless the generated record is regenerated in the
   same change.
3. WHERE a step does not propagate its exit status, THE generated record SHALL list that step
   as advisory and THE step's name SHALL identify it as advisory.
4. WHEN a commit is pushed to `main`, THE narrative-truth gate SHALL execute regardless of
   which file paths the commit changed.
5. WHEN a mutation-score regression is introduced by a commit merged to `main`, THE
   CI_Pipeline SHALL record a failed conclusion for that merge commit.
6. WHEN a runtime substance probe regresses, THE CI_Pipeline SHALL record a failed conclusion
   on the pull request that introduces the regression.
7. THE generated record SHALL be produced by parsing the workflow files, and IF the committed
   record differs from the parsed output, THEN THE gate-surface check SHALL fail and SHALL
   print the difference.
8. WHERE a governance document describes a gate as blocking, THE generated record SHALL show
   that gate executing and propagating its exit status on a push to `main`, and IF it does not,
   THEN THE narrative-truth gate SHALL fail naming the document line.
9. WHEN a job that another job depends on is skipped by its trigger condition, THE generated
   record SHALL report the dependent job as not executed, and THE dependent job SHALL NOT
   record a successful conclusion.

**Verdict: partially followed.** Honest per-mechanism, unstated in aggregate, with
two consequential holes: no mutation gate on merge commits, and the narrative gate
skipped on the commits most likely to need it.

**Falsification.** *What would prove this false:* a document enumerating the
per-trigger gate set. *Attempted:* grepped every workflow for `continue-on-error`,
`|| true`, `if: false`, and `github.event_name`; read `ci.yml` triggers.
**[falsification attempted]** *Not verifiable locally:* which of these jobs GitHub
marks a *required* check (Requirement 14).

---

### Requirement 12: Two load-bearing oracles validate a mechanism against a model of itself

**User Story:** As a reader of an oracle-layer test, I want the oracle to be
independent of the thing it judges, so that agreement is evidence.

**The claim as made.** `tests/oracle/test_pricing_impact_oracle.py` is titled
"Oracle Layer 6: Pricing Oracle vs Twin revenue impact", and the seven-layer testing
topology lists Oracle as a distinct verification layer
(`references/testing_topology.md`). `decision-integrity-uplift-proof` task 13.3
claims to have repaired it.

**The verified reality.** The test imports only the twin
(`test_pricing_impact_oracle.py:6`, `from digital_twin.simulation.monte_carlo import
MonteCarloRunner, ShockParams`). No `pricing_oracle` module is involved anywhere in
the file. And the "predicted" value is a closed-form restatement of the simulator's
own behaviour, by the test's own admission at `:12-15`: "The twin's
`orders_delivered` scales linearly with the demand multiplier (verified empirically
against the SimPy engine), so the predicted revenue impact below is the twin's own
behaviour expressed in closed form." The `TOLERANCE = 0.20` bound (`:18`, asserted
`:54`) is real, and what it bounds is the twin against an algebraic description of the
twin.

The second instance is the FE invariant registry (already cited in Requirement 8):
`frontend/spec/check_fe_invariants.py:48-50` validates that listed files exist, and
18 invariants are registered `status: enforced` on that basis
(`fe_invariants.yaml:952-1273`). The registry gate validates the registry.

A third, milder instance: C61 (`verify_claims.py:1742`) is a subset-of-allowlist
ratchet over four pre-existing oracle docstring/body mismatches
(`scripts/audit/oracle_truth.py:83-99`). It verifies "no reintroduced mismatch", not
"oracle tests assert their docstring claims". This one is clearly disclosed with
per-entry rationale and is a legitimate ratchet design — recorded for completeness,
not charged.

**The divergence.** A test named as an independent oracle for an agent neither
involves the agent nor is independent. Its docstring is candid about the second part,
which is why the finding is a naming and layer-classification problem rather than a
concealment.

**Why it matters to core purpose.** The Oracle layer is where the testing topology
places its claim to external validity. If the top layer is self-referential, the
seven layers collapse to six, and the project's confidence in its own decision logic
is less externally grounded than the topology implies.

#### Acceptance Criteria

1. WHERE an oracle-layer test names a component as the subject of its comparison, THE test
   SHALL import that component and SHALL invoke it on the path that produces the asserted
   value.
2. THE reference value in an oracle-layer test SHALL be computed without executing the
   implementation under test, and WHERE the reference is a closed-form restatement of that
   implementation's own behaviour, THE test SHALL be registered in a layer other than Oracle.
3. WHEN the pricing agent's elasticity model is perturbed in a scratch branch, THE pricing
   oracle test SHALL fail.
4. WHERE a frontend invariant carries status `enforced`, THE registry checker SHALL observe an
   executed, non-skipped assertion attributable to that invariant.
5. IF an oracle test's docstring claim and its assertion body disagree, THEN THE oracle auditor
   SHALL fail unless the pair is listed with a dated rationale and a stated removal condition,
   and THE auditor SHALL fail when a listed entry carries neither.
6. THE membership of the Oracle layer SHALL be derived from the checks in criteria 1 and 2
   rather than from a test's file path or title, and IF a test registered as Oracle satisfies
   neither, THEN THE oracle auditor SHALL fail naming that test.
7. WHERE an oracle-layer test asserts a tolerance bound, THE test SHALL fail for a perturbation
   of the implementation that exceeds that bound, and IF no perturbation causes a failure, THEN
   THE oracle auditor SHALL report that tolerance as unconstraining.

**Verdict: superficially achieved** for the pricing oracle and the FE registry;
**bounded scope** for C61, which is honestly a ratchet and says so.

**Falsification.** *What would prove this false:* a `pricing_oracle` import in the
oracle test, or an assertion-level FE registry check. *Attempted:* read both files in
full. **[falsification attempted]**

---

### Requirement 13: Capability exists, is tested, and is not reachable from any production path

**User Story:** As a maintainer, I want each shipped module to be reachable from a
running path or explicitly marked as a seam, so that test count and property count do
not overstate delivered capability.

**The claim as made.** Sprint summaries and the five completed specs enumerate
delivered modules, property counts, and test counts as evidence of capability.

**The verified reality.** Eight instances, each traced by import graph:

| Artifact | Reachability | Evidence |
| --- | --- | --- |
| `uplift/uplift_floor.py::is_proven_uplift`, `::ratchet_to_measured` | tests only | `:204`, `:247`; no gate or production caller (Requirement 2) |
| `orchestrator/guardrails/rules.py::execute_consensus` (the `@deal.pre` I-5 + `@deal.post` I-4 contract) | tests only | `:139-150`; not on the production path (Requirement 5) |
| `pareto_front` | computed, stored, never read | `protocol.py:351` -> `:981`; only `knee_index` reaches context `:719-722` |
| `_phase_twin_verify` result | cannot influence the outcome | `protocol.py:765-766` — `model_copy` updates **only** `audit_trace`; a Tier-4 twin disagreement cannot block execution |
| LLM debate analysis | recorded, ignored | `protocol.py:503`, appended to context at `:472,:487`; never touches values or selection |
| `frontend/src/lib/reconcile.ts` | property-tested, no production import | imported only by `reconcile.property.test.ts` and `reconnect-backoff.property.test.ts`; `transport/ws-multiplex.ts` does not use it |
| `frontend/src/lib/virtual-window.ts::computeWindow` | property-tested; surfaces use `@tanstack/react-virtual` | surfaces import only `ROW_OVERSCAN` (`AuditVault.tsx:13`, `DecisionTheater.tsx:12`) — the property validates a parallel model, not the shipped virtualizer |
| `TrustTrackRecord`, `UpliftSlot` | rendered propless, permanently empty | `frontend/src/surfaces/operations/Operations.tsx:46-47`; defaults `outcomes = []`, `measure = null` |
| `orchestrator/audit/anchorer.py::anchor_today` | no scheduled caller | `:63` (Requirement 6) |

Two of these are correct and documented as such: `TrustTrackRecord` states in-source
that "no per-operator longitudinal endpoint exists yet", and `UpliftSlot` renders
`AWAITING_UPLIFT_MEASURE` — honest empty states under I-7, not fabricated data. A
repo-wide grep for `MOCK|mockData|DEMO_|SAMPLE_|FAKE|dummy` and inline literal data
arrays across `frontend/src/{surfaces,design-system,hooks,lib}` found **no fabricated
data in any production render path**, which is a genuine result.

**The divergence.** Not that the modules are wrong — several are deliberate seams,
and the empty states are exemplary. The divergence is that property counts and test
counts are cited as capability evidence without distinguishing "verified and
reachable" from "verified and dormant". Two of the dormant items are the honest
predicates that would close Requirements 2 and 5.

**Why it matters to core purpose.** Two invariant contracts (I-4, I-5 via
`execute_consensus`) and the uplift honesty predicate are all in this category. The
strongest correctness machinery in the repository is the part not on the path.

#### Acceptance Criteria

1. WHEN a module under `orchestrator/`, `agents/`, `uplift/`, or `frontend/src/lib/` is
   imported by no non-test module, THE module-liveness check SHALL report that module, and IF
   the count of such modules exceeds the recorded baseline, THEN THE Check_Registry SHALL fail
   naming each module added over that baseline.
2. WHERE a module is a declared future seam, THE module SHALL carry a machine-readable seam
   marker, and THE liveness check SHALL exempt only modules carrying that marker.
3. WHERE a property test exercises a function that no non-test module imports, THE test SHALL
   be reported as validating a model rather than the shipped implementation.
4. WHEN the digital twin's verification of a Tier 4 action disagrees with the selected action
   beyond the declared bound, THE Consensus_Protocol SHALL withhold dispatch or escalate that
   decision, and SHALL NOT record the disagreement in `audit_trace` alone.
5. WHEN a Pareto front is recorded on a decision, THE recorded front SHALL be the set the
   ratified action was selected from, and THE ratified action SHALL be a member of that
   recorded front.
6. WHERE a console component has no data endpoint, THE component SHALL render its declared
   empty state and THE surface SHALL state that no data path exists.
7. WHERE a symbol encodes an invariant precondition or postcondition, THE symbol SHALL be
   invoked from a non-test module, and IF it is invoked only from tests, THEN THE liveness check
   SHALL fail naming the symbol and the invariant it encodes.
8. WHEN a decision records a debate analysis that changed no proposal value and no selection,
   THE recorded analysis SHALL be marked advisory.
9. WHEN the module-liveness baseline is recorded, THE baseline SHALL name each dormant module,
   and IF a module is removed from the baseline while still imported by no non-test module, THEN
   THE liveness check SHALL fail naming that module.

**Verdict: implemented but not integrated.** Note that `module_liveness.py` and its
`DEAD_BASELINE` already exist (`verify_claims.py:1258`) — the mechanism for this
requirement is built and, per Requirement 1, unenforced.

**Falsification.** *What would prove this false:* a production import of any listed
artifact. *Attempted:* grepped each symbol's import sites and excluded test trees.
**[falsification attempted]**

---

### Requirement 14: Whether any gate is a required check is not verifiable from this repository

**User Story:** As an auditor judging enforcement, I want the required-check set to be
declared in-repo, so that "blocking" is a property of the repository rather than of a
setting I cannot see.

**The claim as made.** Throughout `CLAUDE.md` and the Truth_Ledger, gates are called
"blocking", "PR-gated", and "fails CI".

**The verified reality.** A job that fails turns a run red. Whether a red run *blocks
a merge* depends on GitHub branch-protection required-status-checks, which is
repository configuration and is not present in this working tree — no
`.github/settings.yml`, no ruleset file, no `CODEOWNERS`-adjacent protection
declaration was found. Therefore, for every gate in this audit, the step from "fails
the workflow" to "cannot be merged" is **not verified locally**.

**The divergence.** No divergence is asserted. This is a boundary of the audit, and
naming it is the finding: the project's strongest claims about enforcement rest on a
fact that its own honesty apparatus cannot check, because the fact lives outside the
repository.

**Why it matters to core purpose.** The whole gate doctrine assumes a red run stops
work. If any load-bearing job is not a required check, the enforcement boundary is
one layer thinner than every document assumes, and no in-repo gate can detect that.

#### Acceptance Criteria

1. THE repository SHALL contain a committed file declaring the set of workflow jobs required to
   pass before a merge to `main`.
2. WHEN a workflow job named in the declared required-check set is renamed or removed, THE
   required-check consistency check SHALL fail naming that job.
3. WHERE a governance document describes a gate as blocking, THE declared required-check set
   SHALL contain the job that executes that gate, and IF it does not, THEN THE consistency check
   SHALL fail naming the document line and the job.
4. IF the declared required-check set differs from the live branch-protection configuration,
   THEN THE reconciliation job SHALL report each difference and SHALL NOT record a successful
   conclusion.
5. IF the reconciliation job cannot read the live branch-protection configuration, THEN THE
   reconciliation job SHALL report the required-check set as unverified and SHALL NOT record a
   successful conclusion.
6. WHEN the reconciliation job runs, THE reported live required-check set SHALL be read from the
   hosting platform during that run and SHALL be recorded with the timestamp of that read.

**Verdict: not verifiable locally.** Requires the `gh api` branch-protection read
described in MISSING EVIDENCE.

**Falsification.** *What would prove this false:* a committed settings or ruleset
file. *Attempted:* searched for `.github/settings.yml`, ruleset JSON, and any
required-check declaration. **[falsification attempted — none found]**

---

## Invariant Classification

Classification of each invariant as **authentically embodied · substantially
followed · partially followed · followed only in appearance · inconsistently
applied · contradicted · explicitly traded off · bypassed unacknowledged · not
verifiable locally**, with evidence. Confidence is stated per row.

| ID | Classification | Evidence | Confidence |
| --- | --- | --- | --- |
| **I-0** local compute | **authentically embodied** — and load-bearing for this audit | `.kiro/steering/local-compute-budget.md`; no process was executed during this audit; test counts and gate behaviour were read, not run | high (direct) |
| **I-1** zero cost | **authentically embodied** | Blocking grep gate at `ci.yml:96-107`, scoped to *every* Python tree with an honest note that the license audit at `:89-96` is advisory; a second copy at `security.yml:73-79`. No paid client import found. ADR-037 addresses cloud-cost honesty | high for the code gate; the free-tier standing of the live GCP VM is **not verifiable locally** |
| **I-2** reward isolation | **substantially followed** | `ci.yml:109` reward-isolation step is blocking; `reward-isolation` pre-commit hook | medium — the AST hook body was not read |
| **I-3** schema-validated outputs | **substantially followed** | `validate_agent_payload` gates the debate revision at `protocol.py:686-688`; `RuntimeValidator` in `packages/synapse_common/invariants.py`; `proto/domain/world_{event,action,state}.schema.json` and `agent_metric.schema.json` added under ADR-052/053; the historical ingress exemption (Truth_Ledger C6) is closed | medium-high |
| **I-4** append-only audit | **split: authentically embodied at the write layer / integrated but not validated at the verify layer** | Write: no `UPDATE`/`DELETE` against `audit_consensus` anywhere; `synapse_app` revoked at `infrastructure/postgres/02_sprint4_consensus.sql:47,56`; outcomes routed to a separate append-only table per E-S9-02; `make_canonical_row` byte-pinned by literal digest plus independent recompute at `packages/tests/test_audit_chain.py:39,60,73-96`. Verify: `orchestrator/audit/cli.py` **does not exist**, both call sites swallow the exit code (`Makefile:592`, `cd-gcp.yml:542`), `scripts/synapse_cli/audit_verify.py` has no entry point (Requirement 6) | high (direct on both halves) |
| **I-5** confidence-gated execution | **bypassed unacknowledged** on the Fast_Path; **substantially followed** on the Full_Path | `protocol.py:287-305` calls neither `validate_decision` nor `_hitl`; `protocol.py:366-372` is genuinely fail-closed; the DbC contract encoding I-5 (`rules.py:139-150`) is invoked only from tests (Requirement 5) | high (direct) |
| **I-6** essential price cap 1.3x | **authentically embodied** | Clip at `rules.py:94` (a cap, per the invariant's wording — not a reject); constant at `packages/synapse_common/models.py:281` and `contracts.py:26`; pinned by `orchestrator/tests/test_guardrails.py:122,144-161`; surfaced honestly in the console's Live Markets surface | high |
| **I-7** honest degradation | **substantially followed, with one contradiction** | Embodied: `ExternalFeedSource` logs and returns `[]` rather than fabricating (`world/source.py:119-126`); `sustainability_agent` returns `diverged` rather than `executed`; `outcome_score` writes `unknown` rather than a fabricated confirm; the Check_Registry's four-way partition with a `NOT VERIFIED -- n SKIP (a SKIP is not a PASS)` callout (`verify_claims.py:1875-1885`) and coercion of raising checks to FAIL (`:1808-1832`). Contradicted: a universal SKIP wrapped in `\|\| true` is presented as "the REAL effectiveness signal" (`frontend.yml:284-288`) and a real-stack SKIP is defined as non-divergence (`real-stack-fidelity.ts:376`) — Requirement 8 | high on both sides |
| **I-8** four-tier routing | **partially followed** | `orchestrator/consensus/tier_router.py` exists and routes; latency bounds appear in Prometheus burn rules (`infrastructure/prometheus/rules/orchestrator_burn.yml:6,34,77` for tiers 1-3); the documented **80% routing-accuracy floor has no gate** (Requirement 7); the Tier-4 15-120s bucket was **not found** | medium; tier-4 bucket **not verified** |
| **I-9** A2A vs MCP separation | **substantially followed** | ADR-038; C43 asserts all 8 agents expose `POST /a2a` (`verify_claims.py:1220`, substring-level); `topics.json` `consumers` vs `consumers_planned` distinction is enforced by `topic_consumer_truth.py` — which is invoked by no workflow (`Makefile:22` only) | medium — the separation is architectural and the gate is lexical |
| **I-10** API latency <2s p99 | **not verifiable locally** | Prometheus alert `SynapseAPILatencyHigh` only; no CI assertion found | n/a |
| **I-11** federated learning keeps data at-store | **not verifiable locally** | `packages/synapse_common/dpdpa.py` cascade helper is real and uses the privileged erasure role (E-S9-10); the Flower gradient-only aggregation claim rests on documentation and was not traced | low — documentation assertion |
| **I-12** twin KL divergence <0.1 | **partially followed** | Wiring is real: `divergence_monitor` emits and `kafka_sync` feeds `update_live_state` (C34). But C34 checks only substrings (`verify_claims.py:919-945`), the `0.1` threshold is asserted only by a runtime alert, and `artifacts/uplift/result.json` records `kl_divergence: null` with `within_fidelity_bound: null` — so the fidelity bound on which uplift validity depends has never been measured | medium-high |
| **I-13** KV-cache stable prefix | **partially followed** | `kv-cache-check` pre-commit hook enforces the code-shape rules (no f-strings / `time.time()` in the three named modules); the documented **0.70 hit-rate floor has no gate** (Requirement 7) | medium |
| **I-14** append-only runtime context | **substantially followed** | `ContextMessage` frozen; `_append_context` is the only mutation path in `protocol.py`; the debate and arbitration phases append rather than replace (`protocol.py:472,487,719-722`) | medium-high |

**Pattern.** The invariants that are *shape* constraints (I-1, I-2, I-6, I-13's code
rules, I-14) are authentically or substantially embodied, because a static gate can
hold a shape. The invariants that are *behavioural* (I-4's verification, I-5's
universality, I-8's and I-13's numeric floors, I-12's threshold) degrade to partial,
because holding them requires running the system and comparing against an
independent expectation. That is the same asymmetry as the top-level finding.

---

## PRESERVE — what is genuinely right

Real achievement, credited without hedging. None of this should be disturbed by work
arising from the requirements above.

1. **`make_canonical_row` byte-pinning is exemplary.**
   `packages/tests/test_audit_chain.py` pins the field set (`:39`), the rounding
   (`:52`), an **independent recompute oracle** using raw stdlib calls (`:60`), and a
   **literal digest string** for a pre-ADR-044-shaped row (`:73-96`). This is how a
   byte-pinned contract should be defended. E-S9-02 exists because someone learned
   this the hard way and wrote it down.

2. **Append-only enforcement is real at the layer that matters.** No `UPDATE` or
   `DELETE` against `audit_consensus` anywhere in the codebase; role grants revoke
   them for `synapse_app`; when outcomes needed recording, they went into a
   **separate append-only table** rather than mutating a chained row. The only
   mutations found are a queue (`audit_outbox`, deliberately granted UPDATE) and the
   DPDPA erasure path under a privileged role. That is I-4 taken seriously.

3. **Binding Pareto arbitration is genuinely wired.**
   `protocol.py:331` `selection = select_binding_action(proposals, weights)` — the
   knee-weighted selection, not `argmax(utility)` — and it feeds `_build_decision` at
   `:962-966`. ADR-052 listed this as a ratchet; it landed. The `argmax` survives only
   on the Fast_Path (`:294`).

4. **The debate genuinely revises proposals.** `protocol.py:697-700` produces
   `prior.model_copy(update={"payload": payload, "utility_score": revised_score})`,
   gated on a `"revised"` status *and* on `validate_agent_payload` passing. Every
   other branch returns the prior unchanged. The concession round changes values,
   not just labels.

5. **Guardrails on the Full_Path are fail-closed and correct.** When
   `validate_decision` returns false, `_phase_execute` is never called — no dispatch
   and no audit row — and `escalate` only awaits a human future. **No code path
   executes the action after escalating.** That is the hard part of HITL, and it is
   right.

6. **Six agents genuinely change the world.** `actuate_items` ->
   `actuation.py:129::actuator.apply` at `demand_prophet:178`,
   `disruption_shield:198`, `freshness_guardian:182`, `inventory_sentinel:121`,
   `pricing_oracle:203`, `routing_navigator:169`. ADR-052 promised a one-agent
   vertical slice and six landed.

7. **`test_real_actuation_e2e.py:70` is a real behavioural proof with an independent
   oracle.** Real `WorldRuntime`, real handler `execute()`, only the HTTP hop shimmed,
   asserting `after.demand_rate != before.demand_rate` read back through
   `perceive()` — not the agent's own status field. This is the standard the other
   gates should be held to, and it already exists here.

8. **I-7 discipline is better than most production systems.** `ExternalFeedSource`
   logs `external_feed_not_wired` and returns `[]` instead of fabricating arrivals.
   `sustainability_agent` returns `"diverged"` with `reason="no_carbon_lever"` and
   empty `world_effects` rather than a fake `"executed"`. `outcome_score` writes
   `unknown` when no realized signal exists. `WorldState.is_synthetic` is pinned true.
   `TrustTrackRecord` and `UpliftSlot` render honest empty states with in-source
   explanations. **A repo-wide grep found no fabricated data in any production
   frontend render path.**

9. **The Check_Registry's own engineering is sound.** A strict four-way status
   partition that raises `StatusPartitionError` if the counts do not sum
   (`verify_claims.py:1834-1841`); a check that raises, returns the wrong type, or
   reports an unknown status is **coerced to FAIL** (`:1808-1832`); and SKIPs get a
   dedicated `NOT VERIFIED -- n SKIP (a SKIP is not a PASS)` callout (`:1875-1885`).
   The design closes the vanishing-check hole. It deserves a CI call site
   (Requirement 1).

10. **`doc_truth._claim_readme_headline_counts` is real mechanical narrative
    pinning.** It *executes* the suite at evaluation time, parses the summary, and
    fails naming each drifted category, with a recursion guard
    (`doc_truth.py:235-262`). Nothing is hardcoded. This is the correct pattern; it is
    applied to one document.

11. **The `uplift/` package is substantial and honest in construction.**
    `interfaces.py`, four named baselines with a README, `kpi.py`, `contract.py` +
    `metric_contract.yaml`, `scenarios.py`, `harness.py`,
    `consensus_arm.py:666::build_consensus_arm` (importing the real
    `ConsensusProtocol` and `AGENT_ENDPOINTS`, reachable from `cli.py:144`),
    `fidelity.py`, `uplift_floor.py`, `cli.py`, with 56 test modules. The
    measurement apparatus for the project's central question exists. It needs to be
    *run* (Requirement 2), not built.

12. **I-1 is a genuinely blocking gate at the right scope.** `ci.yml:96-107` greps
    every Python tree, not just three, and the advisory license step next to it is
    honestly labelled as advisory in its own step name.

13. **`SensorLoop` and `OutboxDispatcher` are actually started.**
    `orchestrator/inference/serve.py:158` and `:184`, both in the lifespan, both
    guarded so a failure degrades rather than blocks startup. The Truth_Ledger C2 row
    records that the dispatcher previously existed and was never started; that is
    fixed.

14. **`WorldRuntime` really runs in the deployed stack.**
    `digital_twin/Dockerfile:44` -> `digital_twin/inference/serve.py:78-85`
    (`runtime.start(run_clock=True)`), default-enabled, with a compose service at
    `docker/docker-compose.gcp.yml:345-355`. Not a test-only object.

15. **The error-pattern ledger is the repository's best asset.** Sixty-plus `E-S*`
    entries recording non-obvious, load-bearing facts (E-S12-01 `docker compose pull`
    is a no-op with `build:`; E-S13-04 substring matching was theatre; E-S14-04 the
    real auto-stop policy is the attached one, not the documented one). Several of
    this audit's findings are re-discoveries of the *pattern* those entries describe,
    which is evidence the ledger is correctly aimed.

---

## MISSING EVIDENCE

Each gap, and the specific CI workflow or experiment that would supply it. Nothing
here was run locally; that is the point.

| Gap | Requirement | Evidence that would close it | Where it must run |
| --- | --- | --- | --- |
| Does a FAIL in the Check_Registry stop a merge? | 1 | A `verify-claims` step in `ci.yml::quality-gates` whose exit code gates the job, plus a fault-injection run on a scratch branch mutating one check to FAIL | `.github/workflows/ci.yml` |
| Is there any decision-quality uplift at all? | 2 | A nightly `uplift.yml` workflow running `python -m uplift.cli --full` at `MIN_POWERED_REPLICATES = 1000` per arm, writing `artifacts/uplift/result.json` with `incomplete: false`, then `scripts.audit.uplift_truth --check` gating on `is_proven_uplift` | new scheduled workflow; **never local** (I-0 forbids `MIN_SCENARIOS` runs) |
| Is the uplift number inside the twin's fidelity bound? | 2, I-12 | The same run recording a measured `kl_divergence` against the live distribution instead of `null` | same nightly workflow |
| Does a real trained model serve non-degraded? | 3 | The free-GPU operator runbook (`docs/runbooks/train-and-publish-checkpoint.md`) + `notebooks/train_demand_prophet.ipynb`, then `DP_HF_REPO` set so C46 flips SKIP->PASS in `ci.yml::training-smoke` | operator/Colab, then `ci.yml::training-smoke` |
| Do the nine zero-floor packages have any coverage? | 7 | One `ci.yml::quality-gates` run on `main` publishing `coverage.xml`, then `scripts/coverage_ratchet.py --apply` to seed real floors | `.github/workflows/ci.yml` |
| Does the mutation gate hold on a merge commit? | 7, 11 | Adding `push: branches: [main]` to `mutation.yml::mutation-fast`, or a scheduled sweep whose failure is actioned | `.github/workflows/mutation.yml` |
| Is the KV-cache hit rate above 0.70? | 7, I-13 | A CI step asserting the measured hit rate from the golden-trace replay | `.github/workflows/ci.yml` |
| Is tier-routing accuracy above 0.80? | 7, I-8 | A CI step asserting routing accuracy over the 200 golden traces (`tests/eval/generate_traces.py`) | `.github/workflows/ci.yml` |
| Does the Atlas console actually work for an operator? | 8 | Implement `window.__atlasHarness`, drop `\|\| true` from `frontend.yml:288`, and separately run RITE testing with 3-5 real operators — the scorecard's own `proxyCeiling` says the scripted proxy cannot establish comprehension | `.github/workflows/frontend.yml` + a human study |
| Does the console survive a real backend? | 8 | The existing nightly `integration.yml::real-stack` job, once the harness exists and a real-stack SKIP is treated as a divergence rather than as informational | `.github/workflows/integration.yml` |
| Does the Audit_Chain detect tampering? | 6 | A CI step that seeds a chain in a throwaway Postgres, mutates one row, and asserts the verifier exits non-zero; plus a scheduled verifier against the live chain | `.github/workflows/integration.yml` (has Postgres) |
| Does each gate fail when its property is violated in the real tree? | 9, 12 | Per-gate fault-injection tests operating on a temporary copy of the tree — **not** monkeypatching the evaluator | `.github/workflows/ci.yml::uplift-verify` (already runs `tests/verify`) |
| Can a non-synthetic order drive a decision? | 4 | Implement `ExternalFeedSource.poll_arrivals`, add the stream-materialization service to compose, and run the existing `sprint6-e2e-oracle.yml` end-to-end with a replayed real-order trace | `.github/workflows/sprint6-e2e-oracle.yml` |
| Is any job a required check? | 14 | `gh api repos/{owner}/{repo}/branches/main/protection` compared against a committed declaration | new reconciliation job |
| Do the CI-only gates currently pass? | 7, 11, and any "PASS" cited from CI | One observed run of `ci.yml` on `main` with the log retained | `.github/workflows/ci.yml` |

---

## Correctness Properties (for property-based testing)

All properties inherit `max_examples` from the root `conftest.py` Hypothesis
profiles (`dev`=10, `ci`/`default`=500, `nightly`=5000). **Never hardcode
`max_examples`.** Anything driving the SimPy twin, the real `ConsensusProtocol`, or
the CLI end-to-end carries `@pytest.mark.slow` so `-m "not slow"` genuinely excludes
it locally.

### Gate integrity (Requirements 1, 7, 9, 12)

- **P1 — Gate fault-injection soundness (metamorphic).** For any registered check
  and any tree mutation that violates the property that check claims to hold, the
  check returns `FAIL`. Generate mutations from a declared per-check mutation
  operator set; the evaluator must **not** be monkeypatched. This is the property
  whose absence Requirement 9 reports.
- **P2 — Status partition invariant.** For any multiset of check results,
  `PASS + FAIL + PARTIAL + SKIP == TOTAL`, and a result with a status outside the
  closed set raises. (Already held by `verify_claims.py:1834-1841`; keep it.)
- **P3 — Exit-code monotonicity.** For any result multiset, `exit_code == 1` iff
  `FAIL > 0`; adding a SKIP never lowers the exit code from 1 to 0, and converting
  any PASS to FAIL never lowers it.
- **P4 — Coverage-floor non-vacuity.** For any floors file, every gated package has
  a floor strictly greater than zero, and for any measured report below a floor the
  gate exits non-zero naming that package.
- **P5 — Ratchet monotonicity.** For any sequence of recorded thresholds
  (coverage floors, Stryker break, mutation survival, `UPLIFT_FLOOR`), the committed
  value never decreases; a decrease is rejected. Covers the Stryker 50->26 hole.
- **P6 — Doc/gate number agreement (round-trip).** For every numeric threshold
  extracted from a governance document, the number located in the corresponding
  executable gate is equal; extracting and re-locating is idempotent.

### Audit chain (Requirement 6)

- **P7 — Canonical row round-trip.** For any decision, `make_canonical_row` followed
  by canonical JSON serialization followed by parsing yields an equivalent row, and
  the field set is exactly the frozen seven keys.
- **P8 — Chain verification detects every single-row perturbation (metamorphic).**
  For any chain of length n >= 2 and any index i, altering, deleting, or reordering
  row i causes the verifier to exit non-zero and to name a break at or before i. For
  the unperturbed chain the verifier exits zero.
- **P9 — Hash independence.** For any two distinct canonical rows the digests differ;
  and `hash_payload_for_row(None, row) == hash_payload_for_row(GENESIS_HASH, row)`.
- **P10 — Append-only closure.** For any sequence of audit operations expressible by
  the application role, the row count is non-decreasing and no previously-written row
  changes bytes.

### Decision path (Requirements 5, 13)

- **P11 — Confidence gate universality.** `@pytest.mark.slow`. For any generated
  request and any tier, if the resulting decision's confidence is below the
  configured threshold then the decision is escalated and no action was dispatched.
  Currently expected to fail on Tier 1/2 — that failure is the finding.
- **P12 — Guardrail veto closure.** For any decision violating a guardrail declared
  `BLOCK`, no dispatch occurs; for any decision violating only clip-class rules, the
  dispatched action satisfies the cap.
- **P13 — Price-cap idempotence.** Applying the essential-price clip twice equals
  applying it once, and the result never exceeds 1.3x base.
- **P14 — Threshold sensitivity (metamorphic).** Raising the configured confidence
  threshold never decreases the escalation count over a fixed request corpus.
- **P15 — Selection consistency.** `@pytest.mark.slow`. For any proposal set and
  weight vector, the ratified action is a member of the recorded Pareto front, and the
  recorded front is the set selection ran over. Currently expected to be
  unconstrained — the front is stored and never read (Requirement 13).
- **P16 — Debate monotonicity.** For any proposal revised by a concession round, the
  revised payload validates against its schema and the revised utility is recomputed
  rather than copied.

### Uplift and world (Requirements 2, 4)

- **P17 — Uplift gate rejects unpowered evidence.** For any artifact with
  `incomplete: true`, or replicates below `MIN_POWERED_REPLICATES`, or a non-finite
  `headline_uplift`, the gate returns the "unavailable" code and never `EXIT_PASS`.
- **P18 — Null-uplift detection (model-based).** `@pytest.mark.slow`. When the
  Consensus_Arm is substituted by a copy of the Baseline_Arm, the measured headline
  uplift is within the declared noise tolerance of zero — the harness's own negative
  control.
- **P19 — Harness determinism.** `@pytest.mark.slow`. For any seed, two runs produce
  byte-identical arm KPI aggregates.
- **P20 — World provenance honesty.** For any world source, `is_synthetic` is true
  iff arrivals originate from a seeded generator; an unreachable configured external
  feed yields a degraded state and zero substituted arrivals.
- **P21 — Actuation observability (metamorphic).** `@pytest.mark.slow`. For any agent
  reporting `status == "executed"`, the world state read back through `perceive()`
  differs from the pre-call state; for any agent reporting `diverged`, it does not.

### Console (Requirement 8)

- **P22 — Scorecard completeness.** For any harness run, the emitted scorecard has
  exactly one row per declared Job_To_Be_Done; an empty row set is a failure, not a
  pass.
- **P23 — Ratchet sensitivity (metamorphic).** For any per-job metric degraded by any
  positive amount, the ratchet fails and names that job; for an unchanged scorecard it
  passes.
- **P24 — Interruption-precision responsiveness.** For any set of raised
  interruptions, the computed precision equals warranted/total, and changing any
  `warranted` flag changes the computed value — excluding the possibility of a
  constant.
- **P25 — Error-condition coverage.** For malformed firehose envelopes, absent
  endpoints, and dropped sockets, every surface renders a declared degraded state and
  none renders fabricated data.

**Not property-testable — use integration or example tests instead** (per the
decision guide): whether a job is a GitHub required check (Requirement 14 — single
API read); whether a workflow step is blocking (parse the YAML once); whether the
published-checkpoint registry is a placeholder (single file read); whether a compose
service exists (single read). Driving 100 iterations against GitHub Actions, GCP, or
a 21-container stack is exactly the anti-pattern I-0 and the decision guide both
forbid.

---

## Root Causes

Traced to the earliest correctable cause. One foundational correction is preferred
over many local fixes; the local fixes are listed as consequences, not as separate
work.

### RC-1 — The verification apparatus has no consequence attached

**Earliest cause:** `scripts/audit/verify_claims.py` was built as a *reporting* tool
(`make verify-claims`, a headline in `README.md`) and never given a gating call site.
Everything the registry certifies is therefore documentation-grade.

**Consequences:** Requirement 1 directly; Requirement 10 (a hand-maintained ledger
drifts because nothing generates it); Requirement 7's coverage and Stryker rows (a
ratchet constant frozen below the shipped config is invisible without a gate);
Requirement 13 (`module_liveness` exists and cannot bite).

**One foundational correction:** add a blocking `verify-claims` step to
`ci.yml::quality-gates` and *generate* the Truth_Ledger's matrix and summary from
`verify_claims --json`. Both the checker and the doc-pinning pattern already exist
(`doc_truth.py:235`); the correction is to point them at each other and consume the
exit code. Ten of this audit's fourteen findings become mechanically detectable at
the commit that introduces them.

### RC-2 — Decision quality was never measured, so nothing downstream can be calibrated

**Earliest cause:** the project's centre of gravity moved to *provable
accountability* (Sprints 11-20) before *demonstrated decision quality* had a single
completed measurement. The harness was then built (genuinely well) and gated against
a committed artifact instead of a run.

**Consequences:** Requirement 2 (a gate that passes on `incomplete: true` against a
floor of 0.0); Requirement 3 (no published model, so even a completed run would
measure untrained policies); Requirement 4 (the only world is the twin's own seeded
simulation, so an uplift number would be bounded by the simulator's generative
assumptions — and `kl_divergence` is `null`, so that bound is itself unmeasured).

**One foundational correction:** a scheduled `uplift.yml` that runs the harness to
full power, records fidelity, and gates on the already-written-and-uncalled
`is_proven_uplift`. The published model (Requirement 3) and one non-simulated world
source (Requirement 4) are the two inputs that make its output *mean* something;
sequence them in that order, because a powered uplift run on synthetic data with
untrained policies is still the most informative next measurement available and it
costs nothing to keep the floor at zero until it is honest to raise it.

### RC-3 — Gates assert vocabulary and shape where the claim is about behaviour

**Earliest cause:** the AST/grep gate pattern is cheap, deterministic, and $0 —
correctly chosen for I-1, I-2, and I-13's code rules, where the claim genuinely *is* a
shape. It was then extended to claims that are behavioural, where a source substring
cannot carry the claim.

**Consequences:** Requirement 9 (`"WorldAction" in src` decides "converted", and the
task list told the implementation to write the string); Requirement 12 (an oracle
compared against a closed form of itself; a registry gate that checks file
existence); Requirement 7's C28 (a floor gate asserting `>= 0`); Requirement 8's
FE-INV-056 (`enforced` meaning "the files exist"). The tell is a gate whose test
monkeypatches the evaluator (`test_agency_truth_gate.py:313-322`) — when the only way
to test a gate is to replace it, the gate is not observing anything.

**One foundational correction:** adopt the standard the repository already met once.
`orchestrator/tests/test_real_actuation_e2e.py:70` reads the world back through
`perceive()` — an oracle independent of the agent's self-report. Require, per gate,
one fault-injection test that violates the property **in a temporary copy of the real
tree** and asserts the gate fails (property P1). Any gate for which such a test cannot
be written is a reporting tool and should be labelled one.

### RC-4 — Invariants are enforced at a layer or route rather than at a choke point

**Earliest cause:** enforcement was added where the work happened — guardrails in
`_full_path` because that is where consensus was being built; the audit chain at the
write site because that is where rows were created.

**Consequences:** Requirement 5 (I-5 holds on the Full_Path and not on the
Fast_Path, so the tier router silently decides whether the invariant applies);
Requirement 6 (I-4 is enforced on write and never checked on read); Requirement 13
(the `@deal.pre`/`@deal.post` contract that encodes both I-5 and I-4 sits off the
production path, in tests).

**One foundational correction:** route every tier through one dispatch choke point
and put the I-5 precondition and I-4 postcondition on it — which is precisely what
`execute_consensus` (`rules.py:139-150`) was written to be. Move it onto the path
instead of writing a second enforcement site. This closes a whole-class gap with one
edit rather than duplicating guardrail calls into `_fast_path`.

---

## Prioritized Buckets

### Purpose-blocking

1. **R2** — the Uplift_Gate passes on an artifact declaring `incomplete: true`
   against a floor of `0.0`, and no workflow regenerates it. The one question the
   system exists to answer has no answer, and the gate says otherwise. *(RC-2)*
2. **R1** — the Check_Registry has no CI call site, so 26 checks and the entire
   accountability half of the purpose are unenforced. *(RC-1)*
3. **R4** — the closed autonomy loop has only ever run on a seeded SimPy simulation
   with the real-feed source an honest stub, so "supply-chain optimization" is
   validated only against the simulator's own assumptions. *(RC-2)*

### Trust and safety

4. **R5** — I-5 confidence gating does not apply on the Fast_Path; the tier router
   decides whether human oversight applies, and this exemption is recorded nowhere.
   *(RC-4)*
5. **R6** — the Audit_Chain is written, anchored, and never verified;
   `orchestrator/audit/cli.py` does not exist and both call sites swallow the exit
   code. *(RC-4)*
6. **R9** — the agency gate certifies conversion by source substring, the task list
   instructed the marker, one "converted" agent is inert as deployed, and the gate's
   own test mocks the gate. *(RC-3)*

### Capability gaps

7. **R3** — no trained model is published; a task claiming to land the registry entry
   is marked complete against an unchanged placeholder. *(RC-2)*
8. **R8** — console effectiveness is measured by a harness that does not exist; every
   JTBD and resilience test skips, the scorecard is empty, the ratchet compares a
   hardcoded constant to itself, and the step is `|| true`. *(RC-3)*
9. **R13** — the honest uplift predicate, the I-4/I-5 DbC contract, the Pareto front,
   the Tier-4 twin verdict, and four frontend modules are built, tested, and
   unreachable. *(RC-4)*

### Unproven claims

10. **R7** — coverage `84%` is enforced as `0.0` on nine of twelve packages; Stryker
    is documented `26`, configured `50`, labelled `85`, and gated at `>= 26`; the
    KV-cache `0.70` and tier-routing `80%` floors have no gate at all. *(RC-1, RC-3)*
11. **R10** — the declared single source of truth reports 48 checks against a
    registry of 53, still marks resolved rows FAIL, and its C-numbers collide with the
    registry's. *(RC-1)*
12. **R12** — the pricing "oracle" never imports the pricing agent and compares the
    twin against a closed form of the twin; the FE invariant registry validates file
    existence. *(RC-3)*

### Operational readiness

13. **R11** — no mutation gate runs on a merge commit to `main`; the narrative-truth
    gate is skipped on doc-only pushes by `paths-ignore`; six frontend jobs never run
    on `main`; `v4-compliance` is `continue-on-error`. Each condition is individually
    documented; the aggregate blocking surface is stated nowhere. *(RC-1)*
14. **R14** — whether any job is a GitHub required check cannot be determined from
    this repository, so every "blocking" claim has one unverified final step.

### Quality

15. Five of six world-mutating agents' servers pass no Kafka producer
    (`agents/*/inference/serve.py`), so their world mutation is real and their
    event-sourcing is not — recorded under R9's acceptance criterion 6.
16. `verify_claims.py:1163` returns `cid="C43"` from the check registered as C46 —
    recorded under R10's acceptance criterion 5.
17. `HitlTimeoutAction.EXECUTE_TIER1` / `EXECUTE_LAST_KNOWN_GOOD` record an action
    name for an action never performed (`escalation.py:129-137`) — recorded under R5's
    acceptance criterion 5.
18. `privacy_boundary` is declared with enforcement `BLOCK` and has no check function
    (`rules.py:41-44`) — recorded under R5's acceptance criterion 3.
19. `frontend/package.json:39,43` point `spec:check` and `audit:licenses` at files
    that do not exist. Not gating (CI calls the Python checker directly), but both
    scripts fail if invoked.

### Future resilience

20. The Truth_Ledger should be **generated**, not maintained (RC-1's correction).
    Every hand-maintained mirror of machine state in this repository has drifted at
    least once; `CLAUDE.md` already records that lesson for `AGENTS.md`, which was
    deleted for exactly this reason.
21. Every gate should carry a declared **mutation operator set** so property P1 can
    be generated rather than hand-written per gate.
22. New behavioural claims should be required to name their independent oracle at
    spec time, following the pattern of `test_real_actuation_e2e.py`.

### Optional

23. Tier-4's documented 15-120s latency bucket was not found in the Prometheus rules;
    worth confirming, low consequence.
24. `topic_consumer_truth.py` is reachable only from `Makefile:22`; folding it into
    the registry costs one line.
25. Truth_Ledger rows C1, C10, C17, C18, C25, C53 have no check; C43-C46 and C56 have
    no row. Mechanically resolved by RC-1's generator.

### Unjustified perfectionism — explicitly excluded

The following look like findings and are not. They are recorded so that work arising
from this audit does not consume effort on them, and so this audit's own criticism is
held to the relevance standard it applies elsewhere.

- **The essential-price cap clips rather than rejects** (`rules.py:94`). I-6 says
  "price cap <= 1.3x". A clip satisfies a cap. This is correct as designed.
- **`ExternalFeedSource` returns `[]`.** This is the I-7 contract working. A stub
  that logs and returns nothing is strictly better than a stub that fabricates, and
  the ADR-052 seam is declared as a seam.
- **`UPLIFT_FLOOR = 0.0`.** The zero is honestly pinned by a test and openly deferred
  to an operator step. The finding in R2 is not the zero; it is that a
  disclosed-vacuous gate is counted inside a "49 PASS" headline and that the gate
  ignores `incomplete: true`.
- **`sustainability_agent` returns `diverged` with no world effect.** The world has no
  carbon lever. Returning `diverged` with `reason="no_carbon_lever"` is the honest
  answer. The finding in R9 is about the gate that reads it as "converted", not about
  the handler.
- **C61's oracle allowlist.** A subset ratchet over four disclosed pre-existing
  mismatches, each with a rationale. That is a legitimate ratchet, not theatre.
- **`continue-on-error` on MyPy for `agents/`** and the advisory license audit. Both
  carry honest step names and a tracked TODO. Labelled advisory work is not a
  dishonest gate.
- **`|| true` on `pnpm size`** and the mobile Lighthouse WARN budgets. Declared
  informational-until-ready with a named ratchet.
- **Frontend e2e skipped on push to `main`** (E-S12-12). There is no backend on the
  runner; the reasoning is written down and correct. The R11 finding is the *absence
  of an aggregate statement*, not any individual condition.
- **`audit_outbox` accepting UPDATE.** It is a queue with a deliberate grant, not a
  ledger.
- **The DPDPA `DELETE FROM audit_decisions`.** Runs under the privileged erasure role
  by design (E-S9-10), and DPDPA erasure is a legal obligation that outranks
  append-only convenience.

---

## Confidence Summary

| Requirement | Confidence | What would change it |
| --- | --- | --- |
| R1 gate has no CI call site | **high** — grep across all 14 workflows | a required check named outside the workflow files |
| R2 uplift gate vacuous | **high** — artifact, gate, and floor all read directly | a regenerated artifact with `incomplete: false` |
| R3 no published model | **high** — file read | a non-placeholder registry entry |
| R4 synthetic-only world | **high** — stub read in full, compose grepped | an implemented `poll_arrivals` |
| R5 Fast_Path bypass | **high** — `_fast_path` read in full | a guardrail call I did not see |
| R6 chain never verified | **high** — module absent by file search | a scheduled verifier outside `.github/` |
| R6 the verifier cannot detect linkage tampering | **high** — `verify_chain` read directly; each row is checked against its own stored `prev_hash` (`audit_verify.py:71`) and the walked predecessor's `current_hash` is never compared | a linkage assertion elsewhere in the walk that I did not see |
| R7 numbers not gated | **high** for the files; **medium** for "no gate exists anywhere" (an absence claim) | a KV-cache or routing assertion in a path I did not grep |
| R8 harness absent | **high** — five method names grepped, six skip sites read | any `__atlasHarness` definition |
| R9 lexical gate | **high** — detector, `ok` computation, and test read | a behavioural probe inside `agency_truth` |
| R10 ledger drift | **high** for the structural drift; **medium** for the live counts (not run) | one observed suite run |
| R11 blocking surface | **high** for the mechanisms; **medium** for completeness (grep was truncated at 100 matches) | reading every workflow line by line |
| R12 self-referential oracles | **high** — both files read in full | — |
| R13 unreachable capability | **medium-high** — import-graph greps per symbol; dynamic imports would be missed | a runtime import I could not see statically |
| R14 required checks | **n/a** — declared unverifiable | a committed settings/ruleset file |

**Absence of evidence is not evidence of absence.** Three findings rest on absence
claims (R6's missing verifier, R7's missing floors, R8's missing harness). Each was
checked by targeted grep across the plausible locations and each is stated with the
search that was performed, so that a reader who knows of another location can
overturn it cheaply. The CI-only facts — whether the gates that *do* run currently
pass — remain unknown from this machine by design, and the workflow that would settle
each one is named in MISSING EVIDENCE.
