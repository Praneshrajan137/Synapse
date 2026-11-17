# VERDICTS - session 2's verdict on every reading of SYNAPSE in this folder

Session 1 read SYNAPSE mostly through the `decision-quality-proof` documents and said every
reading was provisional. Session 2 (2026-11-16 to 2026-11-20) tested them against the code, by
running it where it could. This file records the verdict on each, so the ledger keeps its
history and a reader can see what still holds.

**Verdicts.** *Confirmed* - the reading holds. *Corrected* - it holds in part, or the facts
moved. *Refuted* - it does not hold. *Open* - not tested; the next owner is named.
*No reading* - the entry gives guidance and makes no claim about SYNAPSE.

**Evidence.** `LOG` and `MAP` mean [`docs/truth/LOG.md`](../truth/LOG.md) and
[`docs/truth/TRUTH-MAP.md`](../truth/TRUTH-MAP.md); the entry named there gives the command or
the file and line. Unless an entry says otherwise, statements about code describe the repaired
tree of pull requests #87 and #91 (`1c484fb`), which is not merged into `main`.

## 1. The ten in SYNTHESIS.md

| # | Reading | Verdict | What session 2 found | Evidence |
|---|---|---|---|---|
| 1 | No named user; finished cannot be defined | Confirmed | Still no named user. The operator set the reviewers' frame on 2026-11-17: they judge the work as a whole | LOG OA-4 |
| 2 | Earn the complexity against the tuned rule; the consensus lost by 4.40 | Corrected | 4.40 measured the system before the repair. After it the loss is 1.45 (E5) and 1.40 in a local twelve-replicate run, worse in 12 of 12. The consensus is, in practice, one agent's reorder rule, and most of the loss is one of its levels | LOG RD-01, M-19, M-23, M-24 |
| 3 | Land on one workflow first | Confirmed, sharpened | In practice the system already is one workflow: every traced decision was a reorder bound by the Inventory Sentinel | MAP F-01 |
| 4 | A proof that can fail, against a scorer a practitioner accepts | Corrected | The harness can fail and repeats exactly. But its weights are the measured agent's own default costs; 55% of the tuned rule's cost does not depend on any decision; and its "room to win" rests on a clairvoyant ceiling | LOG V-11, M-23; MAP F-14a, F-29 |
| 5 | A twin earns belief only when realistic and fitted | Confirmed, extended | Besides ten uniform items and one stock number per item: spoilage is a clock that consumes no stock and responds to no decision | LOG M-25; MAP F-30 |
| 6 | Grant autonomy by reversibility, not confidence alone | Confirmed, extended | No reversibility concept exists. Below the confidence floor nothing executes, and nothing executes after a person approves either | LOG M-10, V-04 |
| 7 | Operate the twin store yourself with SYNAPSE advising | Open | Harder than read: no documented command starts a stack that decides, and an approved escalation enacts nothing. Owner: the implementation sessions | MAP F-08, F-19 |
| 8 | Verification is the constraint; give agents a production-like run | Corrected | The decision path and E5's physics run on the laptop: 0.6 s a replicate, the trace byte-identical to CI. The full stack runs nowhere | LOG M-18, M-23; MAP F-19 |
| 9 | Deletion is an experiment | Confirmed | Now cheap: an ablation arm costs minutes locally | LOG M-23 |
| 10 | Show what reaches the customer, the reasons, and only what ran | Corrected | `CLAUDE.md`'s "six of eight `execute()` do not act" is out of date, but one of the eight acts by changing customer demand; the live path enacts every proposer's own proposal, not the selected one; no outcome can be recorded as anything but unknown | LOG M-11, V-03, V-06, V-09 |

## 2. Each ledger entry's reading of SYNAPSE

