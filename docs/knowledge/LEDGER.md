# Insight ledger

One entry per insight that changes a decision for SYNAPSE. Vocabulary and grades are defined in
[`README.md`](README.md). Facts about the repository are marked measured (a command, run on
2026-11-13 at `origin/main` `d4f985c`), read (a file says so) or inferred.

"Present" under a verdict means the repository already does this; the entry then exists as an
audit item for session 2.

## Index

| ID | Insight | Lens | Verdict | Source docs |
|---|---|---|---|---|
| INS-001 | Many agents must beat a matched simple baseline to earn their cost | PROOF | USE | 1 + 1 paper |
| INS-002 | Name the mechanism of uplift before measuring it | PROOF | CREATE | own + 2 |
| INS-003 | Report by slice; the headline cell hides where a system wins and loses | PROOF | ADAPT | 7 |
| INS-004 | A gain inside noise is not a gain; hold cases out; keep the original as reference | PROOF | USE, present | 4 |
| INS-005 | Multi-agent failures sit at handoffs; test through the real envelope | SYSTEM | USE | 7 |
| INS-006 | Every external call: hard timeout, breaker, durable progress, trace | SYSTEM | USE, mostly present | 3 |
| INS-007 | One seam for every model call | SYSTEM | ADAPT | 3 |
| INS-008 | Keep probabilistic judgment in a small box | SYSTEM | USE, present | 4 |
| INS-009 | Grant autonomy by reversibility and blast radius, not confidence alone | SYSTEM | ADAPT | 10 |
| INS-010 | A shared, current world model lifts a planner more than a bigger model | SYSTEM | USE | 4 + 1 paper |
| INS-011 | Keep each run's full record; screen new decision logic by replay | PROOF | ADAPT | 2 |
| INS-012 | Verification is the constraint; plan sessions around it | WORKFLOW | USE | 8 |
| INS-013 | An agent needs a prod-like run it can drive and observe | WORKFLOW | ADAPT | 9 |
| INS-014 | Enforce by gate; trim prose rules newer models no longer need | WORKFLOW | ADAPT | 13 |
| INS-015 | Keep frontier models off bulk reading; write findings where the next run looks | WORKFLOW | ADAPT | 8 |
| INS-016 | Estimate from the work, not the spoken number; overruns are fat-tailed | WORKFLOW | USE | 3 + 2 studies |
| INS-017 | A sharp problem definition is the highest-leverage artifact | WORKFLOW | USE | 6 |
| INS-018 | Name the user, the workflow, and what happens after the demo | PURPOSE | USE | 12 |
| INS-019 | Fit the architecture and its footprint to the stage | OPS | ADAPT | 5 |
| INS-020 | Measure the share of work that changes the product | PROOF | ADAPT | 4 |
| INS-021 | For a narrow job, a small trained model can beat prompting a large one | OPS | PARK | 11 |
| INS-022 | Autonomy is earned on a trust curve: shadow first, promote on a measured record | SYSTEM | ADAPT | 10 |
| INS-023 | Many agents pay as breadth plus adversarial checking, reduced by ordinary code | SYSTEM | USE | 3 |
| INS-024 | Before trusting an aggregate, walk one decision against its expected trace | PROOF | USE | 5 |
| INS-025 | Give agents a map from capability to code to proof | WORKFLOW | ADAPT | 8 |
| INS-026 | Widen agent fan-out only as fast as verification allows | WORKFLOW | USE, present | 3 |
| INS-027 | Least privilege per agent: an out-of-function action is impossible, not discouraged | SYSTEM | ADAPT | 8 |
| INS-028 | Tool, skill or agent: a separate agent needs a reason | SYSTEM | ADAPT | 5 |
| INS-029 | When execution is frictionless, build the dissent in | WORKFLOW | USE | 2 |
| INS-030 | Deletion is an experiment: remove a part, rerun the fixed eval, keep it if the score holds | SYSTEM | ADAPT | 10 |
| INS-031 | A twin earns belief when fitted to real history and tested across regimes | DOMAIN | ADAPT | 5 |
| INS-032 | Every human correction is a label; compile standards from past actions | SYSTEM | ADAPT | 7 |
| INS-033 | An eval that cannot fail measures nothing | PROOF | USE, partly present | 11 |
| INS-034 | Proof of work: checkable evidence, and the process shown is the process that ran | PROOF | USE, present | 8 |
| INS-035 | Dogfood it: operate the twin store yourself with SYNAPSE advising | PURPOSE | CREATE | own + 3 + 5 |
| INS-036 | Make re-verification cheap: address expensive results by content | PROOF | ADAPT | 1 |
| INS-037 | An agent's report of its own obstruction is telemetry: aggregate it, fix the top cause | SYSTEM | ADAPT | 2 |
| INS-038 | An approver is not an operator: show the plan and let the person change any part | PURPOSE | USE, partly present | 8 |
| INS-039 | Reach users through the system they already run | PURPOSE | ADAPT | 5 |
| INS-040 | Spend the strong model at design time; ship the simple artefact it finds | OPS | CREATE | own + 2 |
| INS-041 | A learner exploits whatever earns reward, including the simulator's mistakes | PROOF | USE | 4 |
| INS-042 | Rubric first: plant the issue, then build the world around it | PROOF | ADAPT | 1 |
| INS-043 | A published benchmark recruits others and makes its author the reference | PURPOSE | PARK | 1 |
| INS-044 | Validate the scorer: check that the objective ranks outcomes as a practitioner would | PROOF | USE | 4 |
| INS-045 | Land on one workflow that already has a procedure and a measure, then expand | PURPOSE | USE | 4 |
| INS-046 | Try the action in the twin before executing it | SYSTEM | ADAPT | 1 |
| INS-047 | Keep the proven simple controller live, with a small independent arbiter | SYSTEM | ADAPT | 2 |

## Entries

### INS-001 - Many agents must beat a matched simple baseline to earn their cost

- **Lens / kind:** PROOF / warning
- **Says:** Error compounds across steps, and each agent hands on a confident answer with its
  uncertainty removed. Under matched budgets a single agent often does as well as a team. Teams
  pay off where subtasks are independent or where each step can be checked at once.
- **Sources:** SRC-POSTS-06; arXiv 2512.08296 (Kim et al.).
- **Grade:** E3 at abstract level: under matched token budgets every multi-agent variant lost
  39-70% on sequential tasks; independent agents amplified errors 17.2x and central coordination
  held that to 4.4x. The paper's tables were not read.
- **Verdict:** USE.
- **Lands:** The uplift harness already holds this standard: the comparison is against the tuned
  control E, and the first result was `baseline_wins` by 4.40 units with finding 112 as the named
  cause (read, `HANDOFF.md`). Session 2 checks whether any arm gives one policy the same
  information and compute as the consensus arm (R-03). INS-028 gives the test for whether each
  agent should be separate at all.
- **Wrong if:** after the repair in PR #87, the consensus arm beats control E by more than the
  harness's minimum detectable effect on pre-registered cells.

### INS-002 - Name the mechanism of uplift before measuring it

- **Lens / kind:** PROOF / principle
- **Says:** A coordinated system can beat a tuned control in only three ways: it knows more
  (forecasts, early disruption signals), it coordinates decisions the control makes separately
  (stock, price and routing together), or it adapts when conditions shift. Each is a separate
  hypothesis with its own scenario. A headline without a named mechanism cannot say why it won
  or lost.
- **Sources:** own, prompted by SRC-POSTS-06 and SRC-POSTS-07.
  Also SRC-SEQAI-11, SRC-SEQAI-16: separate units optimise separately unless something brings
  them together; customers valued consistency and an audit trail as well as cost.
- **Grade:** own.
- **Verdict:** CREATE.
- **Lands:** Session 2 writes, for each mechanism, the scenario cell in `uplift/scenarios.py`
  that should show it and the arm that isolates it (R-03). Folder 3 adds a question to ask of
  each cell: is the benefit expected in the mean or in the tail (INS-003)?
- **Wrong if:** no cell can be designed on the declared twin in which any of the three
  mechanisms should help. That would mean the architecture has no expected uplift on this twin.

### INS-003 - Report by slice; the headline cell hides where a system wins and loses

- **Lens / kind:** PROOF / technique
- **Says:** Measure hard cases, regression cases and subpopulations separately, so an overall
  figure cannot hide a loss in one group or a win in another. Users trust consistency across
  conditions more than a peak.
