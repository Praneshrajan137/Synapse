# DIRECTION - the next eleven sessions

**Status: 2026-11-17, session 2.** A recommendation for session 3 to decide on, derived from
[`TRUTH-MAP.md`](TRUTH-MAP.md) and [`FRONTIER.md`](FRONTIER.md). The decisions it needs from the
operator are in [`DECISIONS.md`](DECISIONS.md).

## 1. What the evidence says

1. Where decisions were traced (372 of them), one component made every one: the Inventory
   Sentinel's reorder rule. Five other agents returned the same score in every state of the
   world, and two never proposed. Debate, arbitration, the language model and the twin check
   run only on a path that autonomous operation never takes, and where forced they changed no
   order (MAP F-01 to F-06).
2. The repaired system loses to the tuned rule because one of that rule's levels is set about
   three times too low. Corrected on the same seeds, it about ties the rule (F-13, F-13a).
3. On the cell the proof measures, no policy without hindsight on record clears the margin a
   win must clear. Any room to win lies in structures the twin does not yet have (F-29, F-30).
4. The proof harness is real: deterministic, fast enough to run on the laptop, and able to say
   no. The safety behaviour of the decision core is guarded by tests that fail when it breaks
   (F-14, F-31).
5. Nothing runs as a system anywhere, and the newest work sits on four open branches and in
   uncommitted files (F-18 to F-22, LOG M-22).
6. Eleven sessions fit in the 63 days left only if verification stays on the laptop; the last
   spec slowed from a day and a half to two weeks a session once it waited on labelled CI
   runs (F-32).

## 2. The premise, tested

The stated premise: eight specialised agents, reaching consensus, make better replenishment
decisions than a tuned rule.

**It is not supported, and the reasons are structural, not defects.** One store with no transfer
between stores gives coordination nothing to coordinate. A twin in which waste does not depend
on stock removes the trade-off that makes perishable replenishment hard. On the measured cell a
tuned rule is already near what any policy without hindsight can reach. And the code binds the
most self-confident proposer, so more proposers add cost and no information. Repairs to
individual agents would not change any of these four.

**The premise worth keeping is narrower and stronger: governed decisions with evidence.** An
incumbent rule that always has an answer; challengers, agents among them, that must show in the
twin that an action beats the incumbent before it is taken; every action bounded, recorded and
scored against what happened; and a proof that can fail. The number of agents becomes a
measured quantity, not a premise.

**The strongest case against this, and the answer.** A reviewer with fresh context argued that
the harness and gates were the deliberate product of the last spec, which delivered a controlled
negative result few agent projects could produce, and that a multi-agent architecture is about
extending to many workflows and cities, not about beating a rule on one cell. Both points
stand. They support this direction rather than oppose it: the harness is its spine, and
extension is exactly what the arbiter makes safe, because every new agent is admitted as a
challenger and earns each action. What the reviewers can verify in five days is evidence, not
future extensibility, so the release leads with evidence.

## 3. Four directions, tested against the measurements

| | D1 Repair and prove the current design | D2 The sceptic's system | D3 The harness as the product | D4 Incumbent first, evidence led |
|---|---|---|---|---|
| What it is | Keep the eight-agent consensus central; repair each agent; deploy the full 23-service stack; prove uplift on the primary cell | One tuned policy, the twin and a console; delete the rest | Publish the scenarios, the tuned control and the scoring rule as a benchmark; SYNAPSE is one entrant | D2's runtime core, D3's spine, and whatever of D1 earns its place by ablation |
| Against the measurements | Five agents have nothing to say about a reorder (F-02); the margin is out of reach on the measured cell (F-29); the stack needs about 27 GB of declared memory and the language model on a machine of 32 (F-22) | Honest and robust, but a tuned rule with a user interface is not what the work is, and it would hide most of it | The harness is the strongest asset (F-14), but its world has a waste clock and ten uniform items (F-30), the first thing an operations researcher would attack | Uses parts that exist: the tuned control (arm E), the twin check (tier 4), the harness, the guardrails |
| Against the calendar | Every layer at once; the slow regime of two weeks a session is likely | Fast | Fast | Staged so that each stage leaves something releasable |
| Against "the work as a whole" | Shows the whole, but cannot back its central claim | Shows a fraction | Shows the method, not a system | Shows the whole system, each part labelled with what it measurably does |
| As models improve | Hand-written agent heuristics lose value | Neutral | Gains value | The arbiter and the twin check judge any proposer, including a model-written policy, so it gains value |
| Verdict | Rejected | Rejected as the story; adopted as the runtime core | Adopted as the spine | **Recommended** |