| Entry | Verdict | Finding | Evidence |
|---|---|---|---|
| INS-001 | Corrected | The result after the repair is -1.45, not -4.40. No arm gives one policy the consensus arm's information, but the consensus arm is itself one policy in practice | LOG RD-01, M-19 |
| INS-002 | Corrected | On the primary cell only information can show uplift, and the better-informed classical arm gains 0.25, below the 0.4 margin. Coordination has nothing to act on (one store, no transfers, waste independent of stock). Adaptation needs shocks E5 does not run | MAP F-29 |
| INS-003 | Confirmed | E5 is defined for the primary cell under a neutral shock only (`uplift/e5_suite.py:189-202`). Four adversarial scenarios exist; no consensus run on them was found | LOG R-02 row below |
| INS-004 | No reading | Guidance for training on Colab | - |
| INS-005 | Open | Seam inventory not made. Owner: the first implementation session that touches a seam | - |
| INS-006 | Confirmed | Finding 116 as read; deadlines per call not listed (R-05) | - |
| INS-007 | Confirmed | Two separate clients: the orchestrator's and the Disruption Shield's reasoner | reported by a mapping subagent |
| INS-008 | Confirmed in part | The orchestrator's LLM writes analysis text and never changes a proposal or the selection (reported). The Disruption Shield's reasoner was not examined | MAP F-24 |
| INS-009 | Confirmed | No reversibility concept in `orchestrator/` | LOG M-10 |
| INS-010 | Corrected | After the repair, decisions do change with the world, but only through the Sentinel. Five of six proposers return the same score in all 360 states; two never propose, because the request E5 builds lacks their inputs (one of them a `store_id`) | LOG M-19, M-30 |
| INS-011 | Corrected | A replicate costs 0.6 s locally; E5's 2,000 runs are about twenty minutes here. Decisions are deterministic, so one-step replay is sound | LOG M-23 |
| INS-012 | Corrected | CI is the critical path for the gates, not for decisions or the proof | LOG M-18, M-23 |
| INS-013 | Corrected | The whole system runs nowhere today. The decision path and the proof run in-process on the laptop | MAP F-19 |
| INS-014 | Confirmed | `CLAUDE.md` is 68,472 bytes on `main`, 69,250 on PR #87 | measured |
| INS-015 | No reading | Method; followed | - |
| INS-016 | No reading | Session 3 | - |
| INS-017 | No reading | Session 3 | - |
| INS-018 | Confirmed | No user named | LOG OA-4 |
| INS-019 | Corrected | The cloud compose file defines 23 services plus the LLM server on the host (reported); no machine exists now | LOG OA-1; MAP F-22 |
| INS-020 | Confirmed | Split by path done (R-09) | LOG M-05 |
| INS-021 | No reading | Note: only two of eight agents have a training loop that takes gradient steps (reported) | MAP F-12 |
| INS-022 | Corrected | E5 applies only the selected action in its own twin; the live path enacts every proposer's own proposal. No shadow mode was looked for again | LOG V-03 |
| INS-023 | Corrected | Debate and full arbitration run only in tiers 3 and 4, which autonomous operation never reaches. Where they ran, they chose the same agent and the same order | LOG M-20, M-21, V-01, V-05 |
| INS-024 | Confirmed | The expected trace was written and compared (R-17) | MAP section 1 |
| INS-025 | Open | `MODULE_INVENTORY.md` not re-read. Owner: session 3 (R-10) | - |
| INS-026 | No reading | Rule G8; this session learned the same lesson again | LOG D-03 |
| INS-027 | Confirmed | `WorldAction` has no agent field; no allow-list found in the world or orchestrator packages | LOG R-18 row below |
| INS-028 | Answered | All eight are components, not agents: none holds a loop or an objective between calls (reported); objectives never conflicted in the measured path because five proposals were constants | MAP F-02, F-12 |
| INS-029 | No reading | - | - |
| INS-030 | Confirmed | No retirement path for gates or records found; Q-06 open | - |
| INS-031 | Confirmed, extended | Declared twin; a CC BY 4.0 dataset with hourly stock status exists (FreshRetailNet-50K) | LOG EX-03 |
| INS-032 | Corrected | Nothing learns from overrides, and an approved escalation enacts nothing | LOG V-04 |
| INS-033 | Answered in part | This session injected faults into the decision core itself (LOG M-26); the falsification sweep of the 68 checks was not read | LOG M-26 |
| INS-034 | No reading | - | - |
| INS-035 | Corrected | The console surfaces exist, but no stack runs, and the cockpit's approval enacts nothing | MAP F-08, F-19 |
| INS-036 | Corrected | Replicates are exact functions of their seed, so content addressing is sound; how results are stored was not read | LOG M-23 |
| INS-037 | Answered | Every decision carries degraded agents, the binding one included; the top reason is no calibrated model or feature source; nothing ranks or acts on the reasons, and the confidence gate does not read the flag | LOG M-31; MAP F-02a |
| INS-038 | Answered | An operator can neither release nor amend a withheld decision | LOG V-04 |
| INS-039 | Answered | The Sentinel reads position (on hand plus on order), demand to date, elapsed time, landed lead times by supplier and the item-supplier map; the sensor reads stock levels only | R-37 row below |
| INS-040 | Strengthened | A searched policy can be scored locally at 0.6 s a replicate; seeds must be held out (LOG M-24 shows how fast a fitted setting closes the gap) | LOG M-23, M-24 |
| INS-041 | Open | Reward-safety tests not read (R-34) | - |
| INS-042 | Corrected | `uplift/scenarios.py` holds four scenarios (demand spike, supplier default, monsoon, cold start). No rubric of what a correct response must do was seen | LOG R-38 row below |
| INS-043 | Open | Separability not measured; the harness drives the twin's engine and reads its policy file directly (read), so it is not separable without work | - |
| INS-044 | Answered | The weights are the Sentinel's own default costs (8 for unfilled demand, 1 for stock and spoilage) and one chosen weight (delivery). No outside source | LOG V-11 |
| INS-045 | Corrected | `CLAUDE.md`'s statement on six `execute()` methods is out of date (LOG M-11) | LOG M-11 |
| INS-046 | Answered | A twin check of the proposed action exists and runs, in tier 4 only; autonomous operation never reaches it | LOG M-20, M-21, V-05 |
| INS-047 | Answered | Nothing executes below the gate; the tuned rule is not a fallback | LOG V-04 |
| INS-048 | Open | Fourteen routes counted; the console has not been walked running | LOG M-13 |
| INS-049 | Answered | 0.6 s per 24-hour replicate with the consensus arm | LOG M-23 |
| INS-050 | Open | The sweep's bound on surprising wins not read (R-46) | - |
| INS-051 | Answered | Identical on repeat (24 of 24) and across machines (the trace) | LOG M-18, M-23 |
| INS-052 | Answered | `uplift/harness.py::observe` gives an arm current state and history to date only; the forecaster has no fitted model on E5's path | R-44 row below |
| INS-053 | Corrected | Waste consumes no stock, so stock is not conserved against spoilage | LOG M-25 |
| INS-054 | Open | Sprint 6 A/B assignment not read (R-49) | - |
| INS-055 | Confirmed | Four action kinds; in the harness only price and reorders move the twin, routing and disruption actions are recorded and not applied (`uplift/harness.py::_apply_action`) | read in source |
| INS-056 | Open | Mission Control's order not re-read; the console not walked | - |
| INS-057 | Strengthened | Tuning one level already removes most of the gap (LOG M-24); imitation of the tuned rule is the safer start for any learning | LOG M-24 |
| INS-058 | Confirmed | One stock number per item (`WorldState.inventory`) | read in source |
| INS-059 | Confirmed, sharpened | On the primary cell even the structure-aware rule gains 0.25 against a 0.4 margin: pull, if it exists, is where the rule's assumptions break | MAP F-29 |
| INS-060 | Confirmed | Ten items in E5's traced world, drawn uniformly | LOG M-09, M-16 |

