# Questions

Two lists. **Q** items are decisions only the operator can make. **R** items are research for
the coming sessions; each says what answer would change a plan.

Nothing here is resolved by being written down. An item leaves this file when its answer is
recorded with how it was obtained.

## For the operator

| ID | Question | Why it is owed | From |
|---|---|---|---|
| Q-01 | Who is the first named user of SYNAPSE, and what do they do with it on an ordinary day? | "Help millions of people" names no workflow. The README says there is no live order pipeline and the traces are synthetic. Session 3 cannot define finished without this. | INS-018 |
| Q-02 | How much of the $300 GCP credit remains, and when does it expire? When do the 200 Colab units expire? | Trial credit and compute units both lapse on a clock. `CLAUDE.md` records GCP deploys since at least June 2026, so the balance and date need reading from the billing console. Session 3's budget depends on it. | INS-019 |
| Q-03 | Is "finished" a product someone operates, a reference implementation others learn from, or the proof harness offered for other decision systems? | The three need different work and different deployments. | T-004 |
| Q-04 | May the sprint history move out of `CLAUDE.md` into `docs/`, leaving rules and live error patterns? | 49% of the file is history and it loads every session (measured). `CLAUDE.md` is the governance source of truth, so this is the operator's call. The `doc_truth` pins would move in the same change. | INS-014, T-005 |
| Q-05 | For the larger, less relevant corpus folders (product and market, about 3.1 MB), full reads in the main context, or a cheaper reader filling the same card format with spot checks? | Full reads of the remaining corpus are roughly 1.1M tokens (estimated from word count) on a fixed plan. The cheaper path costs fidelity. | INS-015 |

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
| R-10 | What is the smallest set of files a session must read to start correctly, and what does it cost in tokens? | Sets the reading budget for all later sessions. | T-005 |
| R-11 | How separable is the uplift harness from this twin? | Decides whether T-004 is a real option. | T-004 |

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