- **Sources:** SRC-POSTS-07, SRC-POSTS-08.
  Also SRC-CLASSES-01, SRC-CLASSES-08, SRC-CLASSES-20: an eval suite mixes regression cases with
  known-failure cases; score recovery after a fault and not only first output; judge a policy on
  its worst case and its spread beside its mean.
  Also SRC-SEQAI-01, SRC-SEQAI-04: judge quality, latency and cost together; the real test is a
  place or a case that was absent from tuning.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** The E5 headline is for the primary cell, unshocked (read, `HANDOFF.md`). That is the
  regime where a tuned static control should be strongest (inferred). Shock scenarios exist in
  the harness (measured: "shock" appears in 10 files under `uplift/`). Session 2 reads what the
  shocked cells showed, and whether they ran (R-02). Folder 3 adds two cuts. One is recovery:
  how fast, and at what cost, each arm returns to normal after an injected disruption. The
  other is risk: each arm's worst replicate and its spread, beside its mean. A system built to
  absorb shocks could lose on the mean and still win on the tail (inferred; nothing measured
  says so yet).
- **Wrong if:** every slice moves with the headline, so that slicing adds no information.

### INS-004 - A gain inside noise is not a gain; hold cases out; keep the original as reference

- **Lens / kind:** PROOF / technique
- **Says:** When a system is tuned against a score, accept a change only if the gain exceeds
  measured noise, test on cases kept out of tuning, change a few things at a time, and record
  failed ideas. Compare each version against the original as well as the previous one, or small
  steps add up to drift nobody chose.
- **Sources:** SRC-POSTS-01, SRC-POSTS-07, SRC-HOWTO-02.
  Also SRC-CLASSES-03: a consolidation pass writes to a copy and a person approves the diff.
- **Grade:** E1. The posts relay research whose figures were not checked and are not used.
- **Verdict:** USE, present. The Power_Report states a minimum detectable effect of 0.0235 at
  n = 1000, an A/A test ran, and the report is bound to a source digest (read, `HANDOFF.md`).
- **Lands:** Apply the same rule to policy training on Colab: held-out seeds, and acceptance
  only above the harness's minimum detectable effect.
- **Wrong if:** a trained policy is accepted on a gain smaller than that bound. The rule was
  then not applied.

### INS-005 - Multi-agent failures sit at handoffs; test through the real envelope

- **Lens / kind:** SYSTEM / warning
- **Says:** An agent checking its own work cannot see a failure that happens between agents.
  Across services, behaviour is held by contracts between producer and consumer. A hand-written
  stand-in that differs from the real message hides exactly the defect that matters.
- **Sources:** SRC-POSTS-01, SRC-POSTS-03.
  Also SRC-CLASSES-01, SRC-CLASSES-10, SRC-CLASSES-15, SRC-CLASSES-16: context lost between a
  sub-agent and its orchestrator; patterns visible only across runs; activity green in every
  layer and red in sequence; an orchestrator blind to its agent's limits.
  Also SRC-SEQAI-06: a sub-agent that reports only that it has finished leaves the orchestrator
  with nothing.
- **Grade:** E1 for the posts. The repository's own record agrees (read, `CLAUDE.md`): finding
  112 was an envelope mismatch that tests with flat params could not see (E-DQP-02), and the
  dead firehose channels of Sprint 15 were schema mismatches at a seam.
- **Verdict:** USE.
- **Lands:** Session 2 lists every seam (A2A request envelope, each Kafka topic, each firehose
  channel) and whether a test drives it through the producer's real message (R-04).
- **Wrong if:** the next three costly defects are found inside single components.

### INS-006 - Every external call: hard timeout, breaker, durable progress, trace

- **Lens / kind:** SYSTEM / technique
- **Says:** A slow dependency stalls a whole chain unless each call has a deadline. Retries need
  backoff and a breaker. A long task needs progress written somewhere durable, and a trace that
  shows which step was slow.
- **Sources:** SRC-POSTS-06.
  Also SRC-CLASSES-12, SRC-CLASSES-16: an event log and session recovery; descriptive errors
  with a bounded budget to recover.
- **Grade:** E1; standard practice.
- **Verdict:** USE, mostly present (jittered retry, breakers, trace propagation and the outbox
  are in `CLAUDE.md`).
- **Lands:** Finding 116 is the measured case of the gap: a failed lookup that grew from 0.033 s
  to 10.04 s per consult stalled E5 for 3.5 hours (read, `CLAUDE.md` E-DQP-01). Session 2 lists
  outbound calls with no deadline shorter than their tier budget (R-05).
- **Wrong if:** every outbound call already carries such a deadline.

### INS-007 - One seam for every model call

- **Lens / kind:** SYSTEM / technique
- **Says:** Large engineering organisations route all model and tool access through one gateway.
  That gives one place for timeouts, fallbacks, cost counting, access rules and swapping models.
- **Sources:** SRC-POSTS-04, SRC-POSTS-06.
  Also SRC-CLASSES-12: a gateway that alone holds the model credentials.
- **Grade:** E1.
- **Verdict:** ADAPT. At this scale the seam is one shared client module, not a service.
- **Lands:** Ollama is referenced from `orchestrator/llm/ollama_client.py` and separately from
  `agents/disruption_shield/models/reasoning.py` (measured by text search; the code was not
  read). The offline fix for E5 was applied at the Disruption Shield's own reasoner, and PR #87
  adds a second one for another agent's tracker (read, `CLAUDE.md` E-DQP-01 on `main` and on the
  PR #87 branch). Session 2 reads whether the two call sites share a client (R-06).
- **Wrong if:** all model calls already pass through one client that owns the timeout and the
  offline mode.

### INS-008 - Keep probabilistic judgment in a small box

- **Lens / kind:** SYSTEM / principle
- **Says:** Do not try to make a model deterministic. Let it interpret messy input, make the
  extracted facts explicit and validated, and let ordinary code apply the policy. The same
  holds for orchestration: a loop written as code will not skip an item.
- **Sources:** SRC-POSTS-07, SRC-HOWTO-01.
  Also SRC-CLASSES-18: deterministic code schedules and merges while the model does the part
  that varies.
  Also SRC-SEQAI-02: domain logic belongs mainly at the verification and error-handling
  boundary.
- **Grade:** E1.
- **Verdict:** USE, present (schema-validated agent outputs under I-3; rule-based guardrails).
- **Lands:** Session 2 lists any path where model text drives an action with no deterministic
  validator between them (R-07).
- **Wrong if:** no such path exists.

### INS-009 - Grant autonomy by reversibility and blast radius, not confidence alone

- **Lens / kind:** SYSTEM / principle
- **Says:** A person cannot review every action of an agent, so human attention is a budget.
  Spend it where a mistake is costly or cannot be undone, let cheap reversible actions through,
  and invest in making undo easy. The level of autonomy should be adjustable per kind of action
  as trust grows.
- **Sources:** SRC-POSTS-03, SRC-POSTS-04, SRC-POSTS-06, SRC-POSTS-08 (five posts by different
  authors); SRC-HOWTO-01 (start where the worst case is known and bounded).
  Also SRC-CLASSES-05, SRC-CLASSES-06, SRC-CLASSES-17, SRC-CLASSES-18: review placed inside the
  run at named steps, with an inbox and a batch grid; each proposed action classed as safe to
  run or needing a person; review tiered by risk as volume rises.
  Also SRC-CURSOR-02: infrastructure built for agents offers undo as a primitive, blocks
  destructive changes whatever the agent asks, and throttles background agents under load.
- **Grade:** E2 for the review pattern (reported by Anthropic, confirmed in secondary coverage).
- **Verdict:** ADAPT.
- **Lands:** Escalation is gated on confidence (I-5). No notion of reversibility is named in
  `orchestrator/` outside one test (measured by text search, which can miss a concept under
  another name). The change would be a reversibility class per `WorldAction` type that sets the
  escalation tier alongside confidence. There are four kinds (`set_policy`, `reorder`,
  `set_price_mult`, `inject_disruption`; read, `packages/synapse_common/world/models.py`), so
  the class is a four-row table. A price multiplier can be set back; stock already ordered
  mostly cannot (inferred). INS-022 covers how a kind moves up once it has a record.
  Folder 4 adds that undo belongs to the infrastructure. An undo, or a compensating action, for
  each action kind is what makes autonomy cheap to grant; session 2 reads whether the world
  offers either (R-27).
- **Wrong if:** in `audit_escalations`, override rates and loss per error do not differ between
  reversible and irreversible action types.

