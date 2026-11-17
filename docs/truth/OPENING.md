# SYNAPSE session 2 - the opening

**Status: written 2026-11-16 before the gate; the operator replied on 2026-11-17 and the reply
is taken as approval of the defaults in section 11** (see "The operator's answers" in
[`LOG.md`](LOG.md)). The text below is as it was presented. Hypothesis H-01 has since been
confirmed by the operator, and the four questions of section 12 are answered there. Every
identifier of the form M-nn, RD-nn, EX-nn or H-nn resolves to an entry in `LOG.md`, where the
command or the source is given.

Labels used throughout: **measured** (a command in this session produced it), **read** (a file
or pull request says it; not reproduced), **checked** (an outside source opened by the main
session today), **reported** (a subagent's return, not re-checked), **inferred**, **hypothesis**
(with what would prove it false), **unknown**.

## 1. What SYNAPSE is, and whom it serves

- **Stated (read, `CLAUDE.md`).** A multi-agent system with LLM orchestration that optimises a
  quick-commerce supply chain: eight agents, an orchestrator, a digital twin, a data fabric, an
  API and a console.
- **As built (measured, M-02 to M-04).** Seven months old, 364 commits on `main`, 2,121 files,
  384,345 lines. The decision core is 40,948 lines of Python. The console is 24,278 lines of
  TypeScript under `frontend/src`. The proof harness and the audit gates together are 51,118
  lines, larger than the core they examine, and their tests (66,574 lines) are larger than the
  core's (45,390).
- **As it behaves (read, RD-01, RD-07).** One simulated store of ten items. No named user, no
  live orders. The one measured comparison of its decisions is a loss to a tuned reorder rule.
- **Whom it serves (inferred).** Nobody outside the project yet. The first real audience is
  fixed and dated: ten reviewers, five days, from about 2027-01-19. The second is a
  replenishment practitioner who has not been named (Q-01). The third is the operator, who
  carries the cost of failure.
- **Where the effort went (measured, M-05), and two readings of it.** Over all 326 commits,
  22% of added lines were core or console source and 49% were the proof harness, gates and
  documents. In the 122 commits since late July, the period of the decision-quality-proof spec,
  the split was 8% and 77%, with 14% in tests of the core and console. Reading one: the project
  has turned from making decisions to examining itself. Reading two, put by the fresh reviewer:
  that period was chartered to prove or refute the core, so harness lines were its planned
  output, and it delivered a controlled negative result that few agent projects could produce.
  Both fit the numbers. What decides between them is whether the harness is itself the thing
  the reviewers are to judge, which only the operator can say (section 12).
- **What it must never get wrong at the release (inferred).** State a claim it cannot back;
  show simulated output as real; leave control open to strangers; be absent when a reviewer
  arrives.

## 2. The frontier, and where SYNAPSE stands (first calibration)

Five bodies of practice set the standard, and a sixth is added here because the release has an
audience (said openly, as the prompt requires):

1. **Inventory-control theory and its learned successors** (base-stock and (s,S) theory; the
   end-to-end learned policies published by large retailers). They lead on cost against a tuned
   rule. They gave up generality: results hold for the demand and lead-time process assumed.
2. **Experimentation and simulation-validation practice** (switchback and field experiments;
   validation of a simulator against history). They lead on whether a result transfers. They
   gave up speed: they need a live system or real data.
3. **Indian quick-commerce operators' own stores and planning** (the incumbent any product must
   serve or beat). They lead on scale and realism. They publish little about method.
4. **The measured science of agent systems** (controlled studies of several agents against one;
   long-horizon agents running a small business). It leads on knowing when coordination pays.
   It still lacks rule baselines in business settings.
5. **Reliability practice for small deployments, and standards for reviewable artifacts.** They
   lead on being up, observable and reproducible by a stranger.
6. **Added: the reviewer's first five minutes.** No standard exists; it is defined in row 14.

These sixteen properties become the rows of the final scorecard. None will be dropped, merged
or added without saying so.

