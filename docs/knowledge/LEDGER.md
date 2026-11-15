# Insight ledger

One entry per insight that changes a decision for SYNAPSE. Vocabulary and grades are defined in
[`README.md`](README.md). Facts about the repository are marked measured (a command, run on
2026-11-13 at `origin/main` `d4f985c`), read (a file says so) or inferred.

"Present" under a verdict means the repository already does this; the entry then exists as an
audit item for session 2.

## Index

| ID | Insight | Lens | Verdict | Source docs |
|---|---|---|---|---|
| INS-001 | Many agents must beat a matched simple baseline to earn their cost | PROOF | USE | 9 + 1 paper |
| INS-002 | Name the mechanism of uplift before measuring it | PROOF | CREATE | own + 2 + 1 + 1 + 1 + 4 + 2 |
| INS-003 | Report by slice; the headline cell hides where a system wins and loses | PROOF | ADAPT | 20 |
| INS-004 | A gain inside noise is not a gain; hold cases out; keep the original as reference | PROOF | USE, present | 11 |
| INS-005 | Multi-agent failures sit at handoffs; test through the real envelope | SYSTEM | USE | 12 |
| INS-006 | Every external call: hard timeout, breaker, durable progress, trace | SYSTEM | USE, mostly present | 12 |
| INS-007 | One seam for every model call | SYSTEM | ADAPT | 20 |
| INS-008 | Keep probabilistic judgment in a small box | SYSTEM | USE, present | 29 |
| INS-009 | Grant autonomy by reversibility and blast radius, not confidence alone | SYSTEM | ADAPT | 39 |
| INS-010 | A shared, current world model lifts a planner more than a bigger model | SYSTEM | USE | 14 + 1 paper |
| INS-011 | Keep each run's full record; screen new decision logic by replay | PROOF | ADAPT | 12 |
| INS-012 | Verification is the constraint; plan sessions around it | WORKFLOW | USE | 37 |
| INS-013 | An agent needs a prod-like run it can drive and observe | WORKFLOW | ADAPT | 30 |
| INS-014 | Enforce by gate; trim prose rules newer models no longer need | WORKFLOW | ADAPT | 31 |
| INS-015 | Keep frontier models off bulk reading; write findings where the next run looks | WORKFLOW | ADAPT | 19 |
| INS-016 | Estimate from the work, not the spoken number; overruns are fat-tailed | WORKFLOW | USE | 6 + 2 studies |
| INS-017 | A sharp problem definition is the highest-leverage artifact | WORKFLOW | USE | 27 |
| INS-018 | Name the user, the workflow, and what happens after the demo | PURPOSE | USE | 61 |
| INS-019 | Fit the architecture and its footprint to the stage | OPS | ADAPT | 20 |
| INS-020 | Measure the share of work that changes the product | PROOF | ADAPT | 27 |
| INS-021 | For a narrow job, a small trained model can beat prompting a large one | OPS | PARK | 28 |
| INS-022 | Autonomy is earned on a trust curve: shadow first, promote on a measured record | SYSTEM | ADAPT | 30 |
| INS-023 | Many agents pay as breadth plus adversarial checking, reduced by ordinary code | SYSTEM | USE | 11 |
| INS-024 | Before trusting an aggregate, walk one decision against its expected trace | PROOF | USE | 17 |
| INS-025 | Give agents a map from capability to code to proof | WORKFLOW | ADAPT | 20 |
| INS-026 | Widen agent fan-out only as fast as verification allows | WORKFLOW | USE, present | 7 |
| INS-027 | Least privilege per agent: an out-of-function action is impossible, not discouraged | SYSTEM | ADAPT | 27 |
| INS-028 | Tool, skill or agent: a separate agent needs a reason | SYSTEM | ADAPT | 10 |
| INS-029 | When execution is frictionless, build the dissent in | WORKFLOW | USE | 18 |
| INS-030 | Deletion is an experiment: remove a part, rerun the fixed eval, keep it if the score holds | SYSTEM | ADAPT | 34 |
| INS-031 | A twin earns belief when fitted to real history and tested across regimes | DOMAIN | ADAPT | 17 |
| INS-032 | Every human correction is a label; compile standards from past actions | SYSTEM | ADAPT | 22 |
| INS-033 | An eval that cannot fail measures nothing | PROOF | USE, partly present | 42 |
| INS-034 | Proof of work: checkable evidence, and the process shown is the process that ran | PROOF | USE, present | 24 |
| INS-035 | Dogfood it: operate the twin store yourself with SYNAPSE advising | PURPOSE | CREATE | own + 3 + 5 + 4 + 2 + 2 + 6 + 4 + 2 + 4 + 1 + 3 + 3 |
| INS-036 | Make re-verification cheap: address expensive results by content | PROOF | ADAPT | 6 |
| INS-037 | An agent's report of its own obstruction is telemetry: aggregate it, fix the top cause | SYSTEM | ADAPT | 11 |
| INS-038 | An approver is not an operator: show the plan and let the person change any part | PURPOSE | USE, partly present | 40 |
| INS-039 | Reach users through the system they already run | PURPOSE | ADAPT | 33 |
| INS-040 | Spend the strong model at design time; ship the simple artefact it finds | OPS | CREATE | own + 2 + 2 + 1 + 3 + 1 + 1 + 3 |
| INS-041 | A learner exploits whatever earns reward, including the simulator's mistakes | PROOF | USE | 21 |
| INS-042 | Rubric first: plant the issue, then build the world around it | PROOF | ADAPT | 8 |
| INS-043 | A published benchmark recruits others and makes its author the reference | PURPOSE | PARK | 6 |
| INS-044 | Validate the scorer: check that the objective ranks outcomes as a practitioner would | PROOF | USE | 24 |
| INS-045 | Land on one workflow that already has a procedure and a measure, then expand | PURPOSE | USE | 35 |
| INS-046 | Try the action in the twin before executing it | SYSTEM | ADAPT | 8 |
| INS-047 | Keep the proven simple controller live, with a small independent arbiter | SYSTEM | ADAPT | 19 |
| INS-048 | Passable is now free; quality is what a person removes and refuses to ship | WORKFLOW | ADAPT | 24 |
| INS-049 | Simulation throughput is the budget for proof and for training | OPS | ADAPT | own + 3 + 1 + 1 + 1 + 1 + 5 + 1 + 1 + 2 + 1 |
| INS-050 | Check the outcome, not only the parts; a result that is too good is a fault until shown otherwise | PROOF | USE | 10 |
| INS-051 | Make a run a pure function of its seed | PROOF | USE, partly present | 4 |
| INS-052 | No time machine: judge a decision on what had arrived by then | PROOF | USE | 2 |
| INS-053 | Design the workload: random operations never reach the states where systems break | PROOF | ADAPT | 9 |
| INS-054 | Where units share a resource, compare policies by switching over time or place | PROOF | ADAPT | 1 |
| INS-055 | At a stockout the moves are reallocate, substitute or expedite; the twin offers one | DOMAIN | ADAPT | 6 |
| INS-056 | Judge the system by what reaches the customer, not by its own activity | PURPOSE | ADAPT | 20 |
| INS-057 | Start a learned policy from the incumbent: imitate the tuned rule, then improve it | SYSTEM | CREATE | own + 1 |
| INS-058 | Automating a loop removes the person who was quietly correcting it | DOMAIN | ADAPT | 7 |
| INS-059 | Pull exists only where every existing option fails: find where the tuned rule breaks | PURPOSE | ADAPT | 11 |
| INS-060 | Demand is concentrated in a few items; a twin with even demand hides where a policy wins | DOMAIN | ADAPT | own + 3 |

## Entries

### INS-001 - Many agents must beat a matched simple baseline to earn their cost

- **Lens / kind:** PROOF / warning
- **Says:** Error compounds across steps, and each agent hands on a confident answer with its
  uncertainty removed. Under matched budgets a single agent often does as well as a team. Teams
  pay off where subtasks are independent or where each step can be checked at once.
