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
- **Raised by:** Posts Context. Strengthened by Claude Code - Classes, which is the strongest
  folder on this point so far. The corpus's example nearest to SYNAPSE's domain, an inventory
  agent covering stock, forecasting, supplier choice and ordering, went from a 62% to a 92%
  eval pass rate (as reported) when its sub-agents were folded back and its tools cut
  (SRC-CLASSES-01). Two other teams removed a layer of agents (SRC-CLASSES-05, SRC-CLASSES-16).
- **A second point in fairness:** those were model-driven sub-agents sharing one objective.
  SYNAPSE's agents each carry their own reward (I-2), a reason those cases do not cover. It
  holds only if the objectives conflict in practice and arbitration binds (INS-028, INS-023).
- **Added by Sequoia Capital- AI, with conditions on both sides:** a field that tried both found
  that a pipeline of specialised modules joined by hand-written interfaces lost to one learned
  whole (SRC-SEQAI-04), and one company prefers a single agent following a written procedure to
  a graph of narrow steps (SRC-SEQAI-16). The first result needed abundant real data, which
  SYNAPSE does not have, so it is not evidence against the design here. On the other side, a
  learned policy did beat tuned expert practice in chip layout, given a faithful cost function
  and a great many simulated trials (SRC-SEQAI-19), and an explicit staged architecture is
  still held to be right where control and predictability are required (SRC-SEQAI-01).
- **A third arm worth having:** a simple policy found by search against the harness (INS-040),
  and a fallback design in which the consensus acts only when an arbiter prefers it to the rule
  (INS-047). Either turns the question from which side wins into where each one wins.
- **Added by Jane Street:** a panelist with experience inside the labs says swarms of many
  agents exist there and cannot be deployed, because their behaviour drifts and they take
  destructive actions nobody asked for (SRC-JANE-04). A researcher reports a swarm on one
  repository spending heavily on its own conflicts (SRC-JANE-06). The report on the firm's own
  agent platform reads its history as growth from a simple working system (SRC-JANE-01). These
  are coding agents sharing one body of work, not agents with separate functions, so they bear
  on SYNAPSE's design by analogy only. Their direct lesson is for how many agents the
  implementation sessions run at once (INS-026).