### INS-010 - A shared, current world model lifts a planner more than a bigger model

- **Lens / kind:** SYSTEM / fact and principle
- **Says:** Giving a planner an explicit model of the world, which checks whether each action is
  possible and tracks what is uncertain, raised a small model's task success far above a larger
  model working without one.
- **Sources:** SRC-POSTS-05; arXiv 2609.19315 (GAVEL).
  Also SRC-CLASSES-05: shared context compiled once per run into a fixed artifact that every
  later step reads.
  Also SRC-CURSOR-02: sub-agents started from one shared compressed context spend far fewer
  tokens rediscovering it.
  Also SRC-SEQAI-01: when an agent fails, the cause is more often the context it was given than
  the model.
- **Grade:** E3 for the paper and one figure (Qwen3-8B, multi-task, 19.9% to 92.6%). The domain
  is household robot tasks in simulation, so the transfer to supply decisions is by analogy.
- **Verdict:** USE.
- **Lands:** SYNAPSE has the world model (`digital_twin/world/`, typed `world_state`), and
  finding 112 says the agents were not reading their request, so no decision depended on it
  (read, `HANDOFF.md`; the consequence is recorded there as inferred). PR #87 is the repair.
  Session 2 checks that all eight handlers consume world state (R-01).
- **Wrong if:** after the repair, the consensus arm's decisions do not change when the world
  state changes.

### INS-011 - Keep each run's full record; screen new decision logic by replay

- **Lens / kind:** PROOF / technique
- **Says:** If every run stores what was proposed and what it scored, a new selection strategy
  can be tried against the stored records before any live run is paid for.
- **Sources:** SRC-POSTS-01.
  Also SRC-SEQAI-22: each task is recorded whole and kept replayable in a reconstructed
  environment.
- **Grade:** E1. The post's efficiency figures were not checked and are not used.
- **Verdict:** ADAPT.
- **Lands:** A live E5 run is expensive: 229 minutes to fail at its bound, then 3,646.5 s to
  complete (read, `HANDOFF.md`). Storing each step's agent proposals would let an arbitration
  variant be screened by one-step replay first. The limit is real: a changed decision changes
  everything after it, so replay ranks choices at recorded states and says nothing about the
  closed loop.
- **Wrong if:** on a pair whose closed-loop ranking is known (control E against the oracle arm),
  replay ranks them the other way or cannot separate them.

### INS-012 - Verification is the constraint; plan sessions around it

- **Lens / kind:** WORKFLOW / principle
- **Says:** Speeding up one part of a pipeline is capped by the rest: 10x on 30% of the work is
  1.37x overall. Faster generation also lengthens the queue for review, tests and CI.
- **Sources:** SRC-POSTS-03, SRC-POSTS-04, SRC-POSTS-08 (six or more posts); SRC-HOWTO-01 and
  SRC-HOWTO-02 (teams preparing CI and review for the volume agents produce).
  Also SRC-CLASSES-11, SRC-CLASSES-18: the scarce things are now verification, review and
  maintenance; when cycle time stalls the queue is in CI.
  Also SRC-CURSOR-01: three large companies put coding at 5 to 30 percent of an engineer's time;
  people reviewing machine-written code is the queue.
- **Grade:** The arithmetic is checked. The company figures behind it are E2.
- **Verdict:** USE.
- **Lands:** The project's own throughput record names CI as the critical path: about 20-25
  minutes per round, hours for a labelled run (read, `HANDOFF.md`). Session 3 budgets the
  implementation sessions in verification rounds, and puts work that makes verification cheaper
  first.
- **Wrong if:** implementation sessions end waiting on code to be written and not on CI or
  review.

### INS-013 - An agent needs a prod-like run it can drive and observe

- **Lens / kind:** WORKFLOW / technique
- **Says:** An agent verifies its own work well only against something runnable that behaves
  like production, with evidence it can read back. Defects hide in the differences between
  local and production.
- **Sources:** SRC-POSTS-03, SRC-POSTS-04, SRC-HOWTO-01, SRC-HOWTO-02. Both folder 2 documents
  call this the first investment, ahead of any autonomy; one speaker's first unassisted attempt
  failed on local environment setup alone.
  Also SRC-CLASSES-02, SRC-CLASSES-06, SRC-CLASSES-08, SRC-CLASSES-18: what an agent needs that
  a person takes for granted is a way to start the system, observe it, prove success and get
  past login and empty state; a tool to force a chosen state; a long unattended run is only as
  good as the suite that tells it when it is wrong.
  Also SRC-CURSOR-02: agents on a developer's machine are limited by that machine and collide in
  one workspace.
- **Grade:** E2. The repository's deploy history agrees (read, `CLAUDE.md`): E-S12-01, E-S12-02
  and E-S14-06 were all invisible locally.
- **Verdict:** ADAPT.
- **Lands:** Session 2 answers where the whole system can run for verification inside the
  budget, given the laptop limits in `.kiro/steering/local-compute-budget.md` and a GCP VM that
  is up three hours a day, and whether `scripts/deploy/verify_live.py` can target a local or
  thin-slice stack (R-08).
- **Wrong if:** an agent can already start a prod-like stack with one command and run the
  oracle against it.

### INS-014 - Enforce by gate; trim prose rules newer models no longer need

- **Lens / kind:** WORKFLOW / principle
- **Says:** A rule the system must execute works; a written request to be careful does not. The
  reverse also holds: each standing prose rule costs reasoning on every task, and rules written
  for weaker models now over-constrain stronger ones.
- **Sources:** SRC-POSTS-01, SRC-POSTS-04, SRC-HOWTO-01, SRC-HOWTO-02. Folder 2 adds an order of
  enforcement, strongest first: code structure, compiler and CI failures, automated reviewers,
  written rules, style guides. It also adds the practice of stating the outcome wanted and
  leaving the method to the agent.
  Also SRC-CLASSES-01, SRC-CLASSES-06, SRC-CLASSES-07, SRC-CLASSES-13, SRC-CLASSES-17:
  procedures move out of the standing prompt into skills loaded on demand; stored know-how has a
  half-life and is pruned by how often it helps; the model keeps absorbing the harness.
  Also SRC-SEQAI-02, SRC-SEQAI-05, SRC-SEQAI-13, SRC-SEQAI-20: steering scaffolds can be
  deleted; the model absorbs the harness within about a year; software is now built to last
  months.
- **Grade:** E2 (Anthropic's prompt reduction is confirmed in secondary coverage; the exact
  sizes differ between sources). A post's claim that a built-in command flags outdated
  `CLAUDE.md` rules is E1 and unchecked.
- **Verdict:** ADAPT.
- **Lands:** `CLAUDE.md` is 68,257 characters; 49% is sprint history and 34% is error patterns,
  leaving 17% as rules (measured). It loads at the start of every session. A proposal for the
  operator (Q-04): keep rules and live error patterns there, move the history under `docs/`.
  The `doc_truth` gate pins numbers inside `CLAUDE.md`, so a move needs its pins updated in the
  same change. The same question applies to session prompts: the last spec carried a
  180,633-byte session protocol and a 35,730-byte next-session prompt (measured). Each rule in
  them traces to a real failure, so what to keep is the operator's call; the corpus's
  practitioners would turn the rules that can be checked into checks and drop the rest.
  Folder 3 supplies the mechanism for the error patterns: group them by topic (deploy, colour
  system, multi-city, testing) into skills that load only when a task touches that topic, and
  prune the ones that stop being used. The repository has one skill today
  (`.claude/skills/synapse-engineer`).
- **Wrong if:** gate failures or repeated known mistakes rise after the trim. The removed text
  was then doing work.

### INS-015 - Keep frontier models off bulk reading; write findings where the next run looks

- **Lens / kind:** WORKFLOW / technique
- **Says:** Most agent spend goes on reading, much of it rediscovering what nobody recorded.
  Route bulk reads to a cheaper reader that returns only the answer, and enforce that with a
  hook. Record each finding where the next run will find it.
- **Sources:** SRC-POSTS-04; SRC-HOWTO-01 (cheaper models for automations nobody is watching).
  Also SRC-CLASSES-07, SRC-CLASSES-19: match the model tier and the reasoning effort to the
  difficulty of the task; the top effort setting can double cost for a marginal gain.
  Also SRC-CURSOR-02: returns to more tokens fall off logarithmically, and structured prior
  information does more than extra compute.
  Also SRC-SEQAI-01, SRC-SEQAI-02, SRC-SEQAI-08: scripts over raw traces instead of reading
  them; route by difficulty; open-weight models carry the routine work.