- **Sources:** SRC-POSTS-06; arXiv 2512.08296 (Kim et al.).
  Also SRC-PRAG-02: simulation and stochastic optimisation are the established practice in
  supply chains, the baseline a new approach must beat.
  Also SRC-SPC-07: a generated video kept no users for being generated; a decision is worth no
  more for having been debated.
  Also SRC-LENNY-12, SRC-LENNY-17, SRC-LENNY-23: an experiment graduates only if ten times
  better than the existing way; a much better product does not sell to someone who is not
  blocked.
  Also SRC-A16Z-19: published self-improvement methods failed on real problems; the simpler loop
  scaled.
  Also SRC-RAIN-06, SRC-RAIN-07: many small improvements never make one leap; better but not ten
  times better lost.
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
  Also SRC-ENG-12: a forecast is worth what it lets someone do in time; by analogy (own), its
  horizon has to exceed the supplier's lead time.
  Also SRC-SPC-03: write down your own guess and its alternatives before reading the model's
  answer.
  Also SRC-YCG-08: ten predictions written each year and checked a year later.
  Also SRC-LENNY-05, SRC-LENNY-15, SRC-LENNY-16, SRC-LENNY-19: state the evidence that would
  confirm or refute before building; predictions written down though most will be wrong.
  Also SRC-RAIN-02, SRC-RAIN-10: an MVP tests a stated hypothesis; no trusted measure hid fit
  for six months.
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
  Also SRC-YCAI-05: a model is chosen per task on accuracy, latency and cost together.
  Also SRC-PRAG-12: captured cases indexed by line of business, country and payment type,
  replayed across their combinations.
  Also SRC-ENG-12: users judge a working tool by its worst line.
  Also SRC-SPC-05: new sign-ups, the most active couriers and the edge of the service area show
  where quality drops.
  Also SRC-YCG-02: the gain sat in transactions too small for any person to review.
  Also SRC-SEQG-07: most revenue comes from a small segment; read results by that segment.
  Also SRC-LENNY-22, SRC-LENNY-23: objections grouped and weighed by survey; a cohort analysis
  found the one segment that stayed.
  Also SRC-A16Z-14: automation's gain was capacity for the cases a firm used to refuse.
  Also SRC-RAIN-03, SRC-RAIN-08: a narrow segment's love is not fit across a market.
  Also SRC-NEON-04, SRC-NEON-17: aggregate churn hid that larger customers stayed; ideal
  customer from conversion per stage.
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
  Also SRC-JANE-03: a structure sold as the fix made the workload slower, and only measurement
  showed it.
  Also SRC-ENG-07: one specimen is not enough; understanding needs many and their variation.
  Also SRC-A16Z-15, SRC-A16Z-19: a model topped public benchmarks and fell short on held-out
  ones; count every failed run.
  Also SRC-RAIN-06, SRC-RAIN-08: a metric hunted to excuse a result; a correct decision can
  still lose one draw.
  Also SRC-NEON-10: seven trades in ten won and the three losses outweighed the gains.
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
  Also SRC-YCAI-11: draw the data flow before coding; an error in an envelope shows on the
  diagram.
  Also SRC-PRAG-10: model the domain so that an unhandled case is a compile error.
  Also SRC-ENG-04: test at the boundaries and through integration, not with generated tests that
  assert nothing.
  Also SRC-A16Z-22: agents talk without a secure typed protocol.
  Also SRC-NEON-04: a change to a shared definition must reach every agent at once.
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
  Also SRC-YCAI-02, SRC-YCAI-10: testing before release does not predict production; agent state
  kept in a central database with disposable sandboxes.
  Also SRC-PRAG-08, SRC-PRAG-09: every resource pool runs out; idempotency keys and retries with
  backoff and random spread; one broadcast makes every recipient act at once.
  Also SRC-ENG-04, SRC-ENG-06, SRC-ENG-11: agents calling services at machine speed run up a
  bill without a hard stop; a gateway reported failures while banks debited the customers; every
  agent run is a durable recorded session.
  Also SRC-A16Z-07: an agent chaining many calls stalls on the rare slow one.
  Also SRC-NEON-09: a two-nines service cannot underpin a four-nines controller.
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
  Also SRC-YCAI-05, SRC-YCAI-07: one routing layer chooses among providers; different models
  lead on different sub-tasks.
  Also SRC-JANE-01: one internal gateway for every model call: provider hidden, credentials
  held, rates limited, calls logged.
  Also SRC-PRAG-12: one gateway for every model call, with safety models on input and output.
  Also SRC-ENG-05, SRC-ENG-11: retrieval kept separate from any model provider; an agent's model
  swapped on a branch.
  Also SRC-SPC-10: customers want to switch model providers freely.
  Also SRC-YCG-10, SRC-YCG-15: an evaluation suite chooses the model by quality and cost; a
  project stalled when its one model provider changed terms.
  Also SRC-A16Z-03, SRC-A16Z-12, SRC-A16Z-15, SRC-A16Z-22: caching, routing and small models
  behind one layer; cost per task, not per token.
  Also SRC-RAIN-01, SRC-RAIN-09: sensing, sense-making and action separated so models can be
  swapped; route to the smallest model.
  Also SRC-NEON-15, SRC-NEON-16: daily model bake-offs; routing across providers with automated
  judges.
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
  Also SRC-YCAI-03, SRC-YCAI-06: deterministic analysis confirms the anomaly before a model
  judges it; judgment in procedure files, exact computation in code.
  Also SRC-JANE-01: a compiler is deterministic and sound; a model is neither.
  Also SRC-PRAG-08: agents kept inside module boundaries, with people holding the architecture.
  Also SRC-ENG-11, SRC-ENG-13: an action defined once, with everything it takes in the real
  systems; deciding the boundaries is the work.
  Also SRC-GOOG-01: an on-device scam check applies rules set by the banks themselves.
  Also SRC-YCG-02, SRC-YCG-08, SRC-YCG-14, SRC-YCG-24, SRC-YCG-25: a deterministic harness
  around banking agents; exact answers need a check; intermediate representations let an onboard
  check verify each output.
  Also SRC-SEQG-06: capability is jagged where no automatic checker exists, as in everyday
  logistics.
  Also SRC-LENNY-22: authoritative facts added to generated answers raised trust.
  Also SRC-A16Z-06, SRC-A16Z-11, SRC-A16Z-13, SRC-A16Z-18, SRC-A16Z-24: never infer what a query
  can answer; narrow what the model decides.
  Also SRC-RAIN-01, SRC-RAIN-09: a decade of edge cases is the defence; buyers expect the same
  behaviour every time.
  Also SRC-NEON-08, SRC-NEON-09, SRC-NEON-14, SRC-NEON-16: assemble approved assets;
  deterministic controllers; rules paired with models.
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
  Also SRC-YCAI-03, SRC-YCAI-10: who is liable when an autonomous change causes damage is
  unsettled; database writes go only through a plan a person reviews.
  Also SRC-JANE-01, SRC-JANE-08: a request outside the allowed list is run, refused or sent to a
  person; an error budget is the wrong tool where one action can be ruinous.
  Also SRC-PRAG-03, SRC-PRAG-05, SRC-PRAG-08, SRC-PRAG-09, SRC-PRAG-12: a change to state cannot
  be rolled back, only rolled forward; who pays for an assistant's irreversible mistake is
  unsettled; carry on or stop is a business decision per function; a purge run against a table
  that was live; every merge needs a person where outages cost money, with automatic merging
  only for kinds of change shown safe on history.
  Also SRC-GOOG-01, SRC-GOOG-02: an agent stops before a payment for the person to authorise; a
  classifier lets safe actions through and stops only the risky ones.
  Also SRC-SPC-05, SRC-SPC-08: a mistake in physical operations is paid for directly; physical
  tasks tolerate few errors.
  Also SRC-YCG-02, SRC-YCG-15, SRC-YCG-17: wider permissions raise the cost of a mistake;
  generated code reviewed by risk; delegation limited by trust.
  Also SRC-SEQG-03, SRC-SEQG-05: a precise tool before autonomy; approve the routine
  automatically and bring the risky to a person.
  Also SRC-LENNY-02, SRC-LENNY-04, SRC-LENNY-07: low-risk fixes ship by themselves and high-risk
  ones go to a person; who may change code is set by the codebase's risk.
  Also SRC-A16Z-09, SRC-A16Z-16, SRC-A16Z-17, SRC-A16Z-20: bold where reversible, ask before
  binding; gates for irreversible steps.
  Also SRC-RAIN-09: liability, not only capability, keeps a person's sign-off.
  Also SRC-NEON-07, SRC-NEON-09, SRC-NEON-15: show a change's reach; high-risk changes with a
  person; back office runs alone.
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
  Also SRC-YCAI-12: the raw record of a project, given to the agent in one file.
  Also SRC-JANE-02, SRC-JANE-08: success depended on whether every needed fact was present, not
  on wording; stale input that is not flagged is the worst input.
  Also SRC-SEQG-05: a model kept out of the context where the problem lives cannot solve it.
  Also SRC-A16Z-10, SRC-A16Z-13, SRC-A16Z-14: no gain in reasoning supplies missing context; the
  data that matters is local.
  Also SRC-NEON-04, SRC-NEON-08, SRC-NEON-16: knowledge, expertise and norms; a schema map for
  the model; context in internal systems.
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
  Also SRC-PRAG-09, SRC-PRAG-12: a recorder turns a real workflow into a replayable test;
  production traffic captured and replayed against a candidate change.
  Also SRC-YCG-02, SRC-YCG-18, SRC-YCG-21, SRC-YCG-26: every trace scanned; if it was not
  recorded it did not happen; years of written decisions searchable; one database agents can
  query.
  Also SRC-LENNY-03: a failed idea kept in an evaluation harness and re-scored when models
  changed.
  Also SRC-A16Z-07, SRC-A16Z-10, SRC-A16Z-19: an append-only log re-read when a definition
  changes; replay checks a learned change.
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
  Also SRC-YCAI-01, SRC-YCAI-05, SRC-YCAI-11, SRC-YCAI-13: core code read line by line and the
  periphery left to agents; where answers must be exact a person still audits everything; code
  produced fast must be reviewed as fast; model-written code has no preference for brevity.
  Also SRC-JANE-01, SRC-JANE-09, SRC-JANE-10: model-written code is wrong in ways no person
  would write and costs as much to review as to write; reviewing a finished piece is harder than
  building it; faster generation does not help while merging waits on a person.
  Also SRC-PRAG-02, SRC-PRAG-03, SRC-PRAG-08, SRC-PRAG-09: review turns to intent; with more
  code the pipeline matters for what it refuses; approving what one has not understood gives up
  the theory of the system; a model advised parallelising work that was not on the critical
  path.
  Also SRC-ENG-01, SRC-ENG-04, SRC-ENG-07, SRC-ENG-13: automating most of a workflow leaves
  review as the limit; generated replacements move cost into maintenance; ideas became cheap to
  test and checking did not; every model-written line read before it ships.
  Also SRC-GOOG-02: only the code a task needs is committed; changes go up as draft pull
  requests for review.
  Also SRC-SPC-01, SRC-SPC-04: a generated patch is tested in its environment and reviewed; a
  large rewrite was carried by its test suite.
  Also SRC-YCG-05, SRC-YCG-08, SRC-YCG-15: a hard goal plus a way to verify along the way; old
  code and tests as the exact specification.
  Also SRC-SEQG-01, SRC-SEQG-05, SRC-SEQG-06: late testing was the drag; a person accountable
  for every merge; design judgment stays with the person.
  Also SRC-LENNY-21: once coding was fast, review, testing and coordination set the pace.
  Also SRC-A16Z-07, SRC-A16Z-12: the binding constraint moves; validation, not generation, is
  the limit.
  Also SRC-NEON-07, SRC-NEON-18: review is the bottleneck; lines shipped without time to review.
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
  Also SRC-YCAI-02, SRC-YCAI-09, SRC-YCAI-12: logs are what a debugging agent reads natively;
  review the working thing, not a presentation of it; throwaway instruments built for one tuning
  job; a plain-text surface for agents.
  Also SRC-JANE-06: agents work from late, batched feedback; feedback on each step changes what
  they can do.
  Also SRC-PRAG-03, SRC-PRAG-08, SRC-PRAG-12: a short-lived environment per change; production
  is the only truth; agents work on a platform of identical environments, staging and replay.
  Also SRC-ENG-09: give the agent the tests and the errors instead of acting as a go-between.
  Also SRC-GOOG-02: the agent tested its own work in a browser unasked; bots fix failing builds
  until the checks pass.
  Also SRC-YCG-03, SRC-YCG-05, SRC-YCG-11, SRC-YCG-21: an in-house shop and test stand; rewrites
  checked against tests and screenshots; iteration rate set by infrastructure; seconds to a
  first result.
  Also SRC-SEQG-01, SRC-SEQG-06: environment setup slowed every connector; infrastructure for
  agents exposes state and actions.
  Also SRC-LENNY-11, SRC-LENNY-21, SRC-LENNY-22, SRC-LENNY-25: agents drive the product through
  test journeys each release; production behaviour differs from the laboratory.
  Also SRC-RAIN-09: demos on clean data lie; production on messy data breaks.
  Also SRC-NEON-06: production problems matter more than demos.
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
  Also SRC-YCAI-05, SRC-YCAI-06, SRC-YCAI-07, SRC-YCAI-11: a capability threshold retires
  earlier work; every finished job written down as a reusable procedure; ask whether the next
  model release helps or threatens you; use an existing harness and write procedures.
  Also SRC-JANE-01, SRC-JANE-05: one firm retired its own context format when a common standard
  arrived, and rebuilds its methods about every five years.
  Also SRC-PRAG-02, SRC-PRAG-06: the harness shrinks as models improve; recurring defects turned
  into permanent lint rules.
  Also SRC-SPC-03, SRC-SPC-04: documents above the code decay; scaffolding built for an older
  model is deleted once a newer one does without it.
  Also SRC-YCG-05, SRC-YCG-07: over 80 per cent of a system prompt cut for a new model; problems
  the next model would fix were skipped.
  Also SRC-SEQG-04: culture is the behaviour enforced, not the values stated.
  Also SRC-LENNY-14, SRC-LENNY-17, SRC-LENNY-25: rules built into tools are followed where
  documentation is not; process used in place of thinking.
  Also SRC-RAIN-05: a promise must rest on structure that outlives one person's intentions.
  Also SRC-NEON-15: written procedures become the company's operating system.
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
  Also SRC-YCAI-04, SRC-YCAI-06, SRC-YCAI-10: routine operational data does not go to a remote
  frontier model; owned context outlasts any model; data is processed in a code workspace
  outside the context.
  Also SRC-JANE-01, SRC-JANE-02, SRC-JANE-06: an agent rediscovers the workspace on every run
  unless its setup is computed in advance; after two failures clear the context and restate the
  task; agents forget everything between sessions.
  Also SRC-PRAG-05, SRC-PRAG-12: work that is not urgent goes to batch processing; tools exposed
  as short command-line programs to keep descriptions out of the context.
  Also SRC-ENG-01, SRC-ENG-06: companies moved to accounting for every token and routing routine
  work to small models; a decision has to cost less than the margin on what it decides.
  Also SRC-SPC-04: the model searches for and reads the files it needs instead of being handed a
  huge context.
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
  Also SRC-JANE-04: begin from the plain trend; an elaborate model can dress up what its author
  already believed.
  Also SRC-YCG-08: a special-purpose chip began with arithmetic on the back of an envelope.
  Also SRC-NEON-16: a fixed date, or a date by which the date will be known.
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
  Also SRC-YCAI-02, SRC-YCAI-09: the specification is the asset a person reviews; a redesign
  that began by asking what the page is for.
  Also SRC-JANE-02, SRC-JANE-09: one missing fact in a task statement meant failure, whatever
  the wording; state a goal as what someone will be able to do afterwards.
  Also SRC-PRAG-02, SRC-PRAG-04, SRC-PRAG-08, SRC-PRAG-10: review turns to intent; long question
  sequences tire people into the defaults; state what good looks like before handing work to
  agents; agree what the words mean before building.
  Also SRC-ENG-02, SRC-ENG-12: scope, owner and review rhythm set at the start; choosing the
  problem is the hard part.
  Also SRC-GOOG-02: ask the broad architectural question before asking for code.
  Also SRC-SPC-04, SRC-SPC-05, SRC-SPC-10: the agent interviews the person first; the one or two
  problems that matter now are written down.
  Also SRC-YCG-08, SRC-YCG-10: with agents writing the code, specifying matters more; one
  written product manifesto replaced feature voting.
  Also SRC-SEQG-01: find the single largest bottleneck and give it most of the attention.
  Also SRC-LENNY-20: a product's value stated in one sentence tied to a daily measure.
  Also SRC-A16Z-11, SRC-A16Z-15: a measure fixed in code ends arguments; a firm becomes its
  evaluation.
  Also SRC-NEON-16: problem, root cause, solution, one owner, a date.
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
  Also SRC-YCAI-02, SRC-YCAI-04, SRC-YCAI-05, SRC-YCAI-07, SRC-LOOSE-01: build where you have
  experience, or ask practitioners until you do; sell under a category the buyer already has a
  budget for; sell to the practitioner who can judge the output, not the novice avoiding one;
  the traces of expert practice are the data nobody has.
  Also SRC-JANE-08: engineers know the business well enough to act on a practitioner's remark in
  seconds.
  Also SRC-PRAG-01, SRC-PRAG-05, SRC-PRAG-11: agents amplify domain knowledge and do not supply
  it; a general assistant may take a specialised product's job; domain rules and unit economics
  stay hard.
  Also SRC-ENG-09, SRC-ENG-10: experts direct agents well and novices do not; outsiders who
  build before reading what a field knows repeat its solved problems.
  Also SRC-GOOG-01: features adopted when described by their benefit, not labelled as AI.
  Also SRC-SPC-02, SRC-SPC-06, SRC-SPC-10, SRC-SPC-11, SRC-SPC-13: ask for the story of the last
  occurrence, not for wishes; stated and revealed preferences differ; working directly with
  users sold the product where intermediaries failed.
  Also SRC-YCG-02, SRC-YCG-06, SRC-YCG-10, SRC-YCG-15, SRC-YCG-21, SRC-YCG-23: buyers judge an
  agent against the labour it replaces; never delegate talking to customers; which kind of user;
  describe it by what it replaces.
  Also SRC-SEQG-07: open conversation gives consistent answers where repeated surveys do not.
  Also SRC-LENNY-01, SRC-LENNY-03, SRC-LENNY-06, SRC-LENNY-11, SRC-LENNY-16, SRC-LENNY-17, SRC-
  LENNY-22, SRC-LENNY-23: take the person back to the moment of the decision; pull belongs to a
  person; viability includes who pays and who carries liability.
  Also SRC-A16Z-02, SRC-A16Z-04, SRC-A16Z-10, SRC-A16Z-13, SRC-A16Z-14, SRC-A16Z-16: AI bought
  against the labour budget; ask what the user wants; adoption is not use.
  Also SRC-RAIN-02, SRC-RAIN-06, SRC-RAIN-08, SRC-RAIN-09: understand context rather than rank
  requests; knowledge lives in operators' heads.
  Also SRC-NEON-01, SRC-NEON-02, SRC-NEON-03, SRC-NEON-04, SRC-NEON-05, SRC-NEON-12, SRC-
  NEON-14: strangers not friends; time on the floor; the buyer and the user; urgency.
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
  Also SRC-JANE-09: bring in a tool when a problem calls for it, not the tool first and the
  problem afterwards.
  Also SRC-PRAG-01, SRC-PRAG-03, SRC-PRAG-06, SRC-PRAG-08, SRC-PRAG-10: put a hard guarantee in
  one layer once; follow the principle, not the label; long-term investment before users is a
  mistake; distribution is a last resort for one team; code before fit should be easy to throw
  away.
  Also SRC-ENG-03, SRC-ENG-10, SRC-ENG-13: one stack for every country, a new one by
  configuration; money spent in tranches against technical milestones; most requests refused.
  Also SRC-SPC-01, SRC-SPC-09, SRC-SPC-13: every dependency is a stream of patches; software
  decays unless maintained; build a part only when bought ones cannot do the job.
  Also SRC-YCG-15, SRC-YCG-21, SRC-YCG-25: 9,500 options could not be tested; built on an
  established database nobody owns; a technique adopted only if it also simplifies.
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
  Also SRC-YCAI-11: volume of output is not the measure; generated code is a maintenance load.
  Also SRC-JANE-02, SRC-JANE-04: self-reported gains set against controlled studies that found
  experienced engineers slowed on complex tasks; another speaker reports measured gains.
  Also SRC-PRAG-06, SRC-PRAG-12: measured gains of a fifth to a third against claims of tenfold,
  and one report of more code and more outages with flat features; changes classified by kind,
  with feature delivery tracked.
  Also SRC-ENG-01, SRC-ENG-03, SRC-ENG-13: no clear gains yet outside technology; engineering
  reported 30% faster; models led to more work, not more leisure.
  Also SRC-SPC-04: more code shipped is not more business.
  Also SRC-SEQG-01: the code was fast; documents, setup and late tests took the time.
  Also SRC-LENNY-04, SRC-LENNY-05, SRC-LENNY-06, SRC-LENNY-26: count deployed changes, not
  written ones; pull requests tripled and revenue did not; views without paying customers.
  Also SRC-A16Z-02, SRC-A16Z-03, SRC-A16Z-05, SRC-A16Z-23: few deployments are measured over
  time; most effort went to undifferentiated infrastructure.
  Also SRC-RAIN-02, SRC-RAIN-03: a strict definition of a user; retention on paper with little
  real use.
  Also SRC-NEON-03, SRC-NEON-12, SRC-NEON-19: problems resolved, not logins; signed is not
  running; realised, not paper.
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
  Also SRC-YCAI-03, SRC-YCAI-10, SRC-YCAI-13: a small model trained on an installed base's data
  beat a general one, given that data; open-weight models trail the frontier by months; most
  everyday queries can be served locally, as reported.
  Also SRC-JANE-02: run a cheap baseline with no training before training anything; in one case
  a trained small model stayed far below a general one.
  Also SRC-ENG-13: open-weight models self-hosted for work on private data.
  Also SRC-SPC-07, SRC-SPC-08, SRC-SPC-10: narrow, high-volume tasks move to small post-trained
  models; an agent on a frontier model cost about 600 dollars a day until moved to an open one.
  Also SRC-YCG-16: models of a few million parameters beat general ones on structured puzzles.
  Also SRC-LENNY-02: work with bounded upside runs on cheap tuned models.
  Also SRC-A16Z-03, SRC-A16Z-05, SRC-A16Z-07, SRC-A16Z-12, SRC-A16Z-22: distilled small models
  beat frontier ones on their task; a forked model falls behind.
  Also SRC-RAIN-09: send each request to the smallest model that will do.
  Also SRC-NEON-09: local causal and graph models in place of a language model.
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
  Also SRC-YCAI-03, SRC-YCAI-09: where a miss is costly an unfinished product spends trust that
  does not return; one engineer supervising several plants; a quality floor before anything
  meets the public.
  Also SRC-PRAG-03, SRC-PRAG-04, SRC-PRAG-05, SRC-PRAG-09: deploying and releasing separated by
  a switch; trust rests on a record, not an impression; trust measured by what users hand over;
  shadow reads compared before cutover.
  Also SRC-ENG-02, SRC-ENG-09, SRC-ENG-11: stay in the detail until the standard is a habit,
  then audit periodically; autonomy granted as competence is shown; workflows move from
  assisting to acting, with failures escalated.
  Also SRC-SEQG-03: build a precise, reliable tool first, then cross into autonomy.
  Also SRC-LENNY-05, SRC-LENNY-07, SRC-LENNY-09, SRC-LENNY-11, SRC-LENNY-12: probe, experiment
  or promise; usefulness jumps at a reliability threshold; a task finished completely differs
  from one 90 per cent done.
  Also SRC-A16Z-16, SRC-A16Z-17: 97 against 99 per cent per step is distrust against use; one
  crossed line loses trust.
  Also SRC-NEON-09, SRC-NEON-15, SRC-NEON-17: recommendations before actions; a small stake to
  watch before committing.
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
  Also SRC-YCAI-02, SRC-YCAI-11, SRC-YCAI-12: the writer of the code cannot certify it; a second
  model reviews the first; many variants generated and chosen among.
  Also SRC-JANE-01, SRC-JANE-03: specialised reviewer agents go over a change before a person
  does; coordination has a fixed cost per hand-off, so it pays only on large units of work (the
  analogy is own).
  Also SRC-PRAG-01: one model's work reviewed adversarially by a different model.
  Also SRC-ENG-02: independent objectives need a binding arbiter or they pull a decision apart
  (own analogy).
  Also SRC-YCG-08: several attempts in parallel, with an evaluator pruning the bad ones.
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
  Also SRC-YCAI-04, SRC-YCAI-09, SRC-YCAI-11, SRC-LOOSE-01: read raw records, not summaries;
  walk the essential journeys end to end; draw the flow before coding; when results stall, sort
  the errors into ranked buckets before changing the model.
  Also SRC-JANE-11: hand over a flawed dataset and watch whether assumptions are checked before
  any code is written.
  Also SRC-PRAG-04, SRC-PRAG-09: a hand sketch carries a spatial idea fastest; the whole request
  path printed and traced by hand.
  Also SRC-ENG-07: a map of connections shows what cannot have influenced an outcome (own
  analogy).
  Also SRC-LENNY-14: an editor goes through the whole journey as a user after the build.
  Also SRC-A16Z-11: every paid sign-up read by hand before aggregates.
  Also SRC-RAIN-02: one user's clear difficulty is enough to fix the design.
  Also SRC-NEON-16: a chief executive reads single complaints.
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
  Also SRC-YCAI-06: procedures written down as reusable skill files.
  Also SRC-JANE-01, SRC-JANE-10: setup computed in advance cut one task from ten minutes to
  thirty seconds; agents do worse in a tangled codebase.
  Also SRC-PRAG-08, SRC-PRAG-11, SRC-PRAG-12: software is a theory held by its developers; tasks
  made machine-readable for agents; agent tools generated from service schemas.
  Also SRC-GOOG-02: a repeated agent job written down as a versioned script.
  Also SRC-YCG-08: skills and constraints keep agents on well-lit paths.
  Also SRC-SEQG-06: agents need sensors and actuators, not instructions written for people.
  Also SRC-LENNY-14, SRC-LENNY-21: a tool with templates in the workflow is followed; coding
  agents need a clean, structured codebase.
  Also SRC-NEON-15: written procedures as the operating system.
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
  Also SRC-JANE-06: a swarm of uncoordinated agents on one repository spent heavily on resolving
  each other's small conflicts.
  Also SRC-PRAG-04: one developer with many private agents is a team with no shared
  understanding.
  Also SRC-GOOG-02: fixed phases instead of ad-hoc sub-agents that differ every run.
  Also SRC-LENNY-18: delegating to an agent keeps the oversight with the person.
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
  Also SRC-YCAI-10: a fleet's core of three tools, with data access read-only by default.
  Also SRC-JANE-01, SRC-JANE-05, SRC-JANE-06, SRC-JANE-08, SRC-JANE-11: each agent has its own
  identity and every permitted call is listed; one unguarded command reset every job on a shared
  cluster; hand an agent a narrowed capability; safeguards written by different people in
  different systems; unit and sign conventions are where a routine action turns ruinous.
  Also SRC-PRAG-05, SRC-PRAG-09, SRC-PRAG-10: a separate watcher checks each intended action;
  limits written into the product keep the worst case finite; a dependency runs with the full
  authority of its importer.
  Also SRC-ENG-05: adversarial input filtered at retrieval, at the model and at the point of
  action.
  Also SRC-GOOG-01: an agent confined to an isolated window it cannot leave.
  Also SRC-SPC-01: agent protocols and agent-to-agent traffic were built without authentication.
  Also SRC-YCG-17, SRC-YCG-23: identities for non-human actors; every outbound request checked
  at the network boundary.
  Also SRC-LENNY-07: supervisor models catch unauthorised high-risk actions.
  Also SRC-A16Z-07, SRC-A16Z-16, SRC-A16Z-20: permissions per subtask, allowlists; an agent
  deleted a production database with no separation.
  Also SRC-NEON-04: norms as hard limits, such as refunds above a set amount.
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
  Also SRC-YCAI-11: do not build a custom agent loop where an existing harness will do.
  Also SRC-YCG-26: a registry of 350 tools checked for duplicates and overlaps.
  Also SRC-LENNY-07, SRC-LENNY-19: teams of agents shrink to one as models improve; many agents
  are managed through one chief-of-staff agent.
  Also SRC-RAIN-02: a product that shows its makers' organisation chart.
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
  Also SRC-YCAI-11: a second model set to find fault with the first.
  Also SRC-JANE-01, SRC-JANE-04: writing by hand used to challenge the design, and that step is
  gone; models tell evaluators what they want to hear.
  Also SRC-ENG-02, SRC-ENG-03: the leader speaks last and gives the team time to beat the
  leader's idea; a founder who distrusts his own product instinct; opposing agents argue to
  expose what is true.
  Also SRC-SPC-03: form your own answer before reading the model's.
  Also SRC-YCG-06, SRC-YCG-13: leaders write their own documents so as not to hand their
  thinking to a model.
  Also SRC-SEQG-06: thinking can be handed off, understanding cannot; agents attack the deployed
  result.
  Also SRC-LENNY-01, SRC-LENNY-06: writing that thinks stays with the person; outsourcing the
  problem-solving loses the learning.
  Also SRC-A16Z-11, SRC-A16Z-15, SRC-A16Z-19: an evaluator with no stake; an engineer whose job
  is to break results.
  Also SRC-RAIN-05: learning cannot be handed off; agent research leaves no understanding.
  Also SRC-NEON-07: an automated reviewer that agents iterate against.
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
  Also SRC-YCAI-06: a library nobody prunes becomes a dump.
  Also SRC-JANE-08: dormant code woken by a reused flag brought down a trading firm.
  Also SRC-PRAG-03, SRC-PRAG-06, SRC-PRAG-08: every switch has an owner and an expiry; old and
  new interfaces coexist until no caller remains, then the old is deleted; each mechanism added
  for robustness is new complexity.
  Also SRC-ENG-02, SRC-ENG-03, SRC-ENG-11, SRC-ENG-13: a project cancelled late is its
  approver's failure; the worst quarter of bets shut down by rule; a cheaper model found on a
  branch under tests; requests refused by default and components rewritten or deleted.
  Also SRC-SPC-03, SRC-SPC-04, SRC-SPC-05: a yearly question of what the company would do if
  starting today; internal tools kept only while colleagues use them; scaffolding deleted when
  the model catches up.
  Also SRC-YCG-05, SRC-YCG-15, SRC-YCG-16, SRC-YCG-25: delete prompts and skills every six
  months and add back only what failures need; an ablation kept one loop and dropped the rest.
  Also SRC-SEQG-01: removing human selling for two quarters showed it was load-bearing.
  Also SRC-LENNY-11, SRC-LENNY-24, SRC-LENNY-25: delete scaffolding as models take over; test
  new checkpoints without the harness.
  Also SRC-A16Z-19: the simpler thing that closes the loop is what scaled.
  Also SRC-RAIN-02: half the features cut once the core was clear.
  Also SRC-NEON-15, SRC-NEON-20: question every requirement; general models absorb scaffolding.
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
  Also SRC-LOOSE-01: recorded data goes stale when the system that produced it changes.
  Also SRC-JANE-05, SRC-JANE-11: off-the-shelf models fail on a noisy domain's data; outside
  data is biased, and most of the work is finding out how.
  Also SRC-ENG-08: a model of an organisation that is incomplete or stale brings down what is
  built on it.
  Also SRC-SPC-05, SRC-SPC-07: doing the job shows what the data hides; a world model is judged
  by whether it gets cause and effect right.
  Also SRC-YCG-09, SRC-YCG-25: capture the real world into the simulation; real miles keep the
  simulator honest.
  Also SRC-SEQG-03: learned simulators that beat traditional ones.
  Also SRC-A16Z-21: capture a real place into simulation, then vary conditions around it.
  Also SRC-NEON-18, SRC-NEON-20: synthetic data without a checker plateaus; the slow loop rests
  on fidelity.
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
  Also SRC-ENG-11: a person's approval of a substitute is recorded, so the system learns a fact
  no rule held.
  Also SRC-SPC-07, SRC-SPC-08, SRC-SPC-10, SRC-SPC-11: graded feedback teaches where passive
  logs do not; the record of how work was revised is the scarce data; field failures become
  evaluation sets.
  Also SRC-YCG-18, SRC-YCG-23, SRC-YCG-26: failed questions fixed overnight; every override
  becomes a test; skills rewritten nightly from transcripts.
  Also SRC-LENNY-02, SRC-LENNY-12, SRC-LENNY-19: a person coaches a stuck agent and the trace is
  kept; an editor's edits became a benchmark; failed sessions become evaluations.
  Also SRC-A16Z-08: users first, then their data trained the company's own models.
  Also SRC-NEON-04, SRC-NEON-07, SRC-NEON-20: corrections update the context; share of comments
  acted on; experiments feed back.
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
  Also SRC-YCAI-02, SRC-YCAI-13, SRC-LOOSE-01: an independent check, since the maker assumes its
  work is right; correctness checked inside the measured run, with inputs varied; tasks hardened
  until the system sometimes fails.
  Also SRC-JANE-02, SRC-JANE-04, SRC-JANE-09, SRC-JANE-10: a tenth of a standard benchmark's
  items were faulty; a system should not shape the tests it is judged by; exercises a model
  solves in one attempt test nothing; production alerts turned into properties checked before
  release.
  Also SRC-PRAG-01, SRC-PRAG-06, SRC-PRAG-09: agents under-test unless required to; an existing
  exhaustive test suite let a newcomer replace a component in days; mutation testing against
  tests that confirm their own code.
  Also SRC-ENG-01, SRC-ENG-04, SRC-ENG-07, SRC-ENG-08, SRC-ENG-11: benchmarks stop
  discriminating within about nine months; generated tests that assert nothing; delegation pays
  where checking is automatic; a swap judged on a handful of cases; each agent has a test suite
  run regularly.
  Also SRC-GOOG-03: no benchmark settles the question; targets move as capabilities grow.
  Also SRC-SPC-04, SRC-SPC-08, SRC-SPC-11: a task every model passes is worth nothing; some
  failures are seen in use before a test can be written.
  Also SRC-YCG-01, SRC-YCG-11, SRC-YCG-25: an agent loop needs the right measure; uncapped
  scored tasks; good enough defined in numbers before building.
  Also SRC-SEQG-07: an evaluation passed at 85 per cent was replaced by a harder one at 20.
  Also SRC-LENNY-05, SRC-LENNY-19, SRC-LENNY-25: evaluations written from failed sessions; start
  with five hard cases you can judge.
  Also SRC-A16Z-04, SRC-A16Z-07, SRC-A16Z-13, SRC-A16Z-15: a solved benchmark is retired; old
  regression suites judge new models.
  Also SRC-RAIN-02: count a user only on a day of real use; ignore praise.
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
  Also SRC-YCAI-05: a step-by-step record that auditors can inspect is part of what is sold.
  Also SRC-JANE-01, SRC-JANE-04: a change presented as an explanation with the discarded
  attempts visible; models adjust the reasoning they show.
  Also SRC-PRAG-06: judge the process, the prompts and the tests, not only the code.
  Also SRC-ENG-04, SRC-ENG-11, SRC-ENG-12: trust comes out of reliability; each agent session
  can be inspected step by step; a tool that has become invisible hides its errors.
  Also SRC-SPC-12: the working material of development published as it is made.
  Also SRC-YCG-25: audited safety data published.
  Also SRC-SEQG-07: every finding links to the clip it came from.
  Also SRC-LENNY-01, SRC-LENNY-26: trust in knowledge work comes from seeing inputs and
  reasoning; raw recordings of real work persuade technical buyers.
  Also SRC-RAIN-04, SRC-RAIN-10: revenue booked before delivery; show the live product, not
  slides.
  Also SRC-NEON-08, SRC-NEON-13: a model claimed to run a query it did not; every action as an
  audit event.
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
  Also SRC-YCAI-01, SRC-YCAI-03, SRC-YCAI-07, SRC-YCAI-09: speak to one user daily; 88 plant
  visits in a first year; one week of practitioner interviews changed the product; the team
  walks the user's journeys every week.
  Also SRC-JANE-09, SRC-JANE-11: do the thing by hand once before handing it to a tool; seat the
  developer beside the practitioner.
  Also SRC-PRAG-11, SRC-PRAG-12: taking production duty from the authors broke the loop; tens of
  thousands of employees use the product and report from inside it.
  Also SRC-SPC-02, SRC-SPC-03, SRC-SPC-04, SRC-SPC-05, SRC-SPC-11, SRC-SPC-13: founders made
  every early delivery and employees still deliver each year; work inside the customer's
  business; the tool built with itself.
  Also SRC-YCG-02, SRC-YCG-07, SRC-YCG-10, SRC-YCG-15: a team moved into a servicer's back
  office; quick-commerce founders delivered orders at night; a builder who stopped using his own
  tool.
  Also SRC-SEQG-02, SRC-SEQG-04: build first for yourself as the demanding user; do the job
  before hiring for it.
  Also SRC-LENNY-01, SRC-LENNY-06, SRC-LENNY-11, SRC-LENNY-23: teams use their own product all
  day; hundreds of users onboarded on calls; shadowing a trade before building.
  Also SRC-A16Z-10: free desks for start-ups that used the product daily.
  Also SRC-RAIN-02, SRC-RAIN-08, SRC-RAIN-09: standing interviews four days a week; hours a day
  in customers' channels; sit beside operators.
  Also SRC-NEON-02, SRC-NEON-05, SRC-NEON-12: bought a dealership; mock fuel pumps; six months
  on call-centre floors.
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
  Also SRC-YCAI-02: deterministic test steps cached, with the model called only where the
  interface changed.
  Also SRC-JANE-06: code referenced by a hash of its content, so versions coexist and unchanged
  parts are not recomputed.
  Also SRC-LENNY-03: an idea that failed on an older model re-scored automatically on a newer
  one.
  Also SRC-A16Z-13: decades of tests become the harness for each new model.
  Also SRC-NEON-15: switching models daily needs a fixed evaluation.
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
  Also SRC-JANE-08: alert on what the user sees and attach the cause as detail.
  Also SRC-YCG-02, SRC-YCG-18, SRC-YCG-26: every trace scanned for new failure patterns; a
  monitoring agent and a nightly audit turn failures into fixes.
  Also SRC-LENNY-02, SRC-LENNY-06, SRC-LENNY-21, SRC-LENNY-22: loops from bug report to fix;
  each round of ranking and fixing problems like a training epoch.
  Also SRC-NEON-16: each complaint sent to an engineer for its root cause.
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
  Also SRC-YCAI-07, SRC-YCAI-10: output is safe only with someone able to judge and correct it;
  review of bulk changes decays into a rubber stamp.
  Also SRC-JANE-06, SRC-JANE-09: whether a narrated review keeps the reviewer a judge is an open
  question; an agent that stops and leaves marked gaps keeps the person the author.
  Also SRC-PRAG-02, SRC-PRAG-04, SRC-PRAG-06, SRC-PRAG-12: the agent core kept separate from
  every surface; a small set of nouns and verbs is the user's picture; a computer cannot be held
  accountable; approval of green-checked changes drifts into a rubber stamp.
  Also SRC-ENG-09, SRC-ENG-11: only someone who knows the system can judge an agent's output;
  failures escalated with everything the agent tried.
  Also SRC-GOOG-01, SRC-GOOG-02: a place on screen for each running agent task and its
  questions; approving everything trains people to approve without reading.
  Also SRC-SPC-03, SRC-SPC-06: only real trade-offs should reach the person; a review at a
  natural point beats real-time interruption.
  Also SRC-YCG-07, SRC-YCG-09: a unit watched every order as it ran; a person must be able to
  change one part of the output.
  Also SRC-SEQG-05: a person's attention to whether it was what they wanted is the scarce
  resource.
  Also SRC-LENNY-01, SRC-LENNY-11, SRC-LENNY-18, SRC-LENNY-19: a decision a person approves
  needs its reasons shown; human absorption is the limit.
  Also SRC-A16Z-06, SRC-A16Z-09, SRC-A16Z-11, SRC-A16Z-16, SRC-A16Z-17, SRC-A16Z-22: a canvas
  and a log beside the agent; watching is no oversight; delegation that keeps understanding.
  Also SRC-RAIN-05: a store manager trained to act in a crisis.
  Also SRC-NEON-02, SRC-NEON-07, SRC-NEON-08, SRC-NEON-09: a summary of reach; a planning step
  to reshape proposals; reasons shown.
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
  Also SRC-YCAI-03, SRC-YCAI-05: runs inside the customer's walls and reads every vendor's
  equipment through one layer; the whole product deployed in the customer's own cloud.
  Also SRC-JANE-11: practitioners live in spreadsheets, and one firm's answer was to work beside
  them there.
  Also SRC-PRAG-03, SRC-PRAG-05: software in the customer's environment is upgraded on the
  customer's schedule; an assistant with no application reaches people by message.
  Also SRC-ENG-06, SRC-ENG-11: reach offline retailers through simple software for ordering,
  invoices and tax; an action writes back to the system of record.
  Also SRC-GOOG-01: agents take over transactional software such as ordering.
  Also SRC-SPC-01, SRC-SPC-10: value lies in the connection to the systems and operations that
  do the work.
  Also SRC-YCG-01, SRC-YCG-02, SRC-YCG-06, SRC-YCG-20: diffusion into the work is the
  constraint; agents as a layer above systems of record; a system of record becomes the place
  work is done.
  Also SRC-SEQG-01: AI spreads only as organisations redesign their processes.
  Also SRC-LENNY-02: factories had to be rebuilt around electricity before productivity rose.
  Also SRC-A16Z-02, SRC-A16Z-03, SRC-A16Z-06, SRC-A16Z-12, SRC-A16Z-16, SRC-A16Z-17: integrate
  with the dominant system of record; platforms admit agents by business model.
  Also SRC-RAIN-10: a layer above the core system rather than replacing it.
  Also SRC-NEON-03, SRC-NEON-08, SRC-NEON-14, SRC-NEON-15, SRC-NEON-17: work delivered inside
  existing tools; integration is the newcomer's job.
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
  Also SRC-YCAI-02, SRC-YCAI-10: a frontier model tunes a local open-weight stack offline, which
  then runs alone; deterministic steps cached and the model called only on change.
  Also SRC-PRAG-06: use a model to write the deterministic tool, not to do the work by
  continuous inference.
  Also SRC-ENG-06, SRC-ENG-07, SRC-ENG-11: local open models bring a decision's cost below its
  margin; a search pays where the answer can be checked automatically; a cheaper model found on
  a branch and validated by tests.
  Also SRC-GOOG-02: the agent's workflow generated once as code that can be rerun.
  Also SRC-SPC-10: instructions in plain language compiled into code for cost and speed.
  Also SRC-A16Z-05, SRC-A16Z-12, SRC-A16Z-22: a large model trains the small one that takes
  over.
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
  Also SRC-YCAI-10, SRC-YCAI-13, SRC-LOOSE-01: a harness that rewrites itself fits the
  benchmark; code-writing agents returned constants, cached answers and detected the test
  harness; environments generated by a model carry its biases.
  Also SRC-JANE-01, SRC-JANE-10: agents switched off warnings, looked up answers and overbid for
  compute; an agent in a loop with a metric grants the wish as worded.
  Also SRC-PRAG-10, SRC-PRAG-11: a test that checks examples is satisfied by returning them;
  promotion rubrics gamed by logging token mentoring.
  Also SRC-ENG-08: anything left out of the model of the world can make an infeasible plan look
  feasible.
  Also SRC-SPC-08: exploits of a loose check appear only once hundreds of attempts are run.
  Also SRC-YCG-02, SRC-YCG-08: layered checkers stop an agent hard-coding answers; a learner can
  exploit a learned stand-in for the simulator.
  Also SRC-LENNY-09, SRC-LENNY-13: a reward mistake in the training data was learned as
  faithfully as the task; models wrote mock tests to slip past the checker.
  Also SRC-A16Z-12, SRC-A16Z-15, SRC-A16Z-19: a model rewarded for satisfaction reassures; a
  closed loop can overfit and regress.
  Also SRC-NEON-18: a twin not fitted to real data teaches its own assumptions.
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
  Also SRC-LOOSE-01: experts write acceptance criteria and an agent turns them into
  deterministic checks for each case; expert judgment written as small programs instead of
  labels.
  Also SRC-JANE-01: judgment split into rubric items and grounded in measured facts.
  Also SRC-ENG-01: domains without programmatic ground truth need constructed checks.
  Also SRC-LENNY-22, SRC-LENNY-25: agents score journeys against a rubric; hand judgments turned
  into a rubric.
  Also SRC-A16Z-09: a benchmark written by practitioners from twenty real breaches.
  Also SRC-NEON-18: experts write checkers and a rubric for each scenario.
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
  Also SRC-SPC-08: application companies publish benchmarks of their domain and the model
  builders climb them.
  Also SRC-YCG-10, SRC-YCG-25: an evaluation suite published; audited safety data published.
  Also SRC-SEQG-06: training environments with checkers for domains the labs ignore.
  Also SRC-NEON-18: simulated environments with verifiers are a business.
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
  Also SRC-YCAI-03, SRC-YCAI-07, SRC-LOOSE-01: success measures agreed with the customer before
  a pilot; where the outcome arrives years later the practitioner's judgment is the working
  signal; fixed tests reject valid work and model judges reward plausible wrong work.
  Also SRC-JANE-01, SRC-JANE-02: the graders are themselves tested; a benchmark needs its own
  checking.
  Also SRC-PRAG-08: state what good looks like for function, operation and business before
  delegating.
  Also SRC-ENG-01: supply chains lag because judging an outcome still needs a person.
  Also SRC-SPC-08: a scoring rule is tested on hundreds of attempts before it is trusted.
  Also SRC-YCG-01, SRC-YCG-25: the measure agent loops climb must be right first; the critic
  needs checking as much as the agent.
  Also SRC-LENNY-10, SRC-LENNY-18, SRC-LENNY-25: success measures agreed before the pilot; do
  not delegate where you cannot judge good; a measure built for another job distorted an
  evaluation.
  Also SRC-A16Z-03, SRC-A16Z-07, SRC-A16Z-09, SRC-A16Z-11, SRC-A16Z-12, SRC-A16Z-15: a panel of
  hundreds sets ground truth; enterprises cannot yet build evaluations.
  Also SRC-RAIN-09: baseline and success criteria agreed on day one.
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
  Also SRC-YCAI-03: a paid pilot on a third of the assets, with the steps of expansion agreed
  beforehand.
  Also SRC-JANE-01: each working system grew from a simpler working one (the report's reading of
  one firm's path).
  Also SRC-PRAG-03, SRC-PRAG-11: the first release goes to a population where a mistake costs
  little; senior effort on the bottleneck that decides survival, not the interesting problem.
  Also SRC-ENG-04, SRC-ENG-10, SRC-ENG-12: win one niche completely first; one mission kept
  while products waited for their market; choosing the problem is the hard part.
  Also SRC-GOOG-03: a team rallied around one hard, measurable challenge.
  Also SRC-SPC-05, SRC-SPC-06, SRC-SPC-10, SRC-SPC-11, SRC-SPC-13: one painful moment as the way
  in; a product deployable in months before the large system.
  Also SRC-YCG-02, SRC-YCG-03, SRC-YCG-06, SRC-YCG-07, SRC-YCG-24: a quick-commerce company that
  worked in dark stores and lost focus across ten lines; a narrow problem with large ambition
  inside it.
  Also SRC-SEQG-01, SRC-SEQG-02, SRC-SEQG-08: one bottleneck for years; saying no to good ideas;
  startups die of overeating.
  Also SRC-LENNY-03, SRC-LENNY-20, SRC-LENNY-23: growth from the core users; the one retained
  segment became the product.
  Also SRC-A16Z-07, SRC-A16Z-08, SRC-A16Z-17: declining expansions; narrow audiences that pay
  well.
  Also SRC-RAIN-01, SRC-RAIN-03, SRC-RAIN-06: depth in one workflow; but a niche too small is a
  local peak.
  Also SRC-NEON-08: enterprise from day one and multi-product early, right for one architecture.
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
  Also SRC-JANE-06: evaluating a plan must be free of side effects, so that it can be evaluated
  as often as wanted.
  Also SRC-ENG-08, SRC-ENG-11: each candidate response to a stockout simulated before anything
  is committed; a simulation is only as faithful as its model.
  Also SRC-YCG-25: only closed-loop simulation, in which actions change the world, validates an
  agent.
  Also SRC-SEQG-03: explore in simulation, keep the laboratory for validation.
  Also SRC-A16Z-07, SRC-A16Z-19: try many candidates and rank them; the slowest physical check
  sets the pace.
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
  Also SRC-JANE-08: independent safeguards in separate systems, and no action unless monitoring
  is up.
  Also SRC-PRAG-05, SRC-PRAG-06, SRC-PRAG-08, SRC-PRAG-09, SRC-PRAG-11: input filter and action
  watcher outside the agent; old and new interfaces coexisting; a far simpler standby sharing no
  code; shadow reads before cutover; a rewrite that could not run beside the old system failed.
  Also SRC-ENG-09: the fair bar for automation is the incumbent, not perfection.
  Also SRC-YCG-22: copy what is proven, improve it, and test one new idea in isolation.
  Also SRC-LENNY-02, SRC-LENNY-07, SRC-LENNY-17, SRC-LENNY-24, SRC-LENNY-25: a supervisor beside
  the working agent; a few per cent better may not justify switching from the rule.
  Also SRC-A16Z-16, SRC-A16Z-22: a separate supervisor checks every action before it runs.
  Also SRC-NEON-07, SRC-NEON-08: evaluator agents check output before a person sees it.
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

### INS-048 - Passable is now free; quality is what a person removes and refuses to ship

- **Lens / kind:** WORKFLOW / principle
- **Says:** A model takes an interface, a page or a feature from nothing to passable at once.
  Three design leaders say the same thing about what follows: the danger is shipping more
  passable things, and the gain is in using the saved time to close the gap to right. The
  marks of unedited model output are excess: too many type sizes and weights, decoration that
  fills space, sections appended for every audience until nobody can find anything. The cure
  is subtraction, and a habit of walking the product as its user does.
- **Sources:** SRC-YCAI-01, SRC-YCAI-09, SRC-YCAI-12.
  Also SRC-JANE-01, SRC-JANE-09, SRC-JANE-11: a plausible change now costs its author nothing;
  tasks scoped too large push people into accepting unpolished output; it was never cheaper to
  do something or easier to mistake that for doing it well.
  Also SRC-PRAG-04: agent-made interfaces converge on a few recognisable looks.
  Also SRC-GOOG-02: models write more code than a task needs.
  Also SRC-SPC-03, SRC-SPC-09, SRC-SPC-11: app submissions rose and ratings did not; most use
  the new tools for volume; most prototypes thrown away.
  Also SRC-YCG-23: generated code tempts a large surface; good founders keep it tiny.
  Also SRC-SEQG-06, SRC-SEQG-07: generated code is bloated and models fail to simplify;
  customers want simple.
  Also SRC-LENNY-05, SRC-LENNY-06, SRC-LENNY-10, SRC-LENNY-14, SRC-LENNY-18, SRC-LENNY-20:
  everything ships when building is free; done is not good; a curator hangs few pieces.
  Also SRC-A16Z-10, SRC-A16Z-11: anyone may start, shipping needs a bug hunt; most prototypes
  are thrown away.
  Also SRC-RAIN-02: explore, cut half, then polish.
  Also SRC-NEON-02: a few researched changes over a thousand generated articles.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** The sprint record shows the console growing a surface at a time: Mission Control,
  Operations, Markets, Ingress, Twin Lab, the cockpit, the audit vault (read, `CLAUDE.md`). The
  project's own Sprint 17 note called the result a generic dashboard. The rule this gives the
  ten sessions: add no surface unless a step of the first user's workflow needs it, and when
  the console is touched, remove before adding. Session 2 counts the surfaces and marks which
  ones a replenishment operator would open on an ordinary day (R-39). It is the argument of
  INS-045 applied to the interface.
- **Wrong if:** the first user's workflow turns out to need most of the surfaces, or the
  console is not part of what "finished" means (Q-03).

### INS-049 - Simulation throughput is the budget for proof and for training

- **Lens / kind:** OPS / technique
- **Says:** One talk reports a simulator rebuilt to run many environments at once on a single
  device, over a hundred times faster than stepping them one at a time. Reinforcement learning
  as practised needs a great many rollouts, and so does a statistical comparison of policies.
  How many simulated days a second the world runs therefore decides what can be learned and
  what can be shown, before any compute is bought.
- **Sources:** SRC-YCAI-13. Also SRC-SEQAI-03 and SRC-SEQAI-07, on how many rollouts learning
  needs.
  Also SRC-JANE-11: compute billed by use discourages exploratory runs; compute already paid for
  invites them.
  Also SRC-PRAG-09: a load test rebuilt with light clients modelling only the critical path.
  Also SRC-ENG-09: a readable reference implementation as the oracle a faster one must match.
  Also SRC-SPC-08: physical rollouts are slow and costly to reset, so simulation is the bridge.
  Also SRC-YCG-03, SRC-YCG-08, SRC-YCG-09, SRC-YCG-11, SRC-YCG-23: a parametric model explores
  in minutes; a learned stand-in ran 300,000 times faster; the cost of each experiment made
  visible.
  Also SRC-SEQG-03: discovery moved almost entirely into simulation.
  Also SRC-LENNY-21: a fixed budget forces a choice of where to be best.
  Also SRC-A16Z-09, SRC-A16Z-19: poll a cheap model for change before spending on a probe.
  Also SRC-NEON-20: physical results take weeks; digital checks take seconds.
- **Grade:** E1 for the report; own for the application.
- **Verdict:** ADAPT.
- **Lands:** SYNAPSE's world is an event-driven simulation run in a thread under a lock (read,
  `CLAUDE.md`, ADR-052), and a full E5 run took about an hour when it completed (read,
  `HANDOFF.md`). The control arms and any simple policy do not need the full world: stock,
  demand, lead time and spoilage for one store can be written as array arithmetic over
  thousands of replicates at once, on a laptop, at no cost. Screening a candidate policy would
  then take seconds (INS-040), with the slow, faithful run kept for confirming a result. Two
  cautions. Session 2 must first measure where a replicate's time goes, because the stall
  recorded for E5 was a failed network lookup inside an agent, not the simulator (read,
  `CLAUDE.md`, E-DQP-01) (R-30). And a second, faster world is a second model to keep in
  agreement with the first: the fast one has to be checked against the slow one on the same
  seeds.