- **Added by ENGINEERING:** the corpus's one demonstration on a supply-chain decision uses
  several agents, each owning a stage of an order, working over one shared model of the
  organisation, with a person deciding what they cannot (SRC-ENG-11). That is close to
  SYNAPSE's shape, and counts in its favour. It also shows where the value came from: the
  options, and the simulation of each, not debate between the agents. And by analogy (own),
  agents that each optimise an independent objective are passengers each steering for a
  different town unless an arbiter binds (SRC-ENG-02); INS-023 and R-16 are where that is
  measured. INS-055 adds a structural point: without a way to move stock between stores, the
  twin gives coordination little to do.
  YC GUIDE adds the chief executive of a chip company whose founding approach was wrong: he
  said so to the customer paying for it and changed course, and the honesty kept the company
  alive (SRC-YCG-09). E5 is SYNAPSE's version of that moment.
  Lenny's Podcast adds three sources that teams of agents grow while models are weak and shrink
  to one directing agent when a stronger model arrives, and that people who run many agents add
  a chief-of-staff agent to manage the rest (SRC-LENNY-07, SRC-LENNY-19, SRC-LENNY-24); by
  analogy, a round that waits for every participant runs at the pace of the slowest
  (SRC-LENNY-20); and most industries are bound by execution rather than intelligence, which
  caps what a better decision layer can add (SRC-LENNY-02).
  a16z adds the other side: general agents take away the person's understanding without
  taking any responsibility, so narrow agents with clear bounds are easier to delegate to
  (SRC-A16Z-22). That favours specialised agents only where each one's scope is one a person
  can judge.
  Rainmatter adds that a product showing its makers' organisation chart has lost its coherence
  (SRC-RAIN-02); eight agents for seven functions are open to that reading (own).

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
  points toward a thin slice (R-08). Strengthened again by Claude Code - Classes: the most
  scaled engineering organisation in the corpus holds as a fifteen-year rule that fewer
  technologies is faster, for agents as for people (SRC-CLASSES-18). Strengthened by The
  Pragmatic Engineer: the author of the standard books on microservices calls them a last
  resort whose one good reason is to let many teams work without waiting on each other, and
  one company that made every feature a service later merged them back (SRC-PRAG-08). The
  counterweight is Uber, whose agents succeed because of a decade of platform built for its
  scale (SRC-PRAG-12). For one person, the part of such a platform worth having is the part
  that verifies: replay, fast feedback and an identical environment, not the distribution.
  ENGINEERING adds Zerodha: 35 to 40 engineers have run India's largest retail broker for a
  decade on open software they host themselves, by refusing most requests and keeping each
  system with the same two or three owners for years (SRC-ENG-13). South Park Commons adds
  that now models find flaws fast, every dependency and service is a stream of patches
  (SRC-SPC-01), and that ordinary software decays unless someone keeps working on it
  (SRC-SPC-09).
  YC GUIDE adds that code generators now make building easy and leave operating as the hard,
  lasting problem (SRC-YCG-21).
  Lenny's Podcast adds a project that hired thirty engineers before it had any sign of demand,
  and failed (SRC-LENNY-15).

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
- **Raised by:** Posts Context. Sequoia Capital- AI supports the order of work: two companies
  say to find the fit on general models first and train afterwards, so that each trained model
  is one variable swapped into a working harness (SRC-SEQAI-10, SRC-SEQAI-18). It also gives a
  test for whether training can help at all: if the starting policy never succeeds there is
  nothing to reinforce, and if it succeeds sometimes, training can amplify that (SRC-SEQAI-14).
  Session 2 can apply that test to the E5 replicates (R-33).
  Lenny's Podcast adds a product leader's estimate from motor racing: the driver accounts for a
  small share of the result and the car, crew and data for the rest (SRC-LENNY-21).
  a16z adds a test for any claim that a system improves itself: who does the optimising? If an
  engineer reads the results and changes the settings, the engineer is still the optimiser, and
  closing the loop guarantees no convergence (SRC-A16Z-19).

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
- **Raised by:** Posts Context. Strengthened by Sequoia Capital- AI: one company says outright
  that what its customers buy is the boundaries and controls around the agent (SRC-SEQAI-20),
  another's customers valued the transparent record for its own sake (SRC-SEQAI-16), and a
  third published its benchmark and became the reference for its field (SRC-SEQAI-10, INS-043).
  YC AI GUIDE adds two more: a step-by-step record that auditors can inspect is part of what
  one finance company sells (SRC-YCAI-05), and a testing company holds that the lasting asset
  is the specification and the loop that verifies against it, not the code (SRC-YCAI-02).
  Jane Street adds that testing was long treated as low-status work and so left undervalued,
  and that a company was built on that gap (SRC-JANE-10). The Pragmatic Engineer adds a case
  in point: an engineer new to a domain used a model to replace a costly licensed component
  in days, because an exhaustive test suite already existed. The suite was the asset
  (SRC-PRAG-06). South Park Commons adds a company whose product a model can copy on the
  surface in minutes, and whose customers still pay for its depth on the hard cases
  (SRC-SPC-12).
  YC GUIDE adds that model builders spend heavily on environments and scorers for training and
  more than a dozen young companies sell them (SRC-YCG-20); that the hard part of a lasting
  company is no longer the code (SRC-YCG-06); and that interfaces are disposable while the
  data and the know-how are the asset (SRC-YCG-18).
  a16z adds that an assistant with no hold on the customer's data had no pricing power against
  ten rivals (SRC-A16Z-10), and the "yet" test: an advantage that rests on a general model not
  being able to do something is fragile (SRC-A16Z-13). Both point at the twin and the proof as
  the durable part.
  Rainmatter adds the order for a stalled product: change the message, then the channel, then
  the customer, and only then the product (SRC-RAIN-03); and a failed search start-up whose team
  and code became its acquirer's AI base (SRC-RAIN-07).

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
  180,633-byte session protocol (measured). Strengthened again by Claude Code - Classes:
  processes pile up because nobody deletes one unprompted (SRC-CLASSES-11), stored know-how has
  a half-life (SRC-CLASSES-17), and markdown past a couple of hundred lines is not read
  (SRC-CLASSES-14). That last point applies to this folder's own ledger. YC AI GUIDE adds that
  a library nobody prunes becomes a dump (SRC-YCAI-06), and that a specification kept as the
  source of truth is itself a thing to maintain, which nobody checks (SRC-YCAI-02). South Park
  Commons adds a design team that kept going back to the code because every document above it
  decayed (SRC-SPC-03), and a company that settles arguments by shipping something or calling a
  customer, not by the best memo (SRC-SPC-05).
  Lenny's Podcast adds that a long document no longer shows anyone thought, because a model can
  write one (SRC-LENNY-01); that requirements written before the evidence waste effort and are
  useful only after it (SRC-LENNY-17); and that where trying is cheaper than debating, the
  debate is the expensive part (SRC-LENNY-08).

