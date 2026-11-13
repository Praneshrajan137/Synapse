# Tensions

Where the corpus argues against SYNAPSE as built, or against itself. Every corpus folder is
asked the question; "nothing found" is a valid answer and is recorded.

A tension is not a verdict. Each one names what would settle it.

## Against SYNAPSE

### T-001 - Eight agents and a debate, against evidence that coordination often costs more than it returns

- **The corpus says:** per-step error compounds, handoffs strip uncertainty, and under matched
  budgets a single agent often matches a team (SRC-POSTS-06; arXiv 2512.08296, E3 at abstract
  level).
- **SYNAPSE says:** eight specialised agents reach consensus through an orchestrator. The first
  measured comparison against a tuned control was `baseline_wins`, with a named defect (finding
  112) as the cause (read, `HANDOFF.md`).
- **In fairness to the design:** the same paper finds that central coordination contains error
  growth (4.4x against 17.2x for independent agents) and that parallel subtasks gain. SYNAPSE's
  orchestrator is central and its agents cover separate functions. The result so far measures a
  defect, not the design.
- **Settled by:** the re-run after PR #87 against control E, on shocked and unshocked cells,
  with the mechanism of any uplift named in advance (INS-001, INS-002, INS-003).
- **Raised by:** Posts Context.

### T-002 - A mature platform's infrastructure at a stage with no user

- **The corpus says:** architecture is a trade-off for a stage and a team; defer what can wait
  (SRC-POSTS-08, SRC-POSTS-04).
- **SYNAPSE says:** Kafka, Neo4j, Redis, Postgres, Feast and MLflow, a Helm chart with a service
  mesh, two cloud targets, and 21 containers on one 8-vCPU VM (read, `CLAUDE.md`), built by one
  person, with no live order pipeline (read, `README.md`).
- **Why it matters now:** every component is carried in every session's reading, every CI run
  and every hour of cloud credit.
- **Settled by:** session 3 listing which components the definition of finished needs, and the
  cost of running them against the remaining credit (INS-019, Q-02).
- **Raised by:** Posts Context. Strengthened by Claude code - How to: a company with many
  backing services found running the full stack locally a limit on agent work and moved its
  agents to cloud sandboxes (SRC-HOWTO-01). On a $300 credit that route is mostly closed, which
  points toward a thin slice (R-08).

### T-003 - "Agency is architectural", against harness times model

- **The corpus says:** a better harness around a fixed model raises results a great deal
  (SRC-POSTS-01), and on a narrow job training matters far more than prompting (SRC-POSTS-05).
  Both findings are about models that are already capable.
- **SYNAPSE says:** the loop was closed with untrained policies, on the argument that agency is
  a property of the architecture and training is a later quality step (read, `CLAUDE.md`,
  ADR-052).
- **The gap:** an untrained policy behind a good architecture is a heuristic. A heuristic beats
  a tuned heuristic only if the architecture gives it more information, joint decisions, or
  adaptation (INS-002). Which of those needs a trained model is not yet written down.
- **Settled by:** the uplift decomposition in session 2 (R-03), then the Colab allocation in
  session 3 (INS-021).
- **Raised by:** Posts Context.

### T-004 - Which asset is the product: the agents or the proof?

- **The corpus says:** the durable layer is the one where learning accumulates, namely evals,
  routing, memory and the audit trail; the teams that win are the ones that can tell whether
  output is any good (SRC-POSTS-02, SRC-POSTS-03, SRC-POSTS-07).
- **SYNAPSE says:** the product is eight agents optimising a supply chain. Its most developed
  part is the apparatus that reported, before anyone asked it to, that those agents lost to a
  baseline. An earlier audit named this as a fault: apparatus ahead of substance.
- **The inference (own, unverified):** an apparatus that can return an honest negative on a
  multi-agent decision system is uncommon, and may be worth more to more people than one more
  supply-chain optimiser. It may equally be too bound to this twin to serve anything else.
- **Settled by:** the operator, in session 3 (Q-03), after session 2 reads how separable the
  harness is from the twin.
- **Raised by:** Posts Context.