| # | Property | Frontier reference and value | SYNAPSE now | Status |
|---|---|---|---|---|
| 1 | Cost against a tuned classical rule | Best published learned policy beats base-stock by 0.79% to 5.68% in simulated lost sales, more as lead time grows (checked, EX-02) | Repaired consensus arm scores 3.9266 against the tuned control's 2.4804 on the twin's weighted objective, 58% worse; fill rate 0.762 against 0.939 (read, RD-01). The two columns use different cost measures in different worlds: what carries over is the sign and the rough size, not the percentage | Behind. Read, not reproduced |
| 2 | Knowing where a tuned rule loses | Literature places the room in long lead times, shifting or censored demand, perishables, shared constraints, substitution and transfers (reported) | Regret against hindsight is computed by the harness; its values by cell are unread. The twin lacks most of those structures (measured, M-09) | Unknown. First research task |
| 3 | Internal validity of the comparison | Pre-registered claim, paired seeds, interval, power, negative and positive controls, negative results published (reported) | All present by the ledger, and a loss was published twice (read, RD-01, RD-06). One flag is open: the controls' agreement check reads `harness_mis_measuring`, which the ledger attributes to the seed sets (finding 117). Whether a replicate repeats from its seed is untested | Level in design; unverified until finding 117 and R-43 are settled |
| 4 | External validity | A field or switchback experiment, or a simulator validated against real history (reported) | Twin declared; fidelity `unknown` (read, RD-07). A CC BY 4.0 dataset of hourly fresh-retail sales with stock status exists and is unused (checked, EX-03) | Behind |
| 5 | Reproduction by a stranger | Artifact badges: available, functional, reusable, results reproduced (reported) | E5 runs only as a labelled CI job of 53 minutes (read, RD-01). Time from clone to a first decision is unmeasured | Estimated behind |
| 6 | Assortment and demand realism | Stores carry thousands to tens of thousands of items; secondary sources range from 2,000 to over 40,000 (reported, conflicting) | Ten items in E5's traced world (measured, M-16), drawn uniformly by the engine (measured, M-09). Whether any scenario cell reshapes the mix is unread | Behind by about three orders of magnitude |
| 7 | Operational structure | Hub-and-spoke replenishment; 65% of stock records wrong in the standard study of one retailer (reported) | One store, one stock number per item, lost sales only, no transfers (measured and read) | Behind |
| 8 | A named user and workflow | Products of this kind are built with a named practitioner | None (read, Q-01) | Behind |
| 9 | Evidence the architecture earns its complexity | Several agents gain up to 80.8% on separable work and lose 39% to 70% on sequential work, at 285% to 515% more tokens; adding agents to a strong single baseline returns less (reported) | No ablation arm. One agent's heuristic bound 15 of 15 traced decisions (measured, M-16); all of E5 untraced (H-02) | Behind |
| 10 | Agents that act | Each acting component has an observed effect under test (defined here) | Eight of eight reach an actuator or an event source by static audit; no behavioural probe is on record (measured, M-11) | Unverified |
| 11 | A working path to production | Merge to verified live in minutes; withdrawal exercised | The last run that deployed was 2026-06-14. All 22 scheduled deploys since have failed, and so have the 28 newest runs. The watchdog is 0 of 26 green and has never reached the system (measured, M-08) | Behind |
| 12 | Showcase reliability | Proposed bar: 99.5% over 120 hours (36 minutes down), outage known within 2 minutes, restore rehearsed under 30 minutes, fresh machine to working system under 45 minutes | Nothing measured. A daily stop policy is attached (read). The trial allows eight cores at once, which is the release VM alone (checked, EX-01) | Behind |
| 13 | Cost inside the credit | Under $300, inside the expiry | Five days about $40; fourteen days about $113 (reported, from a third-party price table) | Level, estimated. The date and the core cap bind, not the money |
| 14 | A cold reviewer's first five minutes | Defined here: within five minutes a reviewer can say what the system did, how they know, and why it matters, each claim one step from its evidence | Unmeasured. Fourteen routes, twelve surfaces (measured, M-13) | Unknown |
| 15 | Gates shown able to fail | Every load-bearing check has a demonstrated failing case | A falsification sweep exists; the share of checks it can fail is unread (R-24) | Unknown |
| 16 | No exposure in a public repository | No default credential published; no open control surface | Default credentials listed as open exposures (read, `CLAUDE.md`); the admin sign-in defect is repaired on `main` and the repair has never been deployed (read, RD-05) | Behind |

Rows 6, 7, 9 and part of 2 rest on subagent reports whose own grading is mostly "snippet" or
"secondary". Confirming them from primary sources is the first research task after the gate.

## 3. What was established before the gate