### T-012 - The twin is declared; the corpus's comparable proofs are fitted to real history

- **The corpus says:** where a decision's result arrives late, the proof is a model of the
  world built from what really happened: a merchant's actual sequence of actions, or fifteen
  years of market history run through one standard pipeline (SRC-CLASSES-04, SRC-CLASSES-20).
- **SYNAPSE says:** its world is a simulation with declared parameters. The handoff records its
  fidelity as unknown, and an earlier dataset's terms as declined (read, `HANDOFF.md`).
- **So:** every uplift figure, positive or negative, is conditional on a world nobody has
  compared with a store. This bounds T-001 as well: a win on the declared twin would not show
  the agents help a real operator, and the loss does not show they would not.
- **In fairness to the design:** a declared twin is what a project with no customer and no
  budget can have, the harness says so itself instead of hiding it, and the interface for
  swapping in a real feed was built in advance (ADR-052).
- **Settled by:** session 2 finding what real, permissively licensed history exists (R-13);
  session 3 deciding whether "finished" requires a calibrated world (INS-031, Q-03).
- **Raised by:** Claude Code - Classes. Strengthened by Sequoia Capital- AI, the strongest folder
  on this point. A learner trained in an environment learns the environment, errors included
  (SRC-SEQAI-07, SRC-SEQAI-14, SRC-SEQAI-18). A model that passes a benchmark and fails in use
  has usually fitted the benchmark (SRC-SEQAI-10). The founders of a lab built on simulation
  say their approach holds only where the truth can be computed (SRC-SEQAI-21). The same folder
  offers a partial way out that needs no real data: planted issues with a written rubric
  (INS-042), and a scorer checked against a person's judgment (INS-044). Strengthened again by
  YC AI GUIDE: in production the effort goes into data and not architecture, the reverse of
  SYNAPSE's allocation so far (SRC-LOOSE-01), and the strongest result from a small trained
  model came from a company holding data on hundreds of thousands of machines (SRC-YCAI-03).
  ENGINEERING adds two points: a model of an organisation that is incomplete or stale brings
  down whatever is built on it (SRC-ENG-08), and a gate deferred until a system is large
  becomes harder to pass, not easier (SRC-ENG-03). Fitting the twin to real history costs more
  the more is built on it first.

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
- **Raised by:** Claude code - How to. Sequoia Capital- AI adds that a mismatch between the
  stack a model is trained on and the stack that serves it loses performance without raising
  any error (SRC-SEQAI-18).

### T-013 - Much has been built, and nobody has yet asked for it

- **The corpus says:** building is no longer the scarce thing. The limits are commercial value,
  changing what users actually do, and knowing what is worth building (SRC-CURSOR-02). An
  organisation that can now ship three hundred things has to ask which of them matter
  (SRC-CLASSES-07). Confirm that people have the problem before building (SRC-CLASSES-15), and
  be able to say who depends on it and what workflow it sits in (SRC-POSTS-08).