A fifth form was considered and rejected: a scripted demonstration in which scenarios are
replayed for the reviewers. It shows a process that did not run, the failure the knowledge base
ranks tenth (INS-034, INS-056).

## 4. The recommended direction, concretely

1. **Incumbent first.** The tuned rule decides every reorder unless a challenger's action is shown
   in the twin, at that state, to beat it, and passes the guardrails; then the challenger's
   action is taken. Each decision records both actions, the twin's verdict and, later, what
   happened. The machinery exists: arm E is the incumbent, the tier-4 twin check is the
   lookahead, the dispatch choke point is the gate (F-06, F-31).
2. **Agents earn their place by ablation.** Before the ablation runs, a rule is written down: a
   component that changes no measured outcome in any pre-registered cell is shown as "not used
   in this workflow". The forecaster's output goes into the Sentinel's request, which is the
   information mechanism the primary cell can reward (F-29).
3. **Fix the four category errors before adding anything.** Waste takes stock and depends on
   what is held (F-30). Forecasts inform; they do not scale demand (F-09). Outcomes are recorded
   after execution (F-10). Approval enacts, and an operator can amend a quantity (F-08).
4. **The proof becomes a map.** Pre-registered by cell: the primary cell, the four adversarial
   scenarios, and the new structures, with the negative results and their causes kept. Fitted on
   one set of seeds, judged on another. Run on the laptop, confirmed in CI (F-14, LOG M-24).
5. **The release is a thin slice.** The twin, the orchestrator with its agents in-process, the
   API, the console and Postgres, on one machine, rehearsed twice. The rest of the stack stays in
   the repository, labelled as not deployed (F-19, F-22).

## 5. The gaps, ranked by gain against cost and risk

| Rank | Gap | What closing it gains | Cost | Risk if left | Evidence |
|---|---|---|---|---|---|
| 1 | No deployable system and no place to rehearse | The release exists at all | 2 sessions | Certain failure | F-18 to F-22 |
| 2 | Work in flight not landed | Every later change builds on `main` | 1 session | Rework, lost truth | LOG M-07, M-22 |
| 3 | One level in the reorder rule | From losing by 1.4 to about level | Part of a session | Low | F-13a |
| 4 | Four category errors | An expert cannot discount the rest on sight | 1 to 2 sessions | High with expert reviewers | F-08, F-09, F-10, F-30 |
| 5 | A claim that can be true | "Where and by how much each part helps" | 2 sessions | The reviewers' first question goes unanswered | F-01, F-29 |
| 6 | The reviewer's first five minutes | "Why should I care" answered on screen | 1 session | The story does not land | LOG M-28 |
| 7 | A truer twin: skew, more items, calibrated demand | "Is this world real?" answered in part | 1 session | Medium | F-30, LOG EX-03 |
| 8 | Published default credentials | A public link that is safe | Part of a session | Medium | FRONTIER row 16 |
| 9 | The apparatus: a watchdog that never saw the system, eight stale alarms, a 68 KB `CLAUDE.md` | Cheaper, more honest sessions | Part of sessions 3 and 11 | Slow drift | F-25, Q-04 |

**Deferred, deliberately and in writing:** transfers between stores and multiple stores; record
inaccuracy beyond one stress cell; validation against a real store; the language-model tier;
the Helm, Kafka, Neo4j and multi-city topology; training policies on Colab beyond imitating the
incumbent; any new console surface. Each is real work; none moves what ten reviewers can verify
by January.

## 6. Pre-mortem: it is 2027-01-25 and the release failed