1. **A repaired E5 exists, and it still loses (read, RD-01).** The session prompt listed this as
   unknown. After the fix of finding 112 the consensus arm dispatched all 24,000 decisions and
   lost by 1.4463 objective units, interval [-1.4650, -1.4286]. Fill rate 0.762 against 0.939.
2. **The newest truth about E5 is not committed anywhere (measured, M-07).** It lives in four
   modified files in the `ledger` worktree, with unfilled placeholders. The fix itself, PR #87,
   has been open and green since 2026-11-02.
3. **Where it has been traced, the "consensus" is one agent's untuned heuristic (measured,
   M-16).** In the project's own CI trace of 2026-11-14 the Inventory Sentinel bound 15 of 15
   decisions. Six of eight agents returned a proposal, four of them with confidence exactly 0.5.
   Each decision took 21 milliseconds in Tier 2; no debate was reached. The Sentinel's
   order-up-to level was about 27 units where the tuned rule holds 118 to 183, so it ordered
   nothing at any traced state. The trace covers three states at one seed, not all of E5 (H-02).
4. **Nothing has been deployed since 2026-06-14 (measured, M-08).** The weekly deploy introduced
   on 2026-06-15 has never succeeded: 22 of 22 scheduled runs failed. Whatever is live, if
   anything is, predates the agentic loop, the uplift proof and the open-access repair. Eight
   `sev1` issues opened by automation are open, six since July and two since 2026-11-01. The
   watchdog is 0 of 26 green, and it has never reached the system: its first runs stopped
   because the VM was not running in its window, its later ones at cloud authentication. So it
   has reported the state of a schedule and a credential, never of the system. Today's deploy
   run failed in all 12 build legs, and the provider's own error says the identity pool or
   provider "is disabled or deleted or ... doesn't exist". The environment may no longer exist
   (hypothesis, H-01); the rival reading is that only that provider was removed.
5. **The trial allows eight cores at once (checked, EX-01).** The release VM uses all eight, so
   no second machine can run beside it. The laptop has half the VM's memory (measured, M-12).
   There is at present no place to rehearse the full system except the release VM itself.
6. **Where the effort went (measured, M-05).** See section 1.
7. **`CLAUDE.md` is out of date in checkable places.** It says six of eight `execute()` methods
   do not act (M-11 says none is a stub); that the watchdog runs twice a day (measured: weekly);
   that the repository is private under another owner (it is public); and its domain line still
   says ten-minute delivery, branding the largest operator dropped in January 2026 (reported).
8. **The prize above a tuned rule is small where the twin lives (checked, EX-02).** A few per
   cent, growing with lead time. A loss of 58% says the arm is mis-specified, not that the
   frontier is far.

## 4. The questions, ranked by leverage

Leverage means how much the answer changes what the next eleven sessions do.

The letters are names; the order of the rows is the rank. The fresh reviewer moved I up and
pulled the question of the objective's weights into C; both changes are adopted.

| Name | Question | Why it ranks here | Earlier IDs |
|---|---|---|---|
| A | What must the ten reviewers conclude, and about what: the agents, the proof harness, or the work as a whole? | It defines finished. Only the operator can answer; this session prepares the memo | Q-01, Q-03, T-004 |
| B | Does a release path exist: a cloud environment, a deploy that authenticates, a place to rehearse, a time from clone to a first decision? | If not, nothing else reaches a reviewer. Its first step is a one-minute check only the operator can make | R-08, R-57, R-61 |
| I | What is true only off `main`, and in what order does it land? | The repair of finding 112 is unmerged, so C and D must be answered on its tree as well as on `main` | new |
| C | Under an objective a practitioner would accept, where can any policy without foresight beat the tuned rule in this twin, and what would a truer twin need? | If nowhere, "repair and prove the current design" is not a direction. If the weights have no source, the question has no meaning yet | R-29, R-58, R-59, R-51, R-55 |
| D | What does one decision actually do, end to end, through the real envelope? | It settles whether "eight agents decide" can be said to a reviewer | R-17, R-01, R-16, R-22, R-32 |
| E | What does a cold reviewer meet in the first five minutes? | The reviewers are the first users | R-39 |
| F | Does the proof hold when attacked: same seed twice, leakage, the open agreement flag? | The harness is the strongest asset and a candidate product | R-43, R-44, R-11, finding 117 |
| G | Which components does anything run, and which would change a measured outcome if removed? | It is session 3's cut list | R-09, T-002 |
| H | Which gates can fail, and which findings did a gate catch? | Separates protection from ceremony, and tests the case that the gates are the product | R-24, R-47 |
| J | What can twelve sessions deliver, judged by the record? | The last spec averaged about 8 days a session (inferred from dates read); the calendar allows about 5.5 | new |