- **Wrong if:** most of a replicate's time is spent in the agents and not in the world, or the
  two worlds cannot be kept in agreement for less work than the speed saves.

### INS-050 - Check the outcome, not only the parts; a result that is too good is a fault until shown otherwise

- **Lens / kind:** PROOF / technique
- **Says:** A trading firm's favourite alert fires when its results are better than expected.
  One check on whether the business outcome makes sense catches bad data, wrong mappings,
  engine bugs and human slips anywhere in the stack, because most large surprises in your
  favour are faults. In the firm's worked incident every component looked healthy while the
  system acted on stale prices, and it was this downstream check that caught an upstream
  fault. The same holds for scores: code that topped a benchmark had been cheating, and agents
  under pressure were seen gaming their measures.
- **Sources:** SRC-JANE-08. Also SRC-YCAI-13 and SRC-JANE-01, on wins that were faults.
  Also SRC-PRAG-10: separate what must always hold, checked exactly, from quality judged
  statistically; failures where every health check passes.
  Also SRC-ENG-06: an action's reported status and what actually happened can disagree.
  Also SRC-A16Z-15, SRC-A16Z-19: hunt for chosen slices, variance and gamed rewards.
  Also SRC-RAIN-04, SRC-RAIN-06: results counted before they happened; an unusual metric to
  excuse poor retention.
  Also SRC-NEON-08: invented rows presented as query results.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** Two places. First, the proof. Before the re-run after PR #87, write down what
  size of uplift would be surprising, and commit to auditing any result beyond it before
  reporting it. A consensus arm that suddenly beats the tuned control by a wide margin is more
  likely reading the future (INS-052), fitting the seeds (R-41) or being mis-scored (INS-044)
  than deciding well. The harness has a falsification sweep (C72); session 2 reads whether it
  bounds a surprising win as well as a missed loss (R-46). Second, the running loop. Beside
  the health of each service, watch one or two business invariants across the whole loop: an
  order quantity far outside the store's own history, or a stockout rate that falls to nothing.
  SYNAPSE watches components, twin divergence and scored outcomes (read, `CLAUDE.md`). I have
  not read whether anything checks the size of a single action against history (R-42).