- **SYNAPSE says:** some twenty sprints, 57 decision records and 68 checks, with no named user,
  no live order pipeline and synthetic traces (read, `README.md`, `CLAUDE.md`).
- **In fairness to the design:** the operator's stated aim is a production system that helps
  many people, and a system of this kind cannot be put in front of a user before it works.
  Building the proof first was also vindicated: the first honest measurement was negative, and
  it is better to learn that from a harness than from a customer.
- **Settled by:** the operator's answers to Q-01 and Q-03 in session 3. Two cheap steps come
  before that: reading what quick-commerce operators publish about their own decisions (R-12),
  and the operator running the twin store personally (INS-035).
- **Raised by:** Posts Context in substance, where it was filed only as INS-018 and Q-01.
  Recorded as a tension at Cursor, which states it most bluntly. Strengthened by Sequoia
  Capital- AI: one company refunded all its revenue on seeing that customers paid without using
  the product daily (SRC-SEQAI-08); the one logistics operator in the corpus found the deciding
  component to be 15% of the work (SRC-SEQAI-23); and one report warns that learning machinery
  built before the workflow is settled is debt (SRC-SEQAI-22). The same folder names the way
  through: commit to one workflow that has an incumbent and a measure (INS-045, Q-07).
  Strengthened by YC AI GUIDE: one company's first customer was a novice who could not use
  what the product produced, and it found its market only among practitioners (SRC-YCAI-07);
  another found that engineering output multiplied while selling still needed people in the
  customer's plant (SRC-YCAI-03). In fairness, SRC-YCAI-07 also shows founders with no
  experience of a field succeeding, because they asked its practitioners before building.
  The Pragmatic Engineer adds that software written for nothing would still have to meet its
  users' expectations and pay for itself (SRC-PRAG-11), and an engineer's two years on a
  project that turned out to have a few hundred users (SRC-PRAG-02). ENGINEERING adds a
  consultancy that found a hundred small business clients exhausting and spent two years on a
  product for a problem nobody had (SRC-ENG-13); a deep-tech company whose customers kept
  turning prototypes down as premature (SRC-ENG-10); and a panel's view that no large
  non-technology company has yet shown a clear gain from AI (SRC-ENG-01). South Park Commons
  adds a founder whose company began from a complaint with no picture of how the product would
  change anything, which he now calls arrogance (SRC-SPC-10); thousands of hours on projects
  never released, with no effect (SRC-SPC-09); the warning that a general tool can be pleasant
  and matter to nobody (SRC-SPC-06); and the test that ambition has become delusion when
  customers stop using the product (SRC-SPC-05).
  YC GUIDE adds a team that dropped its product a month before launch because nobody would
  miss it (SRC-YCG-02), and the view that a product that truly works needs no metric to show
  it (SRC-YCG-22).
  Lenny's Podcast adds a product leader with forty agents at hand who says she is out of good
  ideas (SRC-LENNY-05); the advice to ask why people do not use a product before asking why to
  build it (SRC-LENNY-17, SRC-LENNY-22); a project that hired thirty engineers before anyone
  wanted it (SRC-LENNY-15); and the pull test of INS-059 (SRC-LENNY-23).
  a16z adds the order one company followed, users first and its own models later from their
  data (SRC-A16Z-08), and an agentic browser feature that shipped and went largely unused
  (SRC-A16Z-16).

### T-014 - Append-only context, against compacting and clearing it

- **The corpus says:** long-running agents stay reliable by managing what enters the model's
  context: condensing old history, moving bulk output to files, and clearing what is stale
  (SRC-SEQAI-06). A platform team lists context hygiene among the few things a harness still
  owes the model (SRC-SEQAI-02).
- **SYNAPSE says:** runtime context is append-only with a status field, and nothing is removed
  (I-14; read, `CLAUDE.md`).
