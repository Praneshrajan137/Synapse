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
| INS-002 | Name the mechanism of uplift before measuring it | PROOF | CREATE | own |
| INS-003 | Report by slice; the headline cell hides where a system wins and loses | PROOF | ADAPT | 2 |
| INS-004 | A gain inside noise is not a gain; hold cases out; keep the original as reference | PROOF | USE, present | 2 |
| INS-005 | Multi-agent failures sit at handoffs; test through the real envelope | SYSTEM | USE | 2 |
| INS-006 | Every external call: hard timeout, breaker, durable progress, trace | SYSTEM | USE, mostly present | 1 |
| INS-007 | One seam for every model call | SYSTEM | ADAPT | 2 |
| INS-008 | Keep probabilistic judgment in a small box | SYSTEM | USE, present | 1 |
| INS-009 | Grant autonomy by reversibility and blast radius, not confidence alone | SYSTEM | ADAPT | 4 |
| INS-010 | A shared, current world model lifts a planner more than a bigger model | SYSTEM | USE | 1 + 1 paper |
| INS-011 | Keep each run's full record; screen new decision logic by replay | PROOF | ADAPT | 1 |
| INS-012 | Verification is the constraint; plan sessions around it | WORKFLOW | USE | 3 |
| INS-013 | An agent needs a prod-like run it can drive and observe | WORKFLOW | ADAPT | 2 |
| INS-014 | Enforce by gate; trim prose rules newer models no longer need | WORKFLOW | ADAPT | 2 |
| INS-015 | Keep frontier models off bulk reading; write findings where the next run looks | WORKFLOW | ADAPT | 1 |
| INS-016 | Estimate from the work, not the spoken number; overruns are fat-tailed | WORKFLOW | USE | 1 + 2 studies |
| INS-017 | A sharp problem definition is the highest-leverage artifact | WORKFLOW | USE | 2 |
| INS-018 | Name the user, the workflow, and what happens after the demo | PURPOSE | USE | 2 |
| INS-019 | Fit the architecture and its footprint to the stage | OPS | ADAPT | 2 |
| INS-020 | Measure the share of work that changes the product | PROOF | ADAPT | 1 |
| INS-021 | For a narrow job, a small trained model can beat prompting a large one | OPS | PARK | 2 |

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
  information and compute as the consensus arm (R-03).
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
- **Grade:** own.
- **Verdict:** CREATE.
- **Lands:** Session 2 writes, for each mechanism, the scenario cell in `uplift/scenarios.py`
  that should show it and the arm that isolates it (R-03).
- **Wrong if:** no cell can be designed on the declared twin in which any of the three
  mechanisms should help. That would mean the architecture has no expected uplift on this twin.

### INS-003 - Report by slice; the headline cell hides where a system wins and loses

- **Lens / kind:** PROOF / technique
- **Says:** Measure hard cases, regression cases and subpopulations separately, so an overall
  figure cannot hide a loss in one group or a win in another. Users trust consistency across
  conditions more than a peak.
- **Sources:** SRC-POSTS-07, SRC-POSTS-08.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** The E5 headline is for the primary cell, unshocked (read, `HANDOFF.md`). That is the
  regime where a tuned static control should be strongest (inferred). Shock scenarios exist in
  the harness (measured: "shock" appears in 10 files under `uplift/`). Session 2 reads what the
  shocked cells showed, and whether they ran (R-02).
- **Wrong if:** every slice moves with the headline, so that slicing adds no information.

### INS-004 - A gain inside noise is not a gain; hold cases out; keep the original as reference

- **Lens / kind:** PROOF / technique
- **Says:** When a system is tuned against a score, accept a change only if the gain exceeds
  measured noise, test on cases kept out of tuning, change a few things at a time, and record
  failed ideas. Compare each version against the original as well as the previous one, or small
  steps add up to drift nobody chose.
- **Sources:** SRC-POSTS-01, SRC-POSTS-07.
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
  extracted facts explicit and validated, and let ordinary code apply the policy.
- **Sources:** SRC-POSTS-07.
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
  authors).
- **Grade:** E2 for the review pattern (reported by Anthropic, confirmed in secondary coverage).
- **Verdict:** ADAPT.
- **Lands:** Escalation is gated on confidence (I-5). No notion of reversibility is named in
  `orchestrator/` outside one test (measured by text search, which can miss a concept under
  another name). The change would be a reversibility class per `WorldAction` type that sets the
  escalation tier alongside confidence. A price change can be reversed; a supplier order or a
  markdown mostly cannot (inferred).
- **Wrong if:** in `audit_escalations`, override rates and loss per error do not differ between
  reversible and irreversible action types.

### INS-010 - A shared, current world model lifts a planner more than a bigger model