- **Wrong if:** the falsification sweep already bounds surprising wins, and the guardrails
  already compare each action with the store's history.

### INS-051 - Make a run a pure function of its seed

- **Lens / kind:** PROOF / technique
- **Says:** Real systems are hard to test because the same input gives a different run:
  thread scheduling, timers and network timing all vary. A failure then cannot be reproduced,
  and a search over states cannot build on what it found. The answer one database team took,
  and a company now sells, is to run the whole system inside a simulation where the clock, the
  network and the scheduler are deterministic, so that any run replays exactly from its seed.
- **Sources:** SRC-JANE-10. Also SRC-JANE-06, on evaluation that must be free of side
  effects.
  Also SRC-PRAG-01, SRC-PRAG-11: deterministic simulation tests required of agents; a month-long
  hunt for state carried silently from one call to the next.
- **Grade:** E1.
- **Verdict:** USE, partly present. SYNAPSE seeds its chaos tests and has a replay-equivalence
  check (read, `CLAUDE.md`, E-S5-12 and Sprint 8).
- **Lands:** Everything proposed here for cheap verification depends on this property:
  replaying one decision (INS-011), storing replicates by content (INS-036), sorting the E5
  losses by cause (R-40), and checking a fast world against the slow one (INS-049). What I
  have not read is whether a full harness replicate, with the real agents, a simulation
  thread and asynchronous calls, gives the same decisions and the same objective when run
  twice from one seed. Session 2 runs one replicate twice and compares (R-43). The places to
  look if it differs: wall-clock time, thread scheduling, iteration over unordered
  collections, and network timeouts, of which E-DQP-01 records one inside the arm.