- **In fairness to the design:** the rule protects a stable cache prefix (I-13) and an honest
  record, and a consensus decision lasts seconds where the corpus's examples run for hours. If
  the context never grows large, the two never meet.
- **Settled by:** session 2 measuring how large the runtime context gets in one decision, and
  whether anything long-running accumulates it (R-36).
- **Raised by:** Sequoia Capital- AI. Repeated in YC AI GUIDE, where a history of agent
  scaffolding treats editing and clearing context as an advance over append-only growth
  (SRC-YCAI-10). Jane Street adds evidence from a study of prompting: adding to a failing
  prompt made results worse, and the model began ignoring parts of what it had been given
  (SRC-JANE-02).

### T-017 - "Quality is not a gate", against a project governed by gates

- **The corpus says:** correctness is built in when software is constructed, by types and
  specifications that make wrong states impossible. Gates at the exit catch late what should
  have been impossible, and give a comforting picture (SRC-PRAG-10).
- **SYNAPSE says:** it is governed by some 68 mechanical checks and a strict gate culture (read,
  `README.md`, `CLAUDE.md`). Finding 112, the defect named as the cause of the E5 result,
  passed every one of them: the tests sent a request in a shape the real protocol never sends
  (read, `CLAUDE.md`, E-DQP-02).
- **In fairness to the design:** SYNAPSE also builds correctness in, with strict typing, frozen
  models and a schema on every agent output. The same corpus folder records a hard gate as
  Google's turning point, when release engineers refused every untested change
  (SRC-PRAG-06), and the report's own counter-argument is that layered checks form a sieve
  that catches a great deal.
- **So (inferred):** a gate checks what someone thought to write down. Finding 112 lived in what
  nobody wrote down, where a gate cannot see and a constructed type could have: a request
  envelope typed once, and shared by sender and receiver, would have made the wrong shape
  impossible to write.
- **Settled by:** R-24 (which checks can be made to fail) and R-47 (how each named finding was
  caught: by a gate, by construction, by measurement, or by someone reading).
- **Raised by:** The Pragmatic Engineer.
  Lenny's Podcast adds two warnings: a design leader citing Christopher Alexander, that a system
  can obey all its rules and still be lifeless (SRC-LENNY-14), and a product author who did not
  foresee how often process would be used in place of thinking (SRC-LENNY-17).

## Inside the corpus

### T-006 - Harness over model, or training over prompting?

- SRC-POSTS-01 relays results where a weaker model with an improved harness beat a stronger one.
  SRC-POSTS-05 relays an experiment where training moved accuracy 15-21 points and prompt
  examples less than one.
- **Reading:** they answer different questions. The harness wins when the base model is strong
  and general. Training wins on a narrow job with labelled data. SYNAPSE has both kinds of
  part: a general reasoner in the disruption path, and narrow forecasters and policies.
- **Added later:** YC AI GUIDE has both halves again: a harness change on fixed weights
  (SRC-YCAI-10), and a small trained model beating a general one where the company held the
  data (SRC-YCAI-03). Jane Street adds a case where training a small model did not close the
  gap to a general one (SRC-JANE-02), with the advice to run a baseline that involves no
  training first (INS-021). South Park Commons adds a video company that trains a missing
  capability into its next model in a few weeks rather than wrapping the current one
  (SRC-SPC-07).
  YC GUIDE adds a legal AI company that bet on general models improving and built orchestration
  and an evaluation suite instead of training its own model (SRC-YCG-10).
  a16z adds two sides. A health researcher who built specialised models says a forked model
  falls behind the frontier within months (SRC-A16Z-12); a coding company won by betting on
  the interface rather than its own model (SRC-A16Z-08). Against them, a large model can
  train a small one to take over a narrow task (SRC-A16Z-22).

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
- **Added by YC AI GUIDE:** SRC-YCAI-11 argues for spending hundreds of dollars a day on
  tokens, and its own report notes that an individual cannot. The same folder supplies the
  route that fits a fixed plan: a strong model used offline to tune a cheap local stack that
  then runs alone (SRC-YCAI-10), and local models for everyday queries (SRC-YCAI-13). See
  INS-040. ENGINEERING adds that companies moved within months from using models freely to
  accounting for every token (SRC-ENG-01).
  YC GUIDE argues three times for spending freely, since prices fall roughly tenfold a year
  (SRC-YCG-01, SRC-YCG-06, SRC-YCG-14). For a fixed $300 credit the reading above stands.
  a16z adds that agents stopped for wasting tokens on dead ends far outnumber those stopped
  for unsafe behaviour (SRC-A16Z-09), and that a model cheaper per token can cost more per task
  (SRC-A16Z-15). Count cost per decision.

