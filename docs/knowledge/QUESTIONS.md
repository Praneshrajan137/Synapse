# Questions

Two lists. **Q** items are decisions only the operator can make. **R** items are research for
the coming sessions; each says what answer would change a plan.

Nothing here is resolved by being written down. An item leaves this file when its answer is
recorded with how it was obtained.

## For the operator

| ID | Question | Why it is owed | From |
|---|---|---|---|
| Q-01 | Who is the first named user of SYNAPSE, and what do they do with it on an ordinary day? | "Help millions of people" names no workflow. The README says there is no live order pipeline and the traces are synthetic. Session 3 cannot define finished without this. One candidate, inferred and not a recommendation: three documents in folder 3 show agents of this kind serving small and mid-sized retailers and merchants, who are many, and not the few large quick-commerce operators, who build their own. | INS-018 |
| Q-02 | How much of the $300 GCP credit remains, and when does it expire? When do the 200 Colab units expire? | Trial credit and compute units both lapse on a clock. `CLAUDE.md` records GCP deploys since at least June 2026, so the balance and date need reading from the billing console. Session 3's budget depends on it. | INS-019 |
| Q-03 | Is "finished" a product someone operates, a reference implementation others learn from, or the proof harness offered for other decision systems? And if a product: does it act, or does it first advise in shadow beside the operator's own rules? | The readings need different work and different deployments. A shadow advisor is the lowest-risk first form, and it leans hardest on the twin's fidelity. | T-004, INS-022 |
| Q-04 | May the sprint history move out of `CLAUDE.md` into `docs/`, leaving rules and live error patterns? | 49% of the file is history and it loads every session (measured). `CLAUDE.md` is the governance source of truth, so this is the operator's call. The `doc_truth` pins would move in the same change. | INS-014, T-005 |
| Q-05 | For the larger, less relevant corpus folders (product and market, about 3.1 MB), full reads in the main context, or a cheaper reader filling the same card format with spot checks? | Full reads of the remaining corpus are roughly 1.1M tokens (estimated from word count) on a fixed plan. The cheaper path costs fidelity. | INS-015 |
| Q-06 | May a gate, a document or a component be retired when removing it changes no measured outcome? | The corpus is firm that process piles up unless someone is given explicit permission to delete. Only the operator can give it here. | INS-030 |

## For session 2 (the project itself)