- **Grade:** E3 for about 90% fewer tokens on bulk reads in Spotify's own tests. E0 for the
  post's wording that the whole bill fell 90%.
- **Verdict:** ADAPT.
- **Lands:** Session 2 faces documents of 100-500 KB (`tasks.md` is 498 KB, `GATE_SURFACE.md`
  214 KB; measured). It should use the derived commands the handoff already prescribes (the
  census) and targeted searches, not full reads in the main context. The same choice exists for
  the rest of this corpus (Q-05). The same holds for reasoning effort in these sessions: bulk
  extraction does not need the top setting, and planning does.
- **Wrong if:** on one sampled folder, a cheaper reader's cards miss decision-relevant content
  that a full read finds.

### INS-016 - Estimate from the work, not the spoken number; overruns are fat-tailed

- **Lens / kind:** WORKFLOW / fact
- **Says:** A number heard before estimating pulls the estimate toward it, and people deny the
  pull. Software overruns are not evenly spread: a minority of projects overrun hugely, so a
  flat buffer does not protect.
- **Sources:** SRC-POSTS-04; Flyvbjerg and Budzier (HBR 2011, arXiv 1304.0265); Jorgensen and
  Sjoberg on customer expectation.
  Also SRC-CURSOR-01: one company sets an aggressive time box on purpose, a month for work once
  planned at nine; it works because the scope is allowed to give.
  Also SRC-SEQAI-23: one hardware operator's rule is to multiply first estimates of cost and
  time by ten.
- **Grade:** E3 for the tail (1,471 IT projects, mean cost overrun 27%, one in six about 200%).
  E3 for the anchoring setup; E0 for the post's figures (it gives 77 and 632 hours; the located
  source gives 99 and 555, and a smaller effect in a field study).
- **Verdict:** USE.
- **Lands:** "Ten implementation sessions" was said before any estimate existed. Session 3
  estimates bottom-up from the definition of finished, then ranks scope into must, should and
  could, so the session count can hold while scope gives.
- **Wrong if:** the bottom-up estimate lands at or under ten sessions with slack.

### INS-017 - A sharp problem definition is the highest-leverage artifact

- **Lens / kind:** WORKFLOW / principle
- **Says:** With agents doing the building, a well-scoped problem turns into a working change
  quickly and a vague one consumes many agent-hours for nothing. The human work is problem
  definition, architecture, review and judging whether a fix addressed the cause.
- **Sources:** SRC-POSTS-08, SRC-POSTS-04, SRC-HOWTO-01.
  Also SRC-CLASSES-04, SRC-CLASSES-07, SRC-CLASSES-14: long planning with the model before any
  dispatch; large goals with stated success criteria; let the model interview the person to draw
  requirements out.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** Session 3's definition of finished, written so that a test can fail it, comes
  before any implementation plan. Session 3 should open with the model interviewing the
  operator, one concrete question at a time, starting from Q-01 to Q-03, and not with a long
  written brief from either side.
- **Wrong if:** session 3 ends with a plan and no failable definition of finished. The entry was
  then not applied.

### INS-018 - Name the user, the workflow, and what happens after the demo

- **Lens / kind:** PURPOSE / principle
- **Says:** Three questions decide whether something built is a product: who pays or depends on
  it, which daily workflow it sits inside, and what happens once the demonstration is over.
  What defends it is how hard it is to remove from real operations, and data only it holds.
- **Sources:** SRC-POSTS-08, SRC-POSTS-02.
  Also SRC-CLASSES-05, SRC-CLASSES-07, SRC-CLASSES-11, SRC-CLASSES-15, SRC-CLASSES-20: keep to
  one core user; when output is cheap the question is which outputs matter; product sense comes
  from sitting with users; confirm people have the problem before building; context that exists
  nowhere public is the moat.
  Also SRC-CURSOR-02: with code abundant the limits are commercial value, changing what users
  do, a first-principles view of what to build, and distribution.
  Also SRC-SEQAI-05, SRC-SEQAI-08, SRC-SEQAI-13, SRC-SEQAI-17: what protects a product is data
  or position nobody else holds; the measure is use, not purchase; domain depth outlasts
  scaffolding; be clear what the product does today.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** The README states there is no live order pipeline, the traces are synthetic and the
  system is single-tenant (read). No user is named anywhere I read this session. The operator's
  stated aim is to help millions of people; session 3 has to say which people, doing what (Q-01).
- **Wrong if:** a named user and workflow already exist in the repository and were missed.

### INS-019 - Fit the architecture and its footprint to the stage

- **Lens / kind:** OPS / warning
- **Says:** An architecture is right for a team, a stage and a lifespan, not in general. An
  agent asked to design will propose the complete system; a small team should defer what can
  wait.
- **Sources:** SRC-POSTS-08, SRC-POSTS-04.
  Also SRC-CLASSES-04, SRC-CLASSES-18: fewer technologies means faster work for people and for
  agents; a codebase can now be rewritten from itself cheaply.
  Also SRC-SEQAI-11: a three-part test for what to keep: needed to stay up, to meet hard
  obligations, or to deliver the promised result.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** The deployed stack is 21 containers on one 8-vCPU VM (read, `CLAUDE.md`
  E-S14-05), with Kafka, Neo4j, Redis, Feast and MLflow behind eight agents, for a system with no
  user yet. Session 3 decides the smallest footprint that demonstrates the claim, against the
  remaining cloud credit (Q-02, T-002). INS-030 turns each proposed cut into an experiment
  instead of an opinion.
- **Wrong if:** the full stack runs for the whole verification period inside the credit with
  margin, and every component is needed by the definition of finished.

### INS-020 - Measure the share of work that changes the product

- **Lens / kind:** PROOF / technique
- **Says:** When agents make pull requests cheap, counting them says nothing. Tag each change by
  type and watch what share is product work.
- **Sources:** SRC-POSTS-04.
  Also SRC-CLASSES-07: measure effective output per unit of compute, not volume.
  Also SRC-CURSOR-01, SRC-CURSOR-02: count completed backlog and idea-to-release time, not hours
  saved; in one account shipped code rose eightfold while app usage stayed flat.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** Of the last 300 non-merge commits on `origin/main` (2026-05-22 to 2026-11-01), 75
  are `feat`, 94 `fix`, 48 `docs`, 15 `ci`, 10 `chore`, 58 other (measured from commit
  prefixes). A prefix is a weak signal: a `feat` can add a gate. Session 2 splits the same
  commits by path, product code against gates and documents (R-09).
- **Wrong if:** the path split shows most `fix` and `docs` commits changed product behaviour.
  The prefix mix would then mislead.

### INS-021 - For a narrow job, a small trained model can beat prompting a large one

- **Lens / kind:** OPS / technique
- **Says:** On one narrow, labelled task, training a small open model moved accuracy by 15-21
  points where adding prompt examples moved it by less than one. A model also behaves
  differently in each harness, so it should be trained and measured in the one it will run in.
- **Sources:** SRC-POSTS-05, SRC-POSTS-02.
  Also SRC-CLASSES-04: the strongest model for development and research, small tuned models in
  production.
  Also SRC-SEQAI-03, SRC-SEQAI-04, SRC-SEQAI-07, SRC-SEQAI-10, SRC-SEQAI-14, SRC-SEQAI-18, SRC-
  SEQAI-21, SRC-SEQAI-22: reinforcement learning needs a great many rollouts; if the starting
  policy never succeeds there is nothing to reinforce; find the fit on general models first and
  train afterwards; several learners at once make each other's world unstable; learning
  machinery built before the workflow is settled is debt.
- **Grade:** E1. One self-reported experiment and one vendor post.
- **Verdict:** PARK until session 3 allocates the Colab units.
- **Lands:** It supports spending the 200 Colab units on one or two narrow models trained inside
  the twin they will be scored in, which is also the standing direction "two agents deep beats
  eight shallow". It does not decide which models.
- **Wrong if:** INS-002 shows the expected uplift comes from coordination or adaptation and not
  from better forecasts. Training would then not be the first spend.

### INS-022 - Autonomy is earned on a trust curve: shadow first, promote on a measured record

- **Lens / kind:** SYSTEM / principle
- **Says:** Teams that now let agents merge code unattended got there in steps. They began where
  the result could be checked empirically and the worst case was bounded, ran the new path in
  shadow beside the existing one for weeks, and widened its authority only as the record held.
  Going straight to many unattended agents spends money and trust for nothing.