### T-010 - A few general tools plus code, or one purpose-built tool?

- SRC-CLASSES-01 replaces twelve special tools with three general ones and lets the agent write
  code against the data. SRC-CLASSES-05 does the reverse: it replaces an agent's wandering
  through general tools with one deterministic tool that returns the structured answer.
- **Reading:** both are cutting what reaches the model's context. General tools suit a model
  that can safely write code over the data. A fixed tool suits a multi-step loop that keeps
  recurring and whose result must be the same every time. SYNAPSE's agents are of the second
  kind, which is consistent with INS-008.

### T-011 - Give the agent a large goal, or work in small verified steps?

- SRC-CLASSES-07 and SRC-CLASSES-04 report that agents do best with large, well-specified goals
  they decompose themselves. SRC-POSTS-04 says to shrink the change until the first step can be
  verified.
- **Reading:** state the goal large and verify small. The person stops doing the decomposition
  and keeps doing the checking. For the ten implementation sessions this means one outcome per
  session with stated success criteria, and commits at each verified step inside it. The
  last spec's 155 leaf tasks were the opposite arrangement (read, `HANDOFF.md`).
- **Added by YC GUIDE:** the creator of Claude Code names over-specifying how as the common
  failure of experienced engineers; state the goal, the limits and the exit criteria, and give
  the model a way to verify as it goes (SRC-YCG-05). That is the reading above.
  Rainmatter adds that building and measuring have sped up and learning has not, so work handed
  to agents should come back in steps a person can follow (SRC-RAIN-05).

### T-015 - Launch before it is ready, or be finished before the first pilot?

- SRC-YCAI-07 sold its product before it was hosted, and treats an early public commitment as
  the way to get anything shipped. SRC-YCAI-03 and SRC-YCAI-09 hold that in their fields an
  unfinished product in front of a customer spends trust that does not come back.
- **Reading:** the first report states the boundary itself. Shipping early holds where a person
  reviews the output and a failure can be repaired by hand. It fails where a miss is costly and
  nobody stands between the system and the consequence. SYNAPSE can be either. As an adviser
  whose recommendation a person accepts or changes, it is the first kind and should reach a
  user early (INS-022, INS-035). As an actor placing orders by itself it is the second, and
  the bar is the one in INS-047.
- **Added by The Pragmatic Engineer:** a rewrite shipped despite a load test that had found
  reads and writes blocking each other, and the company never recovered (SRC-PRAG-11); a
  delivery team sent each release first to a population large enough to show problems and
  small enough that a mistake cost little (SRC-PRAG-03). The second is this tension's
  boundary applied to rollout.
- **Added by YC GUIDE:** Stripe held its public launch for almost two years but had a live
  production user within two months (SRC-YCG-13), which reconciles the two sides: delay the
  launch, not the first real user. A legal AI company froze all sales for six months because
  in its field one failure loses a customer for good (SRC-YCG-10). Waymo's demonstration came
  after eighteen months and commercial service fifteen years later; each further nine of
  reliability cost about ten times the last (SRC-YCG-25). Against waiting: shipping pace is
  the best predictor Paul Graham knows, and action produces information (SRC-YCG-14,
  SRC-YCG-11, SRC-YCG-06).