## 3. Tensions

| Tension | Verdict |
|---|---|
| T-001 | Settled for now on other ground: on the measured path the eight do not coordinate at all; one decides. A subagent reported that the source paper finds its error-amplification contrast (4.4 against 17.2) not significant after controls; the main session confirmed only the abstract's direction, so the sentence in T-001 is to be read with that caveat |
| T-002 | Confirmed: 23 services declared, none running anywhere |
| T-003 | Settled in part: the architecture adds no information on the measured path. Uplift needs information or structure the rule lacks, not more stages |
| T-004 | Reframed by the operator: the reviewers judge the work as a whole (OA-4) |
| T-005 | Unchanged; `CLAUDE.md` 68,472 bytes on `main` |
| T-009 | Confirmed and widened: the measured path is tier 2, which never calls an LLM; the model is reachable only in debate (tiers 3 and 4) |
| T-012 | Confirmed; a candidate dataset is named (LOG EX-03) |
| T-013 | Unchanged |
| T-014 | Open (R-36) |
| T-017 | Corrected in part: five faults introduced into the decision core were all caught by its own tests (LOG M-26). The gates guard what someone wrote down, as T-017 says, and here what was written down includes the safety behaviour. They do not judge whether a decision is good: a change that removes most of E5's loss fails the same test a harmful one would |