- **Sources:** SRC-HOWTO-01, SRC-HOWTO-02.
  Also SRC-CLASSES-04: agent-written changes exposed in stages behind hard barriers.
  Also SRC-CURSOR-01: small teams prove a new practice before it is released to everyone.
  Also SRC-SEQAI-03, SRC-SEQAI-06, SRC-SEQAI-08, SRC-SEQAI-10, SRC-SEQAI-11, SRC-SEQAI-23: first
  drafts for a person to review; gates before and after release; a proactive adviser as the
  first form; one operator's span grew from one vehicle to a hundred as the record held.
- **Grade:** E2. The talk is confirmed by several secondary summaries. Its throughput figures
  are self-reported, differ by 2.5x between sources, and are not used.
- **Verdict:** ADAPT.
- **Lands:** E5 already scores the consensus arm's recommendations as if they had been
  executed, which is a shadow comparison run offline. The running system has no decision-level
  shadow mode (measured by text search: outside tests, "shadow" appears only in an audit
  walker, the metrics module and reward shadowing). The product form would be: the consensus
  runs beside the tuned control in the standing world, its recommendations are scored and
  shown, and each action kind is promoted to acting once its record beats the control by more
  than noise. That is also a way for a first user to adopt it without risk (Q-01, Q-03).
- **Wrong if:** the twin's fidelity cannot be established. A shadow score is a counterfactual
  computed on the twin, and it tells an operator nothing if the twin does not describe their
  store (R-13).

### INS-023 - Many agents pay as breadth plus adversarial checking, reduced by ordinary code

- **Lens / kind:** SYSTEM / technique
- **Says:** Where practitioners get value from many agents, the shape repeats: fan out over
  independent pieces, have other agents attack each result from several angles, then reduce to
  the few findings worth attention. The orchestration is ordinary code, so every item is
  processed and the control flow is certain. They treat it as extra compute spent at decision
  time and keep it for problems whose steps are not known in advance.
- **Sources:** SRC-HOWTO-01. Consistent with arXiv 2512.08296 (INS-001), where parallel tasks
  gained and sequential ones lost.
  Also SRC-CLASSES-13, SRC-CLASSES-18: a reviewing stage must assume a fault and hunt for it,
  because one that confirms adds nothing; deterministic orchestration around the model.
- **Grade:** E1; practitioners describing their own use.
- **Verdict:** USE.
- **Lands:** The consensus has this shape: collect is the fan-out, debate is the adversarial
  check, arbitration is the reducer. ADR-052 recorded that debate never revised a proposal and
  that arbitration was computed and then ignored (read, `CLAUDE.md`). Tests named for binding
  arbitration and debate concession now exist on `main` (measured by file name; not read).
  Session 2 reads whether both stages now act, and specifies ablation arms that remove each
  (R-16).
- **Wrong if:** removing debate or arbitration leaves the consensus arm's outcome unchanged.
  Those stages would then be cost with no return.

### INS-024 - Before trusting an aggregate, walk one decision against its expected trace

- **Lens / kind:** PROOF / technique
- **Says:** A team running agents across its engineering work studies single traces more than
  benchmark totals. For a task that ought to work, they write what the agent should do at each
  step, find the step where the real trace departs, and ask whether context or a tool was
  missing.
- **Sources:** SRC-HOWTO-01.
  Also SRC-CLASSES-15, SRC-CLASSES-16: hunt on the assumption that something is already wrong;
  session traces exposed a cause that automated scoring had missed.
  Also SRC-SEQAI-01, SRC-SEQAI-06: the trace, not the code, is the source of truth for what an
  agent system did.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** Finding 112 is the case for it. The aggregate said the consensus arm lost; the
  cause, that no agent read its request, would show in the first agent call of any one decision
  (inferred from `CLAUDE.md` E-DQP-02). The handoff's own lesson says the same: read the log
  before naming a cause. Session 2 writes the expected trace for one decision after PR #87,
  from world state through each agent's request, proposal, debate, arbitration and action to
  the change in the world, then compares it with a real one (R-17).
- **Wrong if:** the walked decision shows every stage consuming what it should. No defect of
  that class then remains on that path, and the walk cost an hour.

### INS-025 - Give agents a map from capability to code to proof

- **Lens / kind:** WORKFLOW / technique
- **Says:** An agent with good tools still wastes effort if it cannot get from a behaviour a
  user sees to the code behind it. A short structured file mapping each feature to its
  components and entry points sends it straight there. The map needs upkeep, or it misleads.
- **Sources:** SRC-HOWTO-02, SRC-POSTS-04, SRC-POSTS-06.
  Also SRC-CLASSES-03, SRC-CLASSES-08, SRC-CLASSES-10, SRC-CLASSES-11, SRC-CLASSES-18: an index
  file first; a catalogue of systems and owners exposed as a tool; and a counterweight, that
  written documentation decays and the repository should be asked directly.
- **Grade:** E2 for the talk, E1 for the posts.
- **Verdict:** ADAPT.
- **Lands:** `docs/state/MODULE_INVENTORY.md` exists at 9,106 bytes and was last committed on
  2026-06-08 (measured), five months and several specs ago. For SYNAPSE the useful map has four
  columns: the capability, its code, the gate or test that proves it, and the command that runs
  it. Session 2 checks whether the inventory is current and whether a session can start from it
  (R-10).
- **Wrong if:** a session that starts from the map still needs broad searching to find where a
  capability lives.

### INS-026 - Widen agent fan-out only as fast as verification allows

- **Lens / kind:** WORKFLOW / warning
- **Says:** Running many agents before each one's output can be trusted multiplies cost, not
  output. Trust is built on one or two supervised agents first.
- **Sources:** SRC-HOWTO-02, SRC-POSTS-04.
  Also SRC-CLASSES-02: one person can attend to four or five agent sessions at most.
- **Grade:** E2. The repository's own record agrees (read, `HANDOFF.md`): dispatches wider than
  five finished 4 of 18 agents, batches of at most five finished 10 of 14, and steering rule G8
  came from those losses.
- **Verdict:** USE, present (G8).
- **Lands:** The implementation sessions keep G8. If cheaper readers are used on the rest of
  this corpus (Q-05), they run in batches of at most five, with one folder also read in full as
  a check.
- **Wrong if:** under the current plan limits, wide batches finish at the same rate as narrow
  ones.

### INS-027 - Least privilege per agent: an out-of-function action is impossible, not discouraged

- **Lens / kind:** SYSTEM / principle
- **Says:** Give each agent what its job needs and nothing more, and enforce that with hard
  controls, not instructions: read-only credentials, network policy, access rules on each
  tool. Teams report that more layers of this kind are what let them grant more autonomy.
- **Sources:** SRC-HOWTO-01, SRC-POSTS-06.
  Also SRC-CLASSES-03, SRC-CLASSES-09, SRC-CLASSES-10, SRC-CLASSES-12: reference material
  mounted read-only; an agent acts under the identity and permissions of whoever asked; a
  restricted language for what an agent may express.
  Also SRC-CURSOR-02: small, sharp, composable primitives let capability grow without the risk
  growing.
  Also SRC-SEQAI-20: the acting agent can run only tools an administrator has approved.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** `WorldAction` carries an id, a kind, a place, parameters and a decision id. It has
  no field naming the agent that issued it, and its four kinds put `inject_disruption` beside
  `reorder`, `set_price_mult` and `set_policy` (read,
  `packages/synapse_common/world/models.py`). A text search of the world packages finds no
  allow-list. Enforcement may sit in the layer that calls the world, which was not read.
  Session 2 reads it (R-18).
- **Wrong if:** a per-agent allow-list exists at the calling layer, and a test proves that an
  action outside an agent's function is refused.

### INS-028 - Tool, skill or agent: a separate agent needs a reason

- **Lens / kind:** SYSTEM / principle
- **Says:** A capability can be a tool the orchestrator calls, a procedure it loads when needed,
  or a separate agent. Practitioners give two reasons for the third: parallel work on
  independent pieces, and a fresh view kept apart from the main context, as a reviewer has. A
  sub-agent that only wraps a tool should be folded back. Start with one loop and split only
  when a specific failure calls for it. Three teams in the corpus removed a layer of agents and
  improved, one of them on an inventory agent covering stock, forecasting, supplier choice and
  ordering.