### T-016 - Give the agent everything, or keep what it must read small?

- SRC-YCAI-12 and SRC-YCAI-06 report better results from handing an agent the complete raw
  record of a project. SRC-POSTS-04 and SRC-CLASSES-14 say standing prose costs reasoning on
  every task and long files go unread.
- **Reading:** they are about different stores. What loads into every session should be small
  and should be rules. The full record belongs on disk, where an agent reads the part a task
  needs, as in the tiers of SRC-YCAI-10. `CLAUDE.md` mixes the two: rules and live error
  patterns, with 49% history (measured). That is the case for Q-04, and it is how this folder
  is built: a short index, with the detail one file away.
- **Added later:** South Park Commons adds the coding agent's own team: the expected route to
  whole codebases was ever larger context windows, and what worked was a model that searches
  for the files it needs (SRC-SPC-04). That supports the reading above.
  Lenny's Podcast adds that a million-token context holds less than half a per cent of one
  company's call transcripts, so the full record cannot be loaded anyway (SRC-LENNY-21).
  a16z adds a personal agent whose notes file kept losing what tools it had until it was told
  to read its memory before answering (SRC-A16Z-23).

### T-018 - Do types help agents, or only cost tokens?

- SRC-JANE-01 and SRC-PRAG-10 treat a strong type system as feedback that tells agents and
  people what must hold, and makes wrong states impossible to write. SRC-ENG-09 reports a
  comparison across thirteen languages in which static types gave agents no gain in token cost
  or speed.
- **Reading:** the comparison measured what types cost, in tokens and time, not what they
  prevent, in defects that reach run time. For SYNAPSE the costliest defect so far was a
  request in the wrong shape, which a type shared by sender and receiver would have stopped
  (T-017). Here the benefit outweighs the cost, and the strict typing and frozen models stay.

### T-019 - Evaluations first, or intuition until the product exists?

- SRC-SPC-04 holds that evaluations do little for a product's first version, where fast
  iteration and intuition lead. They matter at scale, and some failures are seen only in use.
  SRC-SPC-08 and INS-033 hold that the evaluation is the bottleneck: once one exists,
  improvement follows fast.
- **Reading:** they judge different claims. Whether anyone wants a product is settled by users,
  not by an evaluation, and an early evaluation of it measures the builder's guesses. Whether a
  decision system beats a tuned rule is a claim only an evaluation can settle, and it can be
  written before any user exists. SYNAPSE makes both claims. The proof harness is the right tool
  for the second, and nothing in it answers the first (Q-01, T-013). The risk for the ten
  sessions is to keep improving the harness because it is the part that can be measured.
- **Added by Lenny's Podcast:** for a first version the signal is how people react when shown
  the prototype, not usage metrics (SRC-LENNY-16), and users never care about benchmark scores
  (SRC-LENNY-15). On the other side, evaluations should start with a handful of hand-judged
  cases and grow from there (SRC-LENNY-25). Both fit the reading above.

### T-020 - Let the agent wrap the tools, or wrap the model in deterministic checks?

- SRC-YCG-05, SRC-YCG-23 and SRC-YCG-26 hold that a tight harness cripples a capable model: give
  it tools and a goal, and let the agent wrap deterministic software rather than sit in a small
  box inside it. SRC-YCG-02 and SRC-YCG-25, with the many sources of INS-008, put a
  deterministic harness around the model: compliance rules for banking agents, an onboard check
  on every driving output.
- **Reading:** both sides put the check in the same place, at the boundary where an action
  leaves the system, and differ on how much freedom the reasoning gets inside it. Brex's proxy
  (SRC-YCG-23) is the clearest case of both at once: the agent acts freely, and every outbound
  request passes rules learned from recorded traffic or a model judge. Freedom fits work whose
  output is checked before it matters, such as code under tests. Where an action moves money
  or stock, the outer check is not optional. SYNAPSE already has this shape, agents reasoning
  inside and guardrails on each world action; what it lacks is a guardrail grounded in the
  store's own history (R-42).