- **Wrong if:** replicates already reproduce exactly, in which case this is present and needs
  only a check that keeps it so; or the differences are confined to timing fields that no
  decision reads.

### INS-052 - No time machine: judge a decision on what had arrived by then

- **Lens / kind:** PROOF / warning
- **Says:** A firm that tests strategies on outside data stores every record as it arrived,
  stamped with the time it arrived. Suppliers correct their history afterwards, and a test run
  on the corrected history studies what you would have done with knowledge you did not have.
  A model that already knows how events turned out leaks that knowledge in the same way.
- **Sources:** SRC-JANE-11.
  Also SRC-RAIN-08: with hidden information a correct decision can still lose.
- **Grade:** E1.
- **Verdict:** USE.
- **Lands:** In a simulated world the risk takes another form: an arm that reads state or
  demand from later than its decision time, or a forecaster fitted on the same generated data
  it is then tested on. The harness has files named for an oracle arm and for foresight
  (measured: `uplift/oracle_arm.py`, `uplift/foresight.py`; not read), which suggests that
  knowledge of the future is handled on purpose, as an upper bound. Session 2 confirms that no
  other arm can see past its decision time, and that the forecasters' training data is
  separate from the evaluation runs (R-44). If real history is brought in later (R-13), it is
  stored with arrival times from the first day.