- **Sources:** SRC-CLASSES-01, SRC-CLASSES-05, SRC-CLASSES-16.
  Also SRC-SEQAI-01, SRC-SEQAI-16: an explicit staged architecture is still right where control
  and predictability are required, while another team prefers one agent following a written
  procedure over a graph of narrow steps.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** Session 2 classifies each of the eight (R-22): does it hold its own objective,
  state and loop, or is it a function the orchestrator calls and waits on? In fairness to the
  design, SYNAPSE has a third reason the talks do not cover: each agent carries its own reward
  (I-2), so the agents can stand for objectives that genuinely conflict. That reason holds only
  if the objectives do conflict in practice and arbitration binds (INS-023).
- **Wrong if:** each of the eight has a distinct objective that changes the arbitrated outcome,
  and removing any one worsens the measured result.

### INS-029 - When execution is frictionless, build the dissent in

- **Lens / kind:** WORKFLOW / warning
- **Says:** Models lean toward agreeing with whoever is asking, and an idea now becomes working
  code without the argument that used to filter weak ideas out. The checks that peers once
  supplied have to be placed deliberately.
- **Sources:** SRC-CLASSES-04, SRC-POSTS-08.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** This folder's rule that every corpus folder is asked what it holds against SYNAPSE
  is one such check. Session 3's cut list should give every component it keeps a criterion for
  removing it. It applies to this collaboration too: the model's agreement with a plan is weak
  evidence that the plan is good.
- **Wrong if:** by the end of session 3, nothing in `TENSIONS.md` has changed a decision. The
  dissent would then be decoration.

### INS-030 - Deletion is an experiment: remove a part, rerun the fixed eval, keep it if the score holds

- **Lens / kind:** SYSTEM / technique
- **Says:** The teams that slimmed their systems did it under a fixed eval: take out an
  instruction, a tool, a sub-agent or a skill, run the same cases with and without it, and keep
  the removal if the score holds. In the corpus's inventory-agent example the score rose.
  Processes and rules pile up because nobody removes one unprompted, so someone has to be
  given explicit permission to delete, and ownership and retirement have to be decided when a
  rule is created.
- **Sources:** SRC-CLASSES-01, SRC-CLASSES-06, SRC-CLASSES-07, SRC-CLASSES-11, SRC-CLASSES-20.
  Also SRC-CURSOR-01, SRC-CURSOR-02: a working prototype is required before a specification is
  debated; planning artifacts built to protect scarce engineering time are now overhead.
  Also SRC-SEQAI-11, SRC-SEQAI-20, SRC-SEQAI-23: cut once, not in nibbles; effortless creation
  breeds duplicates that need pruning; the most reliable part is the one removed.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** The uplift harness is SYNAPSE's fixed eval. Session 3's cut list can be a list of
  experiments: for each agent, consensus stage or backing service proposed for removal, the arm
  that runs without it. For gates and documents the question is the operator's (Q-06): 68
  registered checks and 57 decision records have no retirement path that I have read.
- **Wrong if:** one harness run costs so much that ablation arms are unaffordable. INS-011 and
  INS-036 would then come first.

### INS-031 - A twin earns belief when fitted to real history and tested across regimes

- **Lens / kind:** DOMAIN / principle
- **Says:** Where the result of a decision arrives late, proof needs a model of the world. The
  corpus's two working examples build theirs from reality: a commerce platform models each
  merchant as a sequence of real actions and tests interventions on that model before acting,
  and a trading firm runs every strategy through fifteen or more years of real history, across
  different conditions and stresses, over one standard data pipeline so results are comparable.
- **Sources:** SRC-CLASSES-04, SRC-CLASSES-20, SRC-CLASSES-09.
  Also SRC-SEQAI-03, SRC-SEQAI-13: benchmarks resemble training tasks while the world keeps
  changing; progress comes first where feedback is programmatic.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** SYNAPSE's world is declared, not fitted, and the handoff records its fidelity as
  unknown and an earlier dataset's terms as declined (read, `HANDOFF.md`). The seam for real
  data exists: a `WorldSource` interface with a simulator behind it now and an external feed
  planned (read, `CLAUDE.md`, ADR-052). Session 2 finds what real, permissively licensed
  history could calibrate the world (R-13). See T-012.
- **Wrong if:** no usable dataset resembles a dark store's demand. Every result then stays
  conditional on the declared world, and the product should not lean on shadow scores
  (INS-022).

### INS-032 - Every human correction is a label; compile standards from past actions

- **Lens / kind:** SYSTEM / technique
- **Says:** The difference between what a system produced and what the expert finally accepted
  is training data. One company turned thirty thousand past edits by its chief editor into a
  skill, and records each new difference as a rule. Another built its automated reviewer from
  its founder's past review comments. Standards are compiled from what people did, not written
  from scratch.
- **Sources:** SRC-CLASSES-08, SRC-CLASSES-09, SRC-CLASSES-20.
  Also SRC-SEQAI-01, SRC-SEQAI-07, SRC-SEQAI-09, SRC-SEQAI-22: traces curated into experiments;
  live feedback polishes a model that is already good; corrections recorded where they happen,
  including edits, undos and retries.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** Two places. In the product, operator overrides are recorded in `audit_escalations`
  (read, `CLAUDE.md`); session 2 reads whether anything learns from them (R-23). In the
  workflow, the roughly 120 numbered findings of the last spec are this project's corrections.
  Distilled into one page of defect classes, they would make a review skill that a session can
  load, in place of a ledger of several hundred kilobytes.
- **Wrong if:** overrides are too few or too inconsistent to learn from. With no operator yet,
  there are none; INS-035 is one way to produce some.

### INS-033 - An eval that cannot fail measures nothing

- **Lens / kind:** PROOF / principle
- **Says:** An eval the system always passes has stopped measuring. Build evals from real
  failures, keep raising them, and keep a set of cases the current system fails so that a new
  model or design has something to prove itself on. Plant a check that must fail, to show the
  instrument reports failure. A benchmark score is an entrance exam; a trial on the real work
  is what counts. Evals have bugs of their own and need upkeep.
- **Sources:** SRC-CLASSES-06, SRC-CLASSES-07, SRC-CLASSES-08, SRC-CLASSES-09, SRC-CLASSES-13,
  SRC-CLASSES-14.
  Also SRC-SEQAI-01, SRC-SEQAI-04, SRC-SEQAI-10, SRC-SEQAI-20, SRC-SEQAI-23: a private eval
  defines what good means; hard and varied cases over volume; the benchmark before any training;
  a newer model is admitted only through the evals; parts tested until they break.
- **Grade:** E1.
- **Verdict:** USE, partly present. The uplift harness ran a negative control that passed and a
  positive control that was detected, and the house standard already says that a standard which
  only ever passes is not being applied. A gate-falsification sweep exists (C72), was not run in
  the README's counted job, and has an open defect in how it credits an abstention (read,
  `README.md`, `HANDOFF.md` decision (b)).
- **Lands:** Session 2 reads which of the 68 checks the sweep can make fail and which it cannot
  (R-24). The cells where the consensus arm loses to control E are SYNAPSE's standing set of
  failing cases: any new policy or design is admitted on those.
- **Wrong if:** the sweep, repaired, shows every check failing on its planted fault. This would
  then be fully present.

### INS-034 - Proof of work: checkable evidence, and the process shown is the process that ran

- **Lens / kind:** PROOF / principle
- **Says:** Autonomy with no empirical validation is theatre. Work is proven by evidence a
  reviewer can check, including evidence that what was not asked for did not change. Two
  systems with the same output do not deserve the same trust: how the answer was produced has
  to be legible, and it has to be the path that actually executed. One contract can be checked
  from several places, by a person, by an agent and by CI.
- **Sources:** SRC-CLASSES-07, SRC-CLASSES-12, SRC-CLASSES-14, SRC-CLASSES-16.
  Also SRC-CURSOR-01, SRC-CURSOR-02: review by intent and by demonstration; an interface that
  shows the plan and each step as it happens.
  Also SRC-SEQAI-16, SRC-SEQAI-20: a transparent record in place of a black box was itself what
  customers bought; the boundaries and controls are the product.
- **Grade:** E1.
- **Verdict:** USE, present. The decision anatomy, the audit hash chain and the single deploy
  oracle with three call sites are this (read, `CLAUDE.md`).
- **Lands:** It is the corpus's strongest support for treating the proof and audit layer as an
  asset (T-004). It also names the kind of gap recorded as T-009, where the path measured was
  not the whole path claimed. Implementation sessions end with an evidence block: commands,
  outputs, and the scope of the diff.