| Cause, most likely first | Present today? | How the direction answers it |
|---|---|---|
| The first full run on the release machine fails: certificate, identity provider, memory, registry | Yes: nothing deployed since June; the Terraform is untested; the web server names the old machine (F-18 to F-22) | Thin slice; first cloud rehearsal in session 9, five weeks before the release |
| The reviewers cannot tell in five minutes what it did and why it matters | Yes: the first screen shows the system's own state (LOG M-28) | One session on the first five minutes; a cold reader in the dress rehearsal |
| "Does it beat a simple rule?" has the answer "no, and we do not know where it would" | Yes (F-13, F-29) | Incumbent first; the proof as a map by cell |
| Scope swallows the calendar and work strands on branches | Yes: four open pull requests; the slow regime (LOG M-22, M-27) | Land first; verify locally; must, should and could ranked below |
| An expert finds a category error and discounts the rest | Yes: waste as a clock, a forecast that moves demand (F-30, F-09) | Fixed before anything is added |
| A credential or an open control is exploited | Partly: defaults published; the admin defect fixed but never deployed | Hardening session; view-only public access |
| The trial is ended, refused or runs out during the release | Possible: the terms allow it; the credit lapses near the last day (EX-01) | Upgrade before the release (operator); a fallback host |
| An interactive action takes tens of seconds | Possible: the full path took 1.3 to 5 s here and stalled once (LOG M-21) | Incumbent decides in milliseconds; the twin check bounded and measured on Linux in rehearsal |
| The operator's usage limit stops a session mid-change | Seen this session (LOG M-15) | Small steps, committed as they are verified |

## 7. The path, in sessions

Sessions 3 to 13 come before the release, which must start by 2027-01-18 so that five days end
before the trial can lapse. "Local" means verified on the laptop before any CI run.

| Session | Outcome | Verified by | Cloud | Rank |
|---|---|---|---|---|
| 3 | Definition of finished; the decisions in `DECISIONS.md`; the cut list | The operator's answers | - | Must |
| 4 | Pull requests #87, #91 and #90 landed on `main`, #89 if green; the ledger worktree committed; the Sentinel's levels fitted on held-out seeds; a twelve-replicate local proof wired as a fast check | Local miniature of E5; CI green on `main` | - | Must |
| 5 | Outcomes recorded after execution; approval enacts and can amend; forecasts inform instead of moving demand; the sensor flags disruptions | Tests that fail before the change; local traces | - | Must |
| 6 | Waste takes stock by age; skewed demand over more items, its shape fitted to FreshRetailNet-50K; the tuned rule re-tuned | The harness's controls, run locally | - | Should (waste: must) |
| 7 | The incumbent-first arbiter; ablation arms; the map pre-registered | Local runs on held-out seeds | - | Should |
| 8 | One command starts the thin slice on the laptop, timed from a fresh clone to a first decision on screen; the first five minutes redesigned | A cold walk with a clock | - | Must |
| 9 | First cloud rehearsal on the new account: Terraform repaired, deploy, 24-hour soak, snapshot and restore drill, then everything stopped | `verify_live.py`; the restore timed | About $10 | Must |
| 10 | The proof run on the final design; the proof page in the console; `README.md` and `CLAUDE.md` brought to the truth | CI confirms the local numbers | - | Should |
| 11 | Hardening: credentials, access mode, an uptime check that reaches a phone, a runbook, a ten-user load test | Each failure injected once | - | Must (credentials, uptime) |
| 12 | Dress rehearsal: 48 hours, a cold reader, a fix list; then stopped | The bar of FRONTIER row 12 | About $16 | Must |
| 13 | Go or no-go; deploy; the five days begin by 2027-01-18; stopped at the end | Daily checks against row 12 | About $46 | Must |

**If the pace is the slow regime** (two weeks a session, LOG M-27), the must-set alone does not
fit. Then the plan collapses to five sessions: decide and land (3 and 4); fix the decisions and
the category errors (5); thin slice and first five minutes (8); one cloud rehearsal (9 and 12
together); release (13). The arbiter, the ablation and the truer twin are then cut, and the
release says so.

**Cloud.** About eight machine-days, roughly $70 of machine time. Disks and a reserved address
keep billing between uses unless deleted: about $20 to $45 more if they are kept from
mid-December. A budget alert at $120. Every machine is stopped after each use, as the operator
asked, and anything not needed before the next use is deleted. The prices are from a
third-party table until read in the console (FRONTIER 1.5).

## 8. How it compounds