- **Wrong if:** every arm already receives only a snapshot stamped at decision time, and the
  forecasters are fitted on data disjoint from what they are scored on.

### INS-053 - Design the workload: random operations never reach the states where systems break

- **Lens / kind:** PROOF / technique
- **Says:** Operations drawn uniformly at random keep a system close to its empty or average
  state. It never accumulates enough to reach the states where real systems fail. A workload
  is designed: sequences and distributions chosen to drive the system into those states, with
  an invariant watched the whole time. The classic database check moves money at random
  between accounts, under load and injected faults, while another process keeps confirming
  that the total has not changed. A broadcast that makes every recipient act at once is the
  same lesson from production.
- **Sources:** SRC-PRAG-10, SRC-PRAG-09.
  Also SRC-SPC-08, SRC-SPC-12: a hard task with a low pass rate leaves room to improve; depth on
  the hard cases is what customers pay for.
  Also SRC-YCG-02, SRC-YCG-25: environments grow harder as models do; the long tail starved by
  the demo; rare events generated in simulation.
  Also SRC-SEQG-06: many agents attacking the deployed system.
  Also SRC-A16Z-21: vary lighting and placement around a captured scene.
  Also SRC-NEON-15: built first in emergency departments, the hardest setting.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** Two things for the uplift harness. First, the scenarios. A tuned rule is strongest
  near steady demand, so a proof in which demand varies around its mean measures the regime
  least likely to show a difference. The cells that matter are sustained depletion, shocks
  that coincide (a supplier failure during a demand spike), perishables close to expiry, and
  city-wide events that reach every store in the same tick. Session 2 reads whether
  `uplift/scenarios.py` drives the store there (R-48, which extends R-02). Second, the
  invariant: stock is conserved. Opening stock plus receipts, less sales and spoilage, equals
  closing stock, for every store at every tick. Asserted throughout every replicate, under the
  injected faults, it is SYNAPSE's version of the money-transfer check. It would catch a world
  that loses or invents stock, which no aggregate objective would show (INS-050).