## 5. The widest gaps suspected

Ordered by how much each threatens the release. Each is a suspicion until `TRUTH-MAP.md`.

1. No release path and no rehearsal place (measured in part; H-01).
2. No statement of what the reviewers should conclude, so no definition of finished (read).
3. The central claim, that the agents' consensus improves decisions, is refuted on the one cell
   for which a result is recorded, and that cell may hold little room for any winner (read;
   H-03). Whether the shocked cells were run for this arm is unread (R-02).
4. The twin is too thin for a verdict to carry: ten uniform items, no record error, no
   transfers (measured, M-09).
5. Red signals without a recorded response, one of which could never see the system (H-05).
6. Truth scattered and partly uncommitted (measured, M-07).
7. No local view of the running system: a recorded rule forbids simulation runs on the laptop,
   and the behavioural probes are CI-only (read; to be retested, R-20).
8. Published default credentials (read).

## 6. Assumptions carried

| Assumption | Standing |
|---|---|
| `origin/main` at `d4f985c` is the baseline | Measured (M-01) |
| The release is five days from about 2027-01-19 for ten people | Read (operator's note of 2026-11-15) |
| The $300 credit is untouched and expires about 2027-01-24 | Read; the start date of the trial is unknown to this session |
| The ledger's E5 numbers are transcribed faithfully from the run's artifact | Read, unverified; the artifact can be downloaded to check |
| The uplift harness is internally sound | Inferred from its record of failing; untested here, and one of its own checks reads `harness_mis_measuring` (finding 117) |
| The eight agents are mostly numeric components with untrained policies | Read (`CLAUDE.md`), unverified |
| A reviewer will open the console before any document | Assumed; the operator may know otherwise |
| The laptop cannot hold the full stack | Inferred from M-12; untested |
| Subagent reports are right where they say "fetched" | Sampled: three claims re-checked and held (EX-01 to EX-03) |

## 7. What must not change, and how that will be shown

| Must not change | Proof at the close |
|---|---|
| Any tracked file outside `docs/truth/` and `docs/knowledge/` | A path-limited `git diff` against `docs/knowledge-base` is empty |
| `main`, every other branch, every tag | The ref digest of M-14 is unchanged apart from this session's own branch |
| The seven worktrees and the stash | `git -C <path> status --short` and `git stash list` read as in M-07 |
| Anything on `origin` | The `ls-remote` digest of M-14 is unchanged; nothing is pushed |
| GCP, Colab, GitHub state | No command that writes to them is run; GitHub is read through `gh` list and view only |
| `.kiro/settings/` stays untracked | `git ls-files .kiro/settings` is empty |
| No text from the private corpus enters the repository | This session does not open `C:\Documentation` |

## 8. What would convince a sceptical expert

- Every finding carries its reproduction: the command and its output, or a file and line at a
  named commit.
- One decision traced through the running system, with the expected trace written first and
  each departure recorded.
- For each invariant examined, the fault introduced and the check seen to fail, or seen not to.
- A count of claims checked against the code, with every divergence listed.
- A reviewer with fresh context reproducing a random sample of findings and trying to refute
  the most consequential ones, with the outcome of each attempt.
- A plain statement of what was not examined.

## 9. Approach

**Order of work after approval.** One usage window is one five-hour allowance on the plan.

| Window | Work | Questions |
|---|---|---|
| 1 | Release path: read the Terraform, deploy workflow and compose files; start the largest slice that runs on this laptop; time clone to first decision; list what assumes a part-time VM. Then map what each open branch holds that `main` does not, and trace one decision on `main` and on PR #87's tree | B, I, D |
| 2 | Headroom by cell from the harness and its artifacts; one replicate run twice from one seed; leakage; where the objective's weights came from | C, F |
| 3 | Cold walk of the console with a clock and screenshots; a table of every component, whether anything runs it, and what removing it would change | E, G |
| 4 | Gates and invariants: which can fail, shown by introducing the fault, sampled by consequence; how each named finding was caught. Then `docs/knowledge/` reading by reading | H |
| 5 | Frontier from primary sources; four or more directions weighed; pre-mortem; panel; a fresh reviewer's attack; decision memos; scorecard; final account | A, J |

**Budget and stopping rule.** Five windows, closing by 2026-11-20. A question closes when its
acceptance condition is met, or when two passes add nothing that changes a decision. Whatever
is unexamined at the close is listed as work for session 3. The pre-gate reconnaissance used
one full window (M-15).

**Depth.** The inventory is complete: every component is listed, sized and marked as run or not
run. Depth follows consequence: deep on the decision path, the proof and the release path;
sampled elsewhere, with the unsampled remainder named. This is a stated limit, not a quiet one;
the alternative is in section 11.

**Alternatives rejected.**

- Reading all 2,121 files in turn. Most bear on no decision, and the budget does not allow it.
- Starting from the documents and checking each claim. It inherits their framing. The list of
  divergences is a by-product of tracing the system, not the spine.
- A wide fan-out of subagents. It failed once already in this session (M-15, D-03).
- Re-running E5 in CI. It needs a label on GitHub, about an hour a run, and the repaired run's
  artifact already exists to be read.
- Merging the open pull requests first to get one baseline. That changes `main` and is the
  operator's decision. Each branch is read where it stands.
- Probing or provisioning anything on GCP. Outside this session's authority.

**Risks.**

| Risk | Answer |
|---|---|
| The usage limit arrives mid-finding | Log first, commit at each verified step, at most three subagents with capped calls |
| The full stack does not fit in 15.7 GB | Run the thin slice the harness already uses, plus API and console; record what could not run |
| This session's own bias toward "apparatus over substance", which is already in its memory | A fresh reviewer is asked to argue the opposite case at full strength |
| An uncommitted worktree file changes after being read | Each is pinned by a content hash in the log |
| A subagent's report is wrong | A sample is re-checked before any use, as in EX-01 to EX-03 |

## 10. Deliverables and their acceptance conditions

| File | Accepted when |
|---|---|
| `docs/truth/OPENING.md` | The operator approves it |
| `docs/truth/LOG.md` | A reviewer with no other context re-runs its commands and resumes from it |
| `docs/truth/TRUTH-MAP.md` | Every component of M-04 has a row; every finding has a reproduction; a fresh reviewer reproduces at least ten findings drawn at random; it holds the traced decision and the table of divergences |
| `docs/truth/FRONTIER.md` | Each of the sixteen properties has a reference, a value, a source, its date and how it was obtained; no verdict rests on a number the main session did not open |
| `docs/truth/DIRECTION.md` | At least four directions tested against measurements; gaps ranked by gain, cost and risk; a pre-mortem; a path in sessions that fits 64 days at the pace on record |
| `docs/truth/DECISIONS.md` | One page a decision; options, a recommendation, and what each answer changes; each answerable in a line |
| `docs/knowledge/` | Every reading of SYNAPSE marked confirmed, corrected or refuted with its evidence; every R item answered, assigned or retired; the folder's own ID check still passes |
| The scorecard | Sixteen rows plus the three the prompt requires |

## 11. Approvals asked

Defaults are marked. One reply of "approved" takes every default.

1. **Branch.** Cut `docs/truth-session-2` from `docs/knowledge-base`, not from `main`, because
   this session corrects files that exist only on that unpushed branch. This departs from the
   branch rule in `CLAUDE.md` and needs your confirmation. **Default: yes.**
2. **Commits.** Local commits touching only `docs/truth/**` and `docs/knowledge/**`, the opening
   and the log first. No push, no pull request. **Default: yes.**
3. **Instruments.** Keep the measuring scripts in the repository so the numbers can be
   regenerated, moved from `docs/truth/instruments/` to `scripts/truth/` and brought up to the
   repository's typing and lint rules. No gate is wired to them in this session. **Default:
   yes.** Alternative: keep them out of the repository and cite commands only.
4. **Running the system on this laptop.** Start the Docker engine and run the largest slice that
   fits, pulling public images. This uses memory and disk and may take an hour or more.
   **Default: yes.**
5. **Changes to the product so it can be observed.** None are planned. If the system cannot be
   built or run without one, **default: record it as a finding and stop to ask**, not change it.
6. **Reading outside services.** GitHub through `gh` in read-only form, including downloading
   run artifacts and logs to a temporary folder; `git fetch origin`, which updates
   remote-tracking refs only. No GCP call of any kind. **Default: yes.**
7. **Depth.** Complete inventory with depth by consequence, in five windows (section 9).
   **Default: this.** Alternative: full depth on every subsystem, which this session estimates
   at eight to twelve windows and a close near 2026-11-26.

## 12. Four things only you can tell me

1. **Does the VM from June still exist?** A look at the cloud console answers it in a minute,
   and it decides between H-01 and its rival: everything gone, or one identity provider gone.
2. **Is the untouched $300 on the same billing account that paid for that VM?** The trial terms
   admit only new customers and let the provider end a trial at any time (checked, EX-01). If
   either could apply here, it is a risk to the release date that the plan must carry.
3. **What should the ten reviewers conclude, and about what?** About the agents' decisions,
   about the proof harness, or about the work as a whole. One sentence steers the direction
   work. Without it the decision memo lays the options out unranked by your intent.
4. **May any of the credit be spent before the release?** The facts: five days cost about $40
   and a fortnight about $113 (reported, not an official price); the trial allows one eight-core
   machine at a time; the laptop has half that machine's memory. The options are a rehearsal on
   the real machine before the reviewers arrive, a rehearsal of a thin slice on the laptop only,
   or none. This session will measure what the laptop can hold before recommending.

## 13. The panel before the gate

Each judges the opening and the approach through one lens. None blocks; two conditions were
adopted.

| Reviewer | Verdict | Evidence or condition |
|---|---|---|
| Domain Expert | Passes, with a caution | The opening measures "beats the tuned rule". A practitioner would ask about availability at the promise time, waste and workload. Where the objective's weights came from is in window 2 |
| Architect | Passes | Asks that the inventory be regenerable by one command. Adopted (approval 3) |
| Adversary | Passes on a condition | The repository is public, so `docs/truth/` names no person and no address. Adopted (D-05) |
| Verifier | Passes after correction | A reviewer with fresh context re-ran ten measurements: nine reproduced and one command was mistyped. It then found nine errors or overstatements in the first draft, all corrected (below) |
| Operator at 3 a.m. | Not satisfied with the system, satisfied with the plan | Nothing deployed since June and a watchdog that has never seen the system. The release path is first |
| Release Engineer | Passes | Nothing ships in this session; the order of landing the open work becomes a decision memo |
| Maintainer | Passes | Six files, one job each; only the log is long |
| User | Cannot judge yet | The console has not been seen running. Window 3 |
| Performance Engineer | Passes, with a gap named | No load test is planned; ten reviewers are not load. A model served on shared CPUs is a latency risk to measure if it runs locally |
| Craftsman | Asks for one removal | Fault injection across every invariant is the largest low-yield item. Reduced to a sample by consequence, the rest listed with where each is enforced |
| Store Manager | Not satisfied, and cannot be in this session | Nothing here asks a store manager anything. Named as the top unknown for session 3 |
| Release Reviewer | Not satisfied with the system | "What did it do, how do I know, why should I care" has no answer on record today. That is questions A and E |

**What the fresh reviewer changed.** A reviewer given only this file and the log was asked to
reproduce a sample and to attack the reasoning. The faults it found were all in this session's
first draft, which:

- said the last deploy was 2026-06-19, when the successful runs of 15 to 19 June skipped their
  deploy job and the true date is 2026-06-14 (re-measured by the main session);
- dated all eight alarms to July, when two are from November;
- counted the console at 34,684 lines by including its effectiveness harness, and understated
  the core's tests by 7,594 lines;
- called the watchdog an unanswered alarm, when it has never been able to observe the system;
- set a percentage of a weighted objective beside a percentage of cost from another world;
- omitted the harness's own open `harness_mis_measuring` flag;
- stated the effort split only from the window that flatters the conclusion.

Each is corrected above. The full list and the reviewer's opposite case are in `LOG.md`.

## 14. What the prompt did not ask

- **Whether a cloud environment exists at all.** It assumed a deployment to assess (H-01).
- **Where the system can be rehearsed.** The eight-core cap and the laptop's memory make this a
  first-order constraint (EX-01, M-12).
- **How much this session may spend.** It names the limits and allots nothing. Section 9
  proposes an allotment.
- **What the reviewers were promised.** The claim they arrive with decides what counts as
  backing it.
- **What an honest release looks like if the answer stays negative.** A system that shows its
  own loss, its cause and its repair may be the stronger release. To be weighed as a direction.
- **Who answers an alarm.** The gates are examined; the response to them was not asked about.
- **How this account stays true after the session.** Hence approval 3.