- **Lens / kind:** SYSTEM / fact and principle
- **Says:** Giving a planner an explicit model of the world, which checks whether each action is
  possible and tracks what is uncertain, raised a small model's task success far above a larger
  model working without one.
- **Sources:** SRC-POSTS-05; arXiv 2609.19315 (GAVEL).
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
- **Sources:** SRC-POSTS-03, SRC-POSTS-04, SRC-POSTS-08 (six or more posts).
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
- **Sources:** SRC-POSTS-03, SRC-POSTS-04.
- **Grade:** E1. The repository's deploy history agrees (read, `CLAUDE.md`): E-S12-01, E-S12-02
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
- **Sources:** SRC-POSTS-01, SRC-POSTS-04.
- **Grade:** E2 (Anthropic's prompt reduction is confirmed in secondary coverage; the exact
  sizes differ between sources). A post's claim that a built-in command flags outdated
  `CLAUDE.md` rules is E1 and unchecked.
- **Verdict:** ADAPT.
- **Lands:** `CLAUDE.md` is 68,257 characters; 49% is sprint history and 34% is error patterns,
  leaving 17% as rules (measured). It loads at the start of every session. A proposal for the
  operator (Q-04): keep rules and live error patterns there, move the history under `docs/`.
  The `doc_truth` gate pins numbers inside `CLAUDE.md`, so a move needs its pins updated in the
  same change.
- **Wrong if:** gate failures or repeated known mistakes rise after the trim. The removed text
  was then doing work.

### INS-015 - Keep frontier models off bulk reading; write findings where the next run looks

- **Lens / kind:** WORKFLOW / technique
- **Says:** Most agent spend goes on reading, much of it rediscovering what nobody recorded.
  Route bulk reads to a cheaper reader that returns only the answer, and enforce that with a
  hook. Record each finding where the next run will find it.
- **Sources:** SRC-POSTS-04.
- **Grade:** E3 for about 90% fewer tokens on bulk reads in Spotify's own tests. E0 for the
  post's wording that the whole bill fell 90%.
- **Verdict:** ADAPT.
- **Lands:** Session 2 faces documents of 100-500 KB (`tasks.md` is 498 KB, `GATE_SURFACE.md`
  214 KB; measured). It should use the derived commands the handoff already prescribes (the
  census) and targeted searches, not full reads in the main context. The same choice exists for
  the rest of this corpus (Q-05).
- **Wrong if:** on one sampled folder, a cheaper reader's cards miss decision-relevant content
  that a full read finds.

### INS-016 - Estimate from the work, not the spoken number; overruns are fat-tailed

- **Lens / kind:** WORKFLOW / fact
- **Says:** A number heard before estimating pulls the estimate toward it, and people deny the
  pull. Software overruns are not evenly spread: a minority of projects overrun hugely, so a
  flat buffer does not protect.
- **Sources:** SRC-POSTS-04; Flyvbjerg and Budzier (HBR 2011, arXiv 1304.0265); Jorgensen and
  Sjoberg on customer expectation.
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
- **Sources:** SRC-POSTS-08, SRC-POSTS-04.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** Session 3's definition of finished, written so that a test can fail it, comes
  before any implementation plan.
- **Wrong if:** session 3 ends with a plan and no failable definition of finished. The entry was
  then not applied.

### INS-018 - Name the user, the workflow, and what happens after the demo

- **Lens / kind:** PURPOSE / principle
- **Says:** Three questions decide whether something built is a product: who pays or depends on
  it, which daily workflow it sits inside, and what happens once the demonstration is over.
  What defends it is how hard it is to remove from real operations, and data only it holds.
- **Sources:** SRC-POSTS-08, SRC-POSTS-02.
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
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** The deployed stack is 21 containers on one 8-vCPU VM (read, `CLAUDE.md`
  E-S14-05), with Kafka, Neo4j, Redis, Feast and MLflow behind eight agents, for a system with no
  user yet. Session 3 decides the smallest footprint that demonstrates the claim, against the
  remaining cloud credit (Q-02, T-002).
- **Wrong if:** the full stack runs for the whole verification period inside the credit with
  margin, and every component is needed by the definition of finished.

### INS-020 - Measure the share of work that changes the product

- **Lens / kind:** PROOF / technique
- **Says:** When agents make pull requests cheap, counting them says nothing. Tag each change by
  type and watch what share is product work.
- **Sources:** SRC-POSTS-04.
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
- **Grade:** E1. One self-reported experiment and one vendor post.
- **Verdict:** PARK until session 3 allocates the Colab units.
- **Lands:** It supports spending the 200 Colab units on one or two narrow models trained inside
  the twin they will be scored in, which is also the standing direction "two agents deep beats
  eight shallow". It does not decide which models.
- **Wrong if:** INS-002 shows the expected uplift comes from coordination or adaptation and not
  from better forecasts. Training would then not be the first spend.