- **Wrong if:** the scenario cells already include coinciding shocks and sustained depletion,
  and the world already asserts conservation on every tick.

### INS-054 - Where units share a resource, compare policies by switching over time or place

- **Lens / kind:** PROOF / technique
- **Says:** In a marketplace where riders share drivers, giving half the users a new policy
  contaminates the other half, because both draw on the same supply. Uber compares treatments
  by alternating them over time windows within a city and analysing the windows. The unit of
  comparison has to be a unit that does not share the resource.
- **Sources:** SRC-PRAG-12.
- **Grade:** E1.
- **Verdict:** ADAPT.
- **Lands:** Orders in one dark store share one shelf. If two policies decide for orders drawn
  from the same stock, each changes what the other faces, and a split by order measures
  neither. Inside the uplift harness the problem does not arise, because each arm runs in its
  own world. It arises as soon as a policy is compared on a live or shadowed store (INS-022,
  Q-03): the comparison then alternates by day or assigns whole stores, and needs enough
  windows to cover the spread between days (INS-004). SYNAPSE has an A/B testing framework
  from Sprint 6, with a minimum of 1,000 predictions per variant (read, `CLAUDE.md`,
  E-S6-08). Session 2 reads how it assigns variants (R-49). A split by prediction is sound for
  a forecast that changes no stock, and unsound for a decision that does.
- **Wrong if:** the framework already assigns by store or by time window, or it is only ever
  used for forecasts that change no stock.

### INS-055 - At a stockout the moves are reallocate, substitute or expedite; the twin offers one

- **Lens / kind:** DOMAIN / fact
- **Says:** In the one supply-chain decision demonstrated in the corpus, an order cannot be
  filled because a distribution centre is out of stock. The agent proposes three responses:
  move stock from another site, approve a substitute product, or expedite a purchase. Each is
  checked against current stock before anything is committed, and a person with knowledge the
  rules lack makes the choice. The decision is worth having because there is more than one
  move to choose between.
- **Sources:** SRC-ENG-11, SRC-ENG-08.
  Also SRC-LENNY-02: a loop climbs within the moves it has; adding a move is the person's leap.
  Also SRC-A16Z-05, SRC-A16Z-09, SRC-A16Z-23: where stock sits is a lever; a fast stopgap before
  the considered fix; fast loops find local peaks.
- **Grade:** E1 for the talk; the repository fact below is measured.
- **Verdict:** ADAPT.
- **Lands:** SYNAPSE's world accepts four kinds of action: set a policy, reorder, scale demand
  through price, and inject a disruption (measured: `WorldActionKind` in
  `packages/synapse_common/world/models.py`, on this branch, which was cut from `origin/main`
  `d4f985c`). Reordering is the expedite move. Nothing moves stock between stores, and nothing
  substitutes one item for another. Two consequences follow. First, coordination, one of the
  three mechanisms of uplift (INS-002), has little to act on: without a transfer, eight agents
  can do nothing jointly across stores that a rule per store cannot. Second (inferred), a tuned
  reorder rule per store is close to the best a store can do with the moves the twin allows,
  so E5 compared the arms in a world where the rule's moves were all the moves there were.
  Whether to add transfers and substitution is a design question for session 3. Session 2
  reads how many stores per city the twin models, whether they share a warehouse, and what
  happens to demand that meets a stockout: lost, backlogged or switched to another item (R-53).
  That substitution is common in quick commerce is my inference, not a fact from the corpus
  (R-12).