- **As models improve**, the arbiter and the twin check judge any proposer, including a policy a
  model writes and the harness scores (INS-040), so they gain value; hand-written agent
  heuristics lose it.
- **For a maintainer years on**, the run-time system is small, and the proof runs on a laptop.
- **At ten times the scale**, the thin slice multiplies by store; transfers between stores are
  where coordination could finally pay, and they are named as the next frontier, not hidden.
- **Under adversarial pressure**, every action passes the guardrails at the boundary and falls
  back to the incumbent; public access is view-only.
- **Reversibility**: each step lands on `main` behind tests, and turning a challenger off is a
  setting, not a deployment.

## 9. What would change this direction

- The operator says the eight-agent consensus itself is what the reviewers must see: D1's
  elements return to the console, still under the per-agent contribution table.
- The ablation shows the agents together beating the incumbent by the margin on stressed cells:
  lead the release with that.
- The first cloud rehearsal fails for reasons of the platform: move the release to the fallback
  host.
- A named practitioner appears: aim the first five minutes at that person's day.

## 10. The panel, before declaring done

| Reviewer | Verdict | Evidence that earned it |
|---|---|---|
| Domain Expert | Passes the direction; blocks the old claim | The twin's waste clock and uniform items are named and scheduled for repair; the tuned rule is treated as the incumbent it is in practice |
| Architect | Passes | The release form is about five services instead of 23; the arbiter reuses the existing choke point |
| Adversary | Passes on conditions | Published defaults and the never-deployed access fix are ranked; the public link stays view-only |
| Verifier | Passes | Every finding has a command or a line; 5 of 5 faults caught; a fresh reviewer reproduced 9 of 10 measurements and found 9 errors that were corrected |
| Operator at 3 a.m. | Not satisfied with the system, satisfied with the plan | No environment exists; the plan rehearses twice and adds an uptime check that reaches a phone |
| Release Engineer | Passes | Small steps on `main`; a fallback host; every cloud use ends with the machines stopped |
| Maintainer | Passes with a note | Six files, one job each; the log is long, and its "How to resume" is the way in |
| User | Cannot judge yet | The console has been seen only without a backend |
| Performance Engineer | Passes with a gap | The decision path is measured (0.02 s); the twin check's cost on Linux is not |
| Craftsman | Passes | The direction removes more than it adds: most of the 23 services, five agents' constant proposals and the always-on language model leave the release path |
| Store Manager | Not satisfied, and cannot be in this session | No store manager was asked anything; Q-01 is the first decision |
| Release Reviewer | Not satisfied with the system | What it did, how we know and why it matters are answered in these documents, not yet on the screen |

Three members are not satisfied, each for a reason this session cannot remove: the system does
not run, no user has been asked, and the console has not been seen with data. Each is the first
item of a session in section 7.

## 11. What the session-2 prompt did not ask, answered

- **What works, and must be protected while the rest changes?** The harness's determinism and
  its habit of publishing negatives (F-14); the decision core's safety tests, which caught five
  of five faults (F-31); the provenance contract and the console's honest labelling of degraded
  and unknown reads (LOG M-28). Every session in section 7 keeps these green.
- **Does the project's own rule for recording facts drive the growth of its apparatus?** Very
  likely. `CLAUDE.md` asks that a fact worth discovering twice become a gate. Gates check what
  someone wrote down (T-017), and a quarter of all added lines went to the harness and another
  eighth to gates (LOG M-05). Proposed default for the next sessions: change the code so the
  wrong state cannot occur, and add a gate only where that is impossible.
- **What did the word "agent" cost?** It shaped the console around the agents' activity rather
  than the store's outcomes (LOG M-28), the topology around one service per agent (F-22), and
  the decision path around a debate that autonomous operation never reaches (F-05). The
  direction keeps the agents and drops the framing: each is a challenger with a measured
  contribution.
- **Who maintains SYNAPSE after the release?** The operator alone, with sessions like these.
  That argues for the thin slice and the local proof, which one person can run, over the full
  topology, which one person cannot keep alive (F-25).
- **What is the operator's own time worth in this plan?** The decisions owed are thirteen lines
  (`DECISIONS.md`). Everything else in section 7 is work a session can do and verify without
  the operator, except approving merges and the cloud's sign-in.