- **Wrong if:** an operator, shown a decision's anatomy, cannot tell from it why the decision
  was made. The legibility would then be for engineers only.

### INS-035 - Dogfood it: operate the twin store yourself with SYNAPSE advising

- **Lens / kind:** PURPOSE / technique
- **Says:** Product sense comes from using the product every day and from pressure by a
  demanding first user, not from dashboards. SYNAPSE has no user, but it has a standing world
  and a console. The operator can be the store manager of the twin for a fixed period, with the
  consensus advising in shadow, accepting or overriding its recommendations.
- **Sources:** own, prompted by SRC-CLASSES-11, SRC-CLASSES-16, SRC-CLASSES-09.
  Also SRC-SEQAI-11, SRC-SEQAI-14, SRC-SEQAI-16, SRC-SEQAI-20, SRC-SEQAI-23: a request the
  system cannot meet shows what to build; almost no evaluation includes the people in the loop;
  founders and engineers sat with every customer; the users, not the engineers, set the service
  hours.
- **Grade:** own.
- **Verdict:** CREATE.
- **Lands:** The pieces exist (read, `CLAUDE.md`): the standing world, an ingress console for
  injecting orders, a cockpit for escalations, and steering. A dogfooding block in the
  implementation plan would produce three things nothing else in the project can: override
  labels (INS-032), a first trust record per action kind (INS-022), and a list of what is
  confusing or missing in the console from someone who had to use it. It is also the cheapest
  honest answer to "who has used this?".
- **Wrong if:** operating the twin teaches nothing a real store manager would recognise, which
  is the fidelity question again (INS-031, T-012).

### INS-036 - Make re-verification cheap: address expensive results by content

- **Lens / kind:** PROOF / technique
- **Says:** One team re-runs its agent's whole plan from the top on every change, which removes
  drift, and makes that affordable by storing each expensive step under a hash of its inputs.
  Only steps whose inputs changed are recomputed; a thousand-line plan re-evaluates in seconds.
- **Sources:** SRC-CLASSES-12.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** A full E5 run took 229 minutes at its bound and about an hour when it completed
  (read, `HANDOFF.md`). The Power_Report is already bound to a digest of its source set, which
  is the same idea at the coarsest grain. Session 2 reads whether replicate results are stored
  by seed, arm and source digest, and what invalidates them (R-25). If each replicate were
  addressed that way, a change to one arm would recompute only that arm.
- **Wrong if:** replicates are already cached at that grain, or the digest they depend on
  changes with nearly every commit, so that nothing would ever be reused.

### INS-037 - An agent's report of its own obstruction is telemetry: aggregate it, fix the top cause

- **Lens / kind:** SYSTEM / technique
- **Says:** One platform gave its agent a way to report what was obstructing it. Aggregated,
  the reports revealed outages before monitoring did and fed a pipeline that drafts repairs for
  people to approve. The report is a signal about the system, not a complaint to be logged.
- **Sources:** SRC-CLASSES-17.
  Also SRC-SEQAI-01: an agent that scans traces for clusters of failure and files each with its
  evidence.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** SYNAPSE's agents already report honestly: each proposal carries a provenance
  record with a `degraded` flag, and decisions list their degraded agents (read, `CLAUDE.md`,
  ADR-040 and ADR-044). Nothing I have read ranks the reasons. Session 2 measures what share of
  consensus decisions run with at least one degraded agent, and why (R-21). The top reason is a
  strong candidate for the first implementation session.
- **Wrong if:** no decision runs degraded, or the reasons are spread evenly with no dominant
  cause.

### INS-038 - An approver is not an operator: show the plan and let the person change any part

- **Lens / kind:** PURPOSE / principle
- **Says:** An interface that offers a request, a wait and then accept or reject turns the
  person into an approver and their judgment into a rubber stamp. One that shows the plan and
  each step, and lets the person step in and change any part at any point, keeps them the
  author. When producing the work is cheap, the person's craft moves to judgment before it and
  responsibility after it. Other teams in the corpus say the same in practice: the system
  generates, and the person validates and adjusts in a proper interface, inside the run and not
  only at its end.
- **Sources:** SRC-CURSOR-02, SRC-CLASSES-16, SRC-CLASSES-05.
  Also SRC-SEQAI-02, SRC-SEQAI-06, SRC-SEQAI-12, SRC-SEQAI-13, SRC-SEQAI-19: keep the agent
  separate from any one interface; a queue for unattended work and a live view for stepping in;
  a job is its purpose; fixed layouts cost less attention; show the trade-off curve and let the
  person choose the point.
- **Grade:** E1.
- **Verdict:** USE, partly present. The console shows a decision's full anatomy and has
  steering and override (read, `CLAUDE.md`).
- **Lands:** What I have not read is the grain of an override. Session 2 reads whether an
  operator facing an escalation can change part of a recommendation, such as a quantity or a
  price multiplier, or can only accept or reject it (R-28). A partial edit is also a richer
  label than a yes or no (INS-032), and it is what a shadow advisor needs to be useful
  (INS-022).
- **Wrong if:** in use, operators only ever accept or reject, so that finer control goes
  unused. Dogfooding would show it (INS-035).

### INS-039 - Reach users through the system they already run

- **Lens / kind:** PURPOSE / principle
- **Says:** The companies in this folder that found adoption did not ask the customer to move.
  A driving company ships inside cars that manufacturers already build. A model platform runs
  on the customer's own infrastructure. A coding-agent company found users only when it worked
  inside the tools developers already had, and it keeps what it learns in the customer's own
  repository. The one logistics operator in the corpus found that the deciding component was
  15% of the work, and that fitting into customers' ordering and stock systems was much of the
  rest.
- **Sources:** SRC-SEQAI-02, SRC-SEQAI-04, SRC-SEQAI-08, SRC-SEQAI-11, SRC-SEQAI-23.
- **Grade:** E1. The landing below is own.
- **Verdict:** ADAPT.
- **Lands:** SYNAPSE today is a platform to be adopted whole: 21 containers and its own data
  stores (read, `CLAUDE.md`). A retailer already has a point-of-sale or stock system. The form
  this entry points to is a small decision service that reads the retailer's existing feed and
  writes a recommendation back to where they already work. The seam for it was built:
  `WorldSource`, with an external feed named as the later source (read, `CLAUDE.md`, ADR-052).
  Session 2 reads which fields the sensor and the replenishment slice actually need from the
  world (R-37). Session 3 costs the thin form against the full stack (T-002, Q-03).
- **Wrong if:** the first named user (Q-01) has no system to plug into, or wants to run the
  whole platform themselves.

### INS-040 - Spend the strong model at design time; ship the simple artefact it finds

- **Lens / kind:** OPS / technique
- **Says:** A capable model can be spent in a measured loop that searches for a better process,
  and what ships is ordinary code that costs nothing per decision and behaves the same every
  time. One company has a model write each automation once and then runs the static code.
  Another speaker's point is that models now improve a process by repeated measured trial, so a
  process is something an agent can be set to optimise.
- **Sources:** SRC-SEQAI-05, SRC-SEQAI-20.
- **Grade:** E1 for the practice; own for its use here.
- **Verdict:** CREATE.
- **Lands:** The $0 rule (I-1) bars paid models at run time. It does not bar them at design
  time, and the operator holds a coding-agent subscription. The uplift harness is the
  measurement such a loop needs. A candidate for one implementation session: have the coding
  agent propose replenishment policies as plain code, score each against the harness, and keep
  what beats the tuned control on seeds it never saw. The run-time product is then a readable,
  auditable policy. It is also a missing arm for T-001: a searched simple policy, set against
  the consensus. Two cautions. The search will fit the twin (INS-041, T-012). And a full E5 run
  took about an hour when it completed (read, `HANDOFF.md`), so the loop needs a cheaper screen
  first (INS-011, INS-036, R-30).
- **Wrong if:** the harness gives the loop only a handful of evaluations per session, or the
  policy it finds fails on scenario families held out of the search.

### INS-041 - A learner exploits whatever earns reward, including the simulator's mistakes

- **Lens / kind:** PROOF / warning
- **Says:** Four sources say it independently. A coding model in training looked for ways to
  score without doing the work. A model told to minimise compile errors learned to write
  nothing. Learners satisfy a verifier by shortcut. And the founders of a lab built on
  simulation name the limit themselves: a simulator is a person's model of the world, so the
  learner inherits that person's assumptions. An environment that differs from reality teaches
  the difference.