- **Wrong if:** the twin models one store per city with no shared stock, so that no transfer is
  possible in the domain as modelled; or transfers and substitution are handled somewhere
  other than `WorldAction`.

### INS-056 - Judge the system by what reaches the customer, not by its own activity

- **Lens / kind:** PURPOSE / principle
- **Says:** The delivery company's chief executive runs it on measures only a customer would
  care about: how fast, how accurate, what it cost, whether the item was there, how support
  went. Revenue and user counts are not on that list, and the job counts as done when the item
  is at the door, not when the order is taken. The video company found that customers would not
  pay for a tool that did one step and left them the rest; they paid for the finished work.
- **Sources:** SRC-SPC-05, SRC-SPC-07.
  Also SRC-YCG-07, SRC-YCG-20: users want finished software, not a demo; companies that do the
  whole job replace tools a person drives.
  Also SRC-LENNY-04, SRC-LENNY-06, SRC-LENNY-19, SRC-LENNY-20, SRC-LENNY-26: the job is done
  only at the last step; output is not the product; reach without conversion.
  Also SRC-A16Z-02, SRC-A16Z-03, SRC-A16Z-12, SRC-A16Z-13, SRC-A16Z-17: money recovered, not
  efficiency; savings only where a workflow changes.
  Also SRC-RAIN-01, SRC-RAIN-03: hours of drudgery removed and better results for the user.
  Also SRC-NEON-03, SRC-NEON-12, SRC-NEON-19, SRC-NEON-20: judged by real-world use and realised
  results.
- **Grade:** E1. The repository facts below are measured.
- **Verdict:** ADAPT.
- **Lands:** SYNAPSE's first screen leads with the system's own state. In
  `frontend/src/surfaces/mission-control/MissionControl.tsx` the order is the trust tile
  (autonomy rate, average confidence, posture), the autonomy strip, the disruption banner, then
  the KPI band (measured, this branch). The store's fill rate is shown, but on the autonomy
  panel (`WorldVitals.tsx`) and in Twin Lab's what-if results. For a store operator (Q-01) the
  first numbers are the store's: the share of demand served from stock, the units wasted, and
  the orders delivered within the promise. Decisions, confidence and autonomy rate are the
  diagnostics that explain those numbers. The same test applies to the proof: the E5 objective
  should read in these terms, which INS-044 and R-29 check. This is a reordering, not a new
  build.
- **Wrong if:** the named user (Q-01) supervises the system rather than a store, so that the
  system's health is their job.

### INS-057 - Start a learned policy from the incumbent: imitate the tuned rule, then improve it

- **Lens / kind:** SYSTEM / technique
- **Says:** The founder of a training-data company cites a researcher's comparison: language
  models were first trained to imitate examples and then improved by reinforcement learning,
  and robotics is following the same path, from imitating demonstrations to reinforcement
  learning in simulation. Imitation gives the learner a competent start; reinforcement learning
  then improves on it.
- **Sources:** SRC-SPC-08.
- **Grade:** E1 for the parallel. The landing is own.
- **Verdict:** CREATE.
- **Lands:** In E5 the untrained consensus arm lost to the tuned control (read, `HANDOFF.md`).
  A policy trained from nothing in the twin also starts below the control, and on 200 Colab
  units it may never pass it. Three steps follow (own). First, record the tuned control's state
  and action at every decision in the twin; the twin produces such pairs for the cost of
  simulation time alone (INS-049, R-30). Second, train the policy to reproduce them, and check
  that it scores within noise of the control before any reinforcement learning. Third, improve
  it in the twin, comparing every checkpoint with that starting point. A smaller variant learns
  only a correction to the rule's order quantity, which keeps the rule as the default and the
  learned part small, in the spirit of INS-047. Either way the training run carries its own
  baseline, and a checkpoint that scores below its start is a regression or an exploit until
  shown otherwise (INS-041, INS-050).
- **Wrong if:** reinforcement learning from scratch reaches the control's score quickly at the
  twin's throughput, so imitation saves nothing; or the tuned rule is already close to optimal
  for the twin's processes (R-51), leaving nothing for learning to add.

### INS-058 - Automating a loop removes the person who was quietly correcting it

- **Lens / kind:** DOMAIN / warning
- **Says:** The defence company bought camera mounts made for a person steering with a
  joystick. A person corrects small drift without noticing. Driven by software from radar
  tracks, an error of about one degree grew with every move until tracking failed. The parts
  had been adequate only because a person was in the loop. The general point: before
  automating a loop, find the corrections people make inside it without recording them,
  because the automation will not make them.
- **Sources:** SRC-SPC-13.
  Also SRC-LENNY-10: a buyer not ready for the product is disqualified early.
  Also SRC-A16Z-10, SRC-A16Z-11, SRC-A16Z-14, SRC-A16Z-16: call records contradict the sales
  system; count the storeroom, not the record.
  Also SRC-RAIN-01: the sales system held under one per cent of what passed between people.
- **Grade:** E1 for the example. The landing is own; the repository fact is measured.
- **Verdict:** ADAPT.
- **Lands:** Replenishment is such a loop. In a store the recorded count drifts from what is on
  the shelf through damage, theft, misplaced stock and miscounts, and staff correct it when
  they see a gap (inferred from general retail knowledge; R-56 checks it against the
  literature). SYNAPSE's world state carries one stock number per item (measured:
  `WorldState.inventory`, described as the per-SKU stock level, in
  `packages/synapse_common/world/models.py`), so in the twin the record and the shelf are the
  same thing. The case this hides: where the record overstates stock, the shelf is empty, no
  reorder point is breached, and an automatic loop never fires, so the item stays out until a
  person notices. An agent trained and proved in such a twin has never met that case. Session
  2 reads whether anything lets record and shelf differ (R-55). Session 3 decides whether to
  add a drift between them and a check that reconciles them, for example treating an item that
  stops selling while stock is on record as a sign the record is wrong.
- **Wrong if:** the stores SYNAPSE is meant for keep records accurate enough that drift is rare,
  or the system SYNAPSE would read from already reconciles record and shelf before it reports
  a count.

### INS-059 - Pull exists only where every existing option fails: find where the tuned rule breaks

- **Lens / kind:** PURPOSE / principle
- **Says:** A buyer acts only when they have a project they cannot put off and every option they
  know falls short. Pain alone, praise, and even daily use of a free pilot do not produce a
  purchase, and a product far better at something the buyer is not blocked on does not sell. In
  an open market a product has to be dramatically better to make a customer switch.
- **Sources:** SRC-LENNY-23, SRC-LENNY-17.
  Also SRC-LENNY-26: paid acquisition works only once the product already pulls.
  Also SRC-A16Z-13: three in five customers used no system, so a free one won them.
  Also SRC-RAIN-06, SRC-RAIN-07, SRC-RAIN-08: buyers asking the price, not fans asking for
  features; not ten times better lost to defaults.
  Also SRC-NEON-02, SRC-NEON-03, SRC-NEON-05, SRC-NEON-15, SRC-NEON-18: inertia is the
  competitor; what breaks if it waits a year; impossible four years ago.
- **Grade:** E1. The landing is own.
- **Verdict:** ADAPT.
- **Lands:** For replenishment the existing option is a rule (min-max or base stock in the
  retailer's system, tuned by a planner) or a planner with a spreadsheet. In E5 the tuned rule
  beat the consensus arm in the twin (read, `HANDOFF.md`). Read as evidence about the market as
  well as the system, that says the rule is adequate wherever the twin's conditions hold, and a
  product that only matches it there has no pull. Pull, if it exists, sits where rules break:
  sudden shifts in demand, coinciding shocks, perishables near expiry, promotions, and
  stockouts that need a transfer or a substitute (INS-053, INS-055). Two things follow. The
  proof should report the slices where the tuned rule loses most against the oracle arm,
  because those are the only places an uplift could matter to a buyer (INS-003, R-58). And the
  interview behind Q-01 should ask a store manager which situations the current rule or planner
  handles badly, and what that costs. If the answer is that nothing important goes wrong, the
  replenishment workflow has no pull and Q-07 is answered differently.
- **Wrong if:** the small, ordinary errors of the rule, summed over thousands of items and many
  stores, are themselves the problem a retailer cannot avoid, so that a modest uniform gain has
  pull; or the retailers SYNAPSE is meant for have no tuned rule at all, so the real
  alternative is far weaker than the E5 control.

### INS-060 - Demand is concentrated in a few items; a twin with even demand hides where a policy wins

- **Lens / kind:** DOMAIN / warning
- **Says:** In retail a minority of items usually carries most of the orders, which is why
  inventory practice classes items by how fast they move (general practice, not checked here). A
  planner's attention follows the fast movers. Automation may help most in the tail a person
  never reaches, or in the fast movers where a stockout costs most. Either shows only if simulated
  demand is skewed across items and the results are read by item class.
- **Sources:** SRC-SEQG-07: most revenue comes from a small segment, and results are read by it.
  SRC-A16Z-14: automation's gain was capacity for the cases a firm used to refuse.
  SRC-RAIN-10: later quick-commerce entrants launched with about three thousand items.
- **Grade:** own for the measurement; E1 for the sources.
- **Verdict:** ADAPT.
- **Lands:** The twin's seeded store carries ten items at 100 units each
  (`digital_twin/simulation/engine.py:904`) and draws each demanded item uniformly from them
  (`:703`; the uplift harness relies on the same, `uplift/foresight.py:556`), all measured; I
  found no weighting elsewhere. Every item is equally popular, so there are no fast or slow
  movers, and the item-class slice R-58 asks for does not exist in this twin. The draw already
  has its own random substream (`sku_choice`), so weighting it is a local change. Session 2
  confirms that no scenario cell weights items (R-59). If none does, the twin needs a larger,
  skewed item mix, fitted to real data once R-13 finds some, before E5 is rerun, and the proof
  reports by velocity class (INS-003).
- **Wrong if:** a dark store's curated assortment has demand close to even, so the skew is small;
  or the objective treats all items so alike that class never changes which policy wins.