| ID | Question | The answer that changes a plan | From |
|---|---|---|---|
| R-01 | After PR #87, does any consensus decision change when the world state changes? Do all eight handlers consume world state? | If not, the repair is incomplete and no uplift claim is possible. | INS-010 |
| R-02 | What did the shocked cells show in E5 and the controls, and did they run? | If only the unshocked cell was measured, the headline covers the regime where a tuned control is strongest. | INS-003 |
| R-03 | For each of information, coordination and adaptation: which scenario cell should show the uplift, and which arm isolates it? Does any arm give one policy the consensus arm's information and compute? | If no cell can be named for a mechanism, that mechanism is not a reason to keep its machinery. | INS-001, INS-002, T-003 |
| R-04 | List every seam (A2A request envelope, each Kafka topic, each firehose channel). Which have a test that drives the producer's real message? | Seams without one are where the next finding-112 hides. | INS-005, T-007 |
| R-05 | Which outbound calls have no deadline shorter than their tier budget? | Each is a possible repeat of finding 116. | INS-006 |
| R-06 | Do `orchestrator/llm/ollama_client.py` and `agents/disruption_shield/models/reasoning.py` share one client? | If not, a single seam is cheap work that removes a class of defect. | INS-007 |
| R-07 | Is there any path where model text drives an action with no deterministic validator between? | Each is a place to add one. | INS-008 |
| R-08 | Where can the whole system run for verification inside the budget? Can `scripts/deploy/verify_live.py` target a local or thin-slice stack? | If the only place is the GCP VM, the implementation sessions are paced by its three-hour window and by credit. | INS-013 |
| R-09 | Split the last 300 commits by path: product code against gates and documents. | Gives the real share of product work behind the prefix mix (75 of 300 `feat`). | INS-020 |
| R-10 | What is the smallest set of files a session must read to start correctly, and what does it cost in tokens? Is `docs/state/MODULE_INVENTORY.md` (last committed 2026-06-08) current enough to be that starting map? | Sets the reading budget for all later sessions. | T-005, INS-025 |
| R-11 | How separable is the uplift harness from this twin? | Decides whether T-004 is a real option. | T-004 |
| R-16 | Does debate now change proposals, and does arbitration now bind? What would ablation arms (consensus without debate; without arbitration) cost to add to the harness? | If a stage changes nothing, it is cost. If the arms are cheap, they turn T-001 from an argument into a measurement. | INS-023 |
| R-17 | Write the expected trace for one consensus decision after PR #87, then compare it with a real one, stage by stage. | Any stage that does not consume what it should is a defect of the finding-112 class, found in an hour and not in a CI run. | INS-024 |
| R-18 | Can an agent issue a `WorldAction` outside its function, such as `inject_disruption`? What enforces the answer? | If nothing does, a per-agent allow-list is small work that removes a class of failure. | INS-027 |
| R-19 | What does the Disruption Shield's reasoner return when offline, and which decisions would take the model path in a live system? | Decides how much of the system the E5 headline covers. | T-009 |
| R-21 | What share of consensus decisions run with at least one degraded agent, and what are the reasons, ranked? | The top reason is a candidate for the first implementation session. If the share is high, the E5 headline measured a mostly degraded system. | INS-037 |
| R-22 | For each of the eight agents: does it hold its own objective, state and loop, or is it a function the orchestrator calls? How often does arbitration face a real trade-off between agents' objectives? | Agents that are functions can become tools without loss. If objectives rarely conflict, the case for separate agents rests on little. | INS-028 |
| R-23 | Does anything learn from operator overrides in `audit_escalations`? | If not, the system discards its only human labels. | INS-032 |
| R-24 | Which of the 68 checks can the falsification sweep (C72) make fail, and which not? What is the state of its open defect? | A check that cannot be made to fail is a candidate for repair or retirement (Q-06). | INS-033 |
| R-25 | Does the uplift harness store replicate results by seed, arm and source digest? What invalidates them? | If not, content-addressed caching could cut the cost of every later verification round. | INS-036 |
| R-26 | Do all agents in one decision read the same frozen world snapshot, and how are several agents' writes to the world ordered? | If each agent reads the world at a different moment, their proposals answer different questions. | INS-010 |
| R-27 | Can a world action be undone or compensated (cancel a reorder, restore a price), and can the world be snapshotted and rewound? | An action kind with a cheap undo can be granted autonomy early; one without needs a person or a longer record first. | INS-009 |
| R-28 | Facing an escalation, can an operator change part of a recommendation (a quantity, a price multiplier), or only accept or reject? | If only accept or reject, the console makes an approver of its operator and loses the richer label an edit would give. | INS-038 |
| R-20 | Which recorded limits still hold with the current model and tools (no repo-wide or simulation runs on the laptop, mutation testing flaky on Windows)? Retest one. | A limit that no longer holds is free capacity for the implementation sessions. | SRC-HOWTO-01 |

## For sessions 2 and 3 (outside the repository)

| ID | Question | The answer that changes a plan | From |
|---|---|---|---|
| R-12 | What do quick-commerce operators publish about how they decide stock, assortment and dispatch? | The posts read so far cover only those companies' internal engineering agents. Without this, SYNAPSE's problem statement rests on assumption. | Q-01 |
| R-13 | Which real, permissively licensed dataset could anchor the twin? | The handoff records the twin's fidelity as unknown, so a result on it does not transfer. An earlier dataset's terms were declined. | INS-018 |

## Found in passing

Not from the corpus; noticed while reading the repository. Recorded so they are not lost.

| ID | Observation | How known |
|---|---|---|
| R-14 | `README.md` line 66 says 38 architecture decision records; `docs/adr/` holds 57 files named `ADR-*`, the latest ADR-057. The line sits outside the generated block, so no gate checks it. | Measured, 2026-11-13, `origin/main` `d4f985c` |
| R-15 | The README table row for GCP says the code "lives on `feat/gcp-primary-deployment`" awaiting a PR, while `CLAUDE.md` records that work as landed. | Read; not checked against git history |