- **Sources:** SRC-SEQAI-07, SRC-SEQAI-14, SRC-SEQAI-18, SRC-SEQAI-21.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** It binds any Colab spend on training policies in the declared twin (T-012), and the
  search in INS-040 as much as gradient training. The guards the corpus names: hold out whole
  scenario families, vary the twin's parameters between training and test, read sample
  trajectories and not only the score, and treat a gain that looks too large as a defect report
  on the environment. SYNAPSE has a `test_reward_safety.py` per agent (read, `CLAUDE.md`).
  Session 2 reads whether those tests look for reward earned without the outcome, or only check
  sign and bounds (R-34).
- **Wrong if:** nothing is ever trained or searched against the twin. Then there is no learner
  to exploit it.

### INS-042 - Rubric first: plant the issue, then build the world around it

- **Lens / kind:** PROOF / technique
- **Says:** A company that could not use its clients' confidential material had its domain
  experts write the grading rubric before anything else, plant known issues, and generate the
  surrounding material to contain them. The answer key exists by construction, and no real data
  is needed to know what a correct response must find.
- **Sources:** SRC-SEQAI-10.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** SYNAPSE is in the same position: no real data, and a declared world. Its scenario
  cells live in `uplift/scenarios.py` (measured: the file exists; not yet read). For each
  planted event, such as a supplier failure, a demand spike or a cold-chain fault, the operator
  writes in advance what a competent response must detect and do, and how soon. The harness
  then reports whether each planted issue was found and handled, beside the aggregate
  objective. That gives a result a reader can check case by case, and it answers part of T-012:
  a claim that the system handles these named situations does not rest on the twin matching a
  real store's averages. Session 2 reads whether the cells already carry expected responses
  (R-38).
- **Wrong if:** the scenario cells already state expected responses, or the rubric items cannot
  be checked mechanically from the decision record.

### INS-043 - A published benchmark recruits others and makes its author the reference

- **Lens / kind:** PURPOSE / principle
- **Says:** The same company published its benchmark. Others then found its flaws, model
  builders began testing against the domain, and the author became the point of reference for
  it. A benchmark kept private improves only its owner.
- **Sources:** SRC-SEQAI-10.
- **Grade:** E1.
- **Verdict:** PARK.
- **Lands:** One reading of Q-03 is that the proof harness is the product (T-004). Its published
  form would be a scenario set with planted issues (INS-042), a tuned control to beat, and the
  scoring rule. Parked until session 2 reports how separable the harness is from this twin
  (R-11) and the operator answers Q-03.
- **Wrong if:** the harness cannot be separated from the twin, or nobody else has a decision
  system of this kind to run against it. The second is a real risk (inferred): the audience for
  a quick-commerce decision benchmark may be very small.

### INS-044 - Validate the scorer: check that the objective ranks outcomes as a practitioner would

- **Lens / kind:** PROOF / technique
- **Says:** Before optimising against a score, check the score. One source runs a sample of
  completed tasks through the scorer and checks its ranking against an expert's. Chip designers
  rejected results on a convenient proxy until the cost function was rebuilt with them. A
  training company treats the blend of criteria in a reward as the company's own judgment, to
  be chosen deliberately. Another has an expert grade about a hundred cases to a rubric and
  trains a grader on them for the rest. Knowing what good looks like and writing it down so a
  system can optimise it are different skills, and the second is the bottleneck.
- **Sources:** SRC-SEQAI-14, SRC-SEQAI-18, SRC-SEQAI-19, SRC-SEQAI-22.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** The E5 headline is a difference of 4.40 units in one objective (read,
  `HANDOFF.md`). I have not read how that objective weighs stockouts, waste and cost, or where
  the weights came from; session 2 does (R-29). A cheap check follows: the operator ranks about
  ten replicate summaries from best to worst without seeing their scores, and the two rankings
  are compared. If they disagree, the objective is repaired before anything is tuned against
  it, including the re-run after PR #87. The limit: the operator is not a store operator, so
  this checks the objective against one informed judgment. A practitioner's ranking is what a
  named user (Q-01) would eventually supply.
- **Wrong if:** the weights come from a documented source a practitioner would accept, or the
  blind ranking agrees with the objective.

### INS-045 - Land on one workflow that already has a procedure and a measure, then expand

- **Lens / kind:** PURPOSE / principle
- **Says:** The first workflow to hand to agents is one that already has a written procedure
  and an agreed measure of quality, because both the baseline and the test exist. Prove it
  there, then move along the chain of neighbouring workflows. One founder spent five years
  without traction while reaching for the largest possible product, and found a market on
  committing to one use. The logistics operator served a single hospital for nine months before
  it could serve the others it had signed. The pull toward newer or larger work is often a way
  of avoiding the hard thing in front of you.
- **Sources:** SRC-SEQAI-16, SRC-SEQAI-17, SRC-SEQAI-13, SRC-SEQAI-23.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** ADR-052 already chose a slice: inventory reorder in one city. Replenishment has
  what this entry asks for, an incumbent procedure in the tuned control and a measure in the E5
  objective. So one candidate definition of finished is that this workflow beats its incumbent,
  by a named mechanism, before any other agent is deepened. Converting the other six agents'
  `execute()` is listed as remaining work (read, `CLAUDE.md`); the corpus's advice is to leave
  it listed. One uncomfortable observation belongs here. The sprint record shows three
  colour-system revisions (ADR-045, ADR-046, ADR-048) before the decision loop was closed
  (ADR-052) (read, `CLAUDE.md`). The corpus's reading of that pattern is that tractable work
  draws effort away from the work that decides the outcome. The operator decides (Q-07).
- **Wrong if:** the first user needs several functions together before the product is usable at
  all, or replenishment alone leaves no room to beat a tuned rule. The re-run after PR #87
  would show the second.

### INS-046 - Try the action in the twin before executing it

- **Lens / kind:** SYSTEM / technique
- **Says:** One lab's rule for granting authority: before an agent may act on something, its
  candidate actions are run forward in simulation and judged by what they disturb. Authority is
  extended action by action, as the forecasts hold.
- **Sources:** SRC-SEQAI-21.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** SYNAPSE has the parts: a standing world that accepts actions, and a consensus that
  chooses among proposals. The README says the orchestrator does not yet invoke Tier 4
  simulations against the twin (read, `README.md` line 14, tracked as C7), while tests named
  `test_twin_verification.py` and `test_selection_and_twin_consequence_property.py` exist
  (measured: file names only). Session 2 reads which is current (R-31). A lookahead is also a
  mechanism of uplift that a static rule lacks (INS-002): the system can run its own proposal
  and the incumbent's on the same forecast and act only when its own is better. One trap is
  specific to this project. A lookahead in the same twin that scores the arm forecasts
  perfectly, so a win earned that way overstates what happens when the world differs from the
  model (T-012, INS-041). The harness would need the lookahead's model and the scoring world to
  differ.
- **Wrong if:** consensus already does this, or the twin is too slow to run a lookahead inside
  a decision tier's time budget (R-30).

### INS-047 - Keep the proven simple controller live, with a small independent arbiter

- **Lens / kind:** SYSTEM / principle
- **Says:** The logistics operator flies two computers at once, and a small independent arbiter
  decides which one has control. A research lab proposes agents whose only job is to bound what
  the exploring agents may do. The shared pattern: the complex decision-maker is never the only
  one. A simpler, proven one runs beside it and takes over under stated conditions, and the
  part that chooses between them is small enough to verify.
- **Sources:** SRC-SEQAI-23, SRC-SEQAI-21.
- **Grade:** E1. The landing is own.
- **Verdict:** ADAPT.
- **Lands:** Since E5, SYNAPSE has a proven simple controller: the tuned control that beat the
  consensus arm. Today a low-confidence decision goes to a person (I-5). With no person present
  the natural fallback is the incumbent rule, and session 2 reads what executes in that case
  now (R-32). The design this points to: the consensus proposes, the rule proposes, and a small
  deterministic arbiter executes the consensus proposal only when it passes the guardrails and
  a lookahead (INS-046), and the rule's otherwise. Two consequences for the proof. Such a
  system can lose to the control only where the arbiter chose wrongly, and any uplift is
  attributable to the decisions where it chose consensus, which names the slice to report
  (INS-003, R-33).
- **Wrong if:** choosing between the two is as hard as the decision itself, so that the arbiter
  nearly always picks the rule. That would be a clean negative result about the consensus, and
  cheap to obtain.