### T-005 - "Prose is not free", against the volume of prose

- **The corpus says:** documentation exists to let someone act without asking; standing rules
  cost reasoning on every task; most agent spend is rediscovery (SRC-POSTS-04, SRC-POSTS-01).
- **SYNAPSE says the same** in `.kiro/steering/standard-of-work.md`, and holds a 68,257-character
  `CLAUDE.md` of which 49% is history (measured), a 498 KB task ledger and a 214 KB gate
  surface.
- **Settled by:** measuring the smallest reading set that lets a session start correctly, in
  tokens (R-10), and the operator's answer on `CLAUDE.md` (Q-04).
- **In fairness to the design:** the corpus questions the prose and endorses the gates. Hard
  checks sit at the top of the enforcement order in SRC-HOWTO-02 and written rules near the
  bottom, and the same talk holds that a codebase with guardrails is where agents work best.
  SYNAPSE's gates are what make ten agent-driven implementation sessions plausible at all.
- **Raised by:** Posts Context. Strengthened by Claude code - How to: practitioners there state
  the outcome and leave the method to the agent, while the last spec here carried a
  180,633-byte session protocol (measured).

### T-009 - The uplift proof ran with no model behind the reasoner

- **The corpus says:** measure the path you will deploy. A model behaves differently in each
  harness (SRC-POSTS-05), and instructions are tested where they will run (SRC-HOWTO-02).
- **SYNAPSE says:** it is a multi-agent system with LLM orchestration, with model reasoning in
  its upper decision tiers (read, `CLAUDE.md`). E5 ran with no Ollama behind the Disruption
  Shield's reasoner: a harness that drives the real agents must point the reasoner at a refused
  port or inject an offline one (read, `CLAUDE.md` E-DQP-01), and the README lists the cache
  metric as unmeasured because Ollama was offline.
- **So (inferred):** the measured arm is the system without its model reasoning. The headline
  says nothing, for or against, about what the LLM tier adds.
- **In fairness to the design:** a CI runner has no model server, and running offline kept the
  result honest about what it covered.
- **Settled by:** session 2 reading what the reasoner returns when offline and which decisions
  would take the model path (R-19); then session 3 deciding whether any labelled run can afford
  a real reasoner.
- **Raised by:** Claude code - How to.

## Inside the corpus

### T-006 - Harness over model, or training over prompting?

- SRC-POSTS-01 relays results where a weaker model with an improved harness beat a stronger one.
  SRC-POSTS-05 relays an experiment where training moved accuracy 15-21 points and prompt
  examples less than one.
- **Reading:** they answer different questions. The harness wins when the base model is strong
  and general. Training wins on a narrow job with labelled data. SYNAPSE has both kinds of
  part: a general reasoner in the disruption path, and narrow forecasters and policies.

### T-007 - Mock your dependencies, or run it like production?

- One post in SRC-POSTS-03 argues that shared staging and end-to-end suites fail at scale and
  that each service should test against stand-ins for its neighbours. Others in the same file
  say bugs hide where local differs from production.
- **Reading:** a stand-in is safe only when it is generated from the producer's real contract.
  Finding 112 sat behind tests that sent a hand-written, wrong-shaped request (read,
  `CLAUDE.md` E-DQP-02). Both halves are needed: contract-derived stand-ins for speed,
  and one prod-like path kept alive (INS-005, INS-013).

### T-008 - Spend tokens freely, or count them?

- In SRC-HOWTO-01 two companies set no token limit per engineer and argue that where the
  return is positive, cost should not be minimised. The speaker of SRC-HOWTO-02 has unlimited
  model access. The same report's critique names a cost wall for individuals, and SRC-POSTS-04
  relays work on cutting agent spend.
- **Reading:** most practices in the corpus were proven by people with no limit. On a fixed
  plan, the ones that remove waste survive: verification before autonomy, hard constraints,
  narrow fan-out, cheap readers for bulk work (INS-013, INS-014, INS-015, INS-026). The ones
  that buy quality with volume do not: workflows of forty or more agents, and tuning loops run
  until a perfect score.