## 4. Questions

### For the operator

| ID | Status |
|---|---|
| Q-01 | Open. Memo in `docs/truth/DECISIONS.md` |
| Q-02 | Answered by the operator on 2026-11-15 and 2026-11-17: a new account with the full $300, not yet connected; spending before the release is allowed with every machine turned off after each use (LOG OA-2, OA-3) |
| Q-03 | Answered in part: the reviewers judge the work as a whole (OA-4). Whether the product acts or advises: memo |
| Q-04 | Open. Memo |
| Q-05 | Retired: the corpus was read in full in session 1 |
| Q-06 | Open. Memo |
| Q-07 | Open. Memo; evidence: in practice the system already is replenishment alone |
| Q-08 | Open. Memo |

### Research items

| ID | Status | Answer, or the reason and the owner | Evidence |
|---|---|---|---|
| R-01 | Answered | Decisions change with the world only through the Sentinel; five proposers return constants in all 360 states; two never propose | LOG M-19 |
| R-02 | Answered | E5 and its controls run the primary cell under a neutral shock only. A shocked decision costs about a hundred times more and changed no order in six paired states | LOG M-21; `uplift/e5_suite.py:189-202` |
| R-03 | Answered in part | Information is the only mechanism the primary cell can show; coordination and adaptation need structures or shocks it lacks. The cell list is session 3's | MAP F-29 |
| R-04 | Open | Owner: the implementation session that changes a seam | - |
| R-05 | Open | Partly reported: the LLM call allows two attempts of 30 s; the twin check is capped at 8 s. Owner: implementation | reported |
| R-06 | Answered | No: two clients | reported |
| R-07 | Answered in part | Not in the orchestrator; the Disruption Shield's reasoner not examined | reported |
| R-08 | Answered | Nowhere for the whole system; in-process on the laptop for decisions and the proof | MAP F-19; LOG M-18 |
| R-09 | Answered | 22.3% core and console source over all history; 8.2% since late July | LOG M-05 |
| R-10 | Open | Owner: session 3 | - |
| R-11 | Answered in part | Not separable without work: the harness drives the twin's engine and reads its policy file | read in source |
| R-16 | Answered | Debate and arbitration change nothing measured where they run, and never run in autonomous operation. Ablation arms now cost minutes | LOG M-20, M-21, M-23 |
| R-17 | Answered | Expected and actual trace compared stage by stage | MAP section 1 |
| R-18 | Answered | No allow-list; no agent field on `WorldAction` | read in source |
| R-19 | Open | PR #87 gives the reasoner an offline mode for E5 (read). Owner: implementation | - |
| R-20 | Answered | "No simulation runs on the laptop" does not hold for the decision path or the proof | LOG M-18, M-23 |
| R-21 | Answered | All of them: in 24 of 24 decisions five proposers, the binding Sentinel among them, report `degraded=True` with basis `fallback_floor`; the gate does not read the flag | LOG M-31 |
| R-22 | Answered | Eight components | MAP F-12 |
| R-23 | Answered | Nothing learns from overrides | LOG V-04 |
| R-24 | Open | The sweep was not read; the decision core's own tests were faulted instead | LOG M-26 |
| R-25 | Answered in part | Replicates are exact functions of the seed; storage not read | LOG M-23 |
| R-26 | Answered | One request object is sent to all agents; execution and learning read the world again separately (reported) | reported |
| R-27 | Open | No reversibility concept (LOG M-10). Owner: implementation | - |
| R-28 | Answered | No | LOG V-04 |
| R-29 | Answered | See INS-044 | LOG V-11 |
| R-30 | Answered | 0.6 s per replicate; in the full path the twin check takes most of the time | LOG M-21, M-23 |
| R-31 | Answered | Tier 4 only | LOG M-20, M-21 |
| R-32 | Answered | Nothing | LOG V-04 |
| R-33 | Answered in miniature | 0 of 12 | LOG M-23 |
| R-34 | Open | Owner: the implementation session that trains a policy | - |
| R-35 | Answered | No outcome can be `diverged` on the live path, so no such route can carry anything | MAP F-10 |
| R-36 | Open | Owner: implementation | - |
| R-37 | Answered | See INS-039 | `agents/inventory_sentinel/inference/request_state.py` |
| R-38 | Answered in part | Four scenarios; no rubric seen | `uplift/scenarios.py` |
| R-39 | Answered in part | Fourteen routes; walk pending | LOG M-13 |
| R-40 | Answered | One cause dominates: the Sentinel's level after deliveries land | LOG M-24 |
| R-41 | Answered | E5 uses a fixed seed list, and a setting fitted to it closes most of the gap within minutes, so any search must hold seeds out | LOG M-24 |
| R-42 | Answered in part | The five guardrails (privacy, price cap, rider shift, confidence floor, service level) compare nothing with store history or the incumbent; `WorldAction.params` carries bare floats | reported; read in source |
| R-43 | Answered | Identical | LOG M-23 |
| R-44 | Answered | No leakage found in what an arm observes | `uplift/harness.py::observe` |
| R-45 | Open | Owner: implementation | - |
| R-46 | Open | Owner: session 3 | - |
| R-47 | Open | Owner: session 3; the finding bodies are in the proof spec's ledger | - |
| R-48 | Answered in part | Waste consumes no stock; scenario contents listed | LOG M-25 |
| R-49 | Open | Owner: whichever session runs a live comparison | - |
| R-50 | Answered in part | One decision per city per breach; cities polled in turn; one protocol object shared with the API (reported) | reported |
| R-52 | Open | Owner: implementation | - |
| R-53 | Answered in part | One store in E5; lost sales; no substitution or transfer | MAP F-30 |
| R-54 | Open | Owner: implementation | - |
| R-55 | Answered | One stock number per item | read in source |
| R-57 | Answered | No documented path yields a decision on screen today; in-process, a decision takes 0.02 s | MAP F-19 |
| R-58 | Answered | By term, the tuned rule's gap to the oracle is 0.39 in stock held and 0.24 in unfilled demand; no item or store slice exists | MAP F-29 |
| R-59 | Answered in part | Ten uniform items in E5's world; scenario cells change multipliers, not the mix | LOG M-16; `uplift/scenarios.py` |
| R-61 | Answered | The Terraform's daily stop, the hand-attached morning window, the weekly deploy and watchdog crons, and the stop after a scheduled deploy; moot until an environment exists | reported; LOG OA-1 |
| R-12 | Answered in part | Scale is published; method mostly is not | `docs/truth/FRONTIER.md` |
| R-13 | Answered in part | FreshRetailNet-50K (CC BY 4.0, hourly stock status); Instacart's terms forbid redistribution (reported); M5 and Favorita unconfirmed | LOG EX-03 |
| R-51 | Answered in part | Learned policies beat base-stock by 0.8% to 5.7% in simulated lost sales | LOG EX-02 |
| R-56 | Answered | 65% of nearly 370,000 records in 37 stores inaccurate (DeHoratius and Raman, 2008) | LOG EX-04 |
| R-60 | Answered in part | Expiry-date visibility is the one quantified complaint found (reported) | `docs/truth/FRONTIER.md` |
| R-14 | Confirmed | `README.md:66` still says 38 records; 57 on `main` | measured |
| R-15 | Confirmed | `README.md:17` still says the GCP code awaits a pull request | measured |
