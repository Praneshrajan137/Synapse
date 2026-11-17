# PLAN - SYNAPSE to the world: from session 2 to a five-day public release

**Status: 2026-11-17, end of session 2.** Written after the operator's reframe (LOG OA-7): the
release is for the whole world for five days, and the resources are larger than first stated.
This file is the plan for sessions 3 to 13. It supersedes the audience, release architecture and
session path in [`DIRECTION.md`](DIRECTION.md), whose analysis of the evidence still stands.
Evidence identifiers resolve in [`LOG.md`](LOG.md) (M, V, RD, EX, OA) and
[`TRUTH-MAP.md`](TRUTH-MAP.md) (F). Labels: **measured**, **read**, **checked** (an outside page
opened by the main session), **reported** (a subagent's return), **inferred**, **judgment** (this
session's estimate, with its basis), **dream** (a goal stated without evidence that it is
reachable).

## 0. The plan on one page

- **The real problem.** In fast grocery every item must be on the shelf at the minute it is
  ordered, fresh items spoil within days, demand peaks within the day and is hidden by
  stockouts, and stock comes from a hub several times a day. Each order trades lost sales
  against waste. Large operators build their own systems. Everyone else runs static min-max
  rules and has no way to know whether anything smarter would do better on their own store
  (section 1).
- **What SYNAPSE is uniquely placed to do.** Not to claim that AI wins, but to show, honestly
  and on real demand, where a smarter policy beats a tuned rule, by how much, and to act only
  where it has earned it. Its proof harness already does what the world's tools and benchmarks
  do not (section 1.3).
- **The release: "SYNAPSE Open Dark Store", five days, for anyone.** Four doors and a proof:
  **Watch** a live, pre-registered experiment in which SYNAPSE and a tuned rule run identical
  dark stores side by side; **Play** the store yourself against both, with or without SYNAPSE's
  advice, in your own browser; **Prove** what a smarter policy would do on your own sales data,
  which never leaves your browser; **Compete** with your own policy on an open benchmark; and
  read the **Proof**: every claim pre-registered, every decision hash-chained and verifiable
  (section 4).
- **What changes underneath.** A light decision kernel extracted from the existing code; a world
  calibrated to real hourly demand with real perishability; the agents given jobs where the
  evidence says they can matter (demand shape, shelf life, lead times, disruptions, a shared
  hub); incumbent-first governance; the proof as a map by scenario (section 5).
- **Architecture.** Static-first on a free CDN; the twin and policies running in each visitor's
  browser, so a million visitors cost nothing more than ten; one small live server per Google
  Cloud account, active and standby; Docker cloud sandboxes for heavy verification and for
  running submitted policies in isolation (sections 6 and 7).
- **Sessions.** Eleven, from 2026-11-18 to a launch on 2027-01-18, each with one outcome, an
  acceptance test and a tripwire (section 9).
- **Odds (judgment).** The floor, about 80%; the target, about 50%; the dream, about 20%.
  Section 15 says what each consists of and how we will know.

## 1. The real problem

### 1.1 What a dark store must get right

- A quick-commerce store carries thousands of items (secondary sources give 2,000 to over
  40,000, LOG reported block) and serves 1,000 to 2,000 orders a day (reported). Demand peaks in
  the evening, spikes with weather and festivals, and is censored: a stockout hides the demand
  it turned away (FreshRetailNet-50K exists to recover exactly this, LOG reported block).
- Fresh items spoil in days, so every unit ordered too many is waste and every unit too few is
  a lost order and an unhappy customer. Store ordering and replenishment have long been
  reported as the largest single cause of out-of-stocks (about 47% in a 2002 industry study,
  snippet), and inventory distortion is put at about $1.7 trillion a year worldwide (IHL, 2025,
  snippet).
- Stock records drift from the shelf: 65% of records were wrong in the standard study of one
  retailer (EX-04). A loop that trusts the record never reorders an item that is gone.

### 1.2 Who decides today, and what they lack

- Large operators build planning in-house (reported).
- Everyone else, from small dark-store chains to grocers and pharmacies, uses static min-max
  rules. Free tools such as Odoo's reordering rules are of this kind, and none of the tools
  found shows its user evidence that it beats a simple rule (reported, snippet-level).
- The missing thing is not another forecast. It is **evidence**: on my store, with my demand,
  would a smarter policy really beat the rule I have, by how much, and where would it fail?
  Vendors claim uplift without falsifiable proof; operators cannot test the claim.

### 1.3 Why SYNAPSE, and the frontier it can pass

- **Its harness already answers the question honestly.** Paired seeds, controls, a power
  analysis, a hindsight oracle, pre-registered claims, and negative results published twice
  (F-14, RD-01, RD-06). It runs on a laptop in seconds and repeats exactly (M-18, M-23).
- **The nearest frontier benchmark leaves the hard parts out.** InventoryBench (2026, NeurIPS
  listing) tests single products on weekly demand and finds that OR heuristics combined with a
  language model beat either alone, and that human-AI teams beat humans or AI alone (EX-07).
  Nothing found combines a tuned (s, S) rule, a hindsight oracle, perishability, intraday time,
  censored real demand and a hub of stores (reported). That combination is where fast grocery
  lives, and where SYNAPSE can lead.
- **No live public AI experiment has had a tuned baseline.** Project Vend and similar public
  experiments drew their audience through failures, with no classical rule to compare against
  (reported). A live, pre-registered contest with a tuned rule in the next store, and every
  decision verifiable, would be new.

## 2. What seven months built, read as a whole

| Phase | Months | What it built | What it left |
|---|---|---|---|
| Foundation | April | Infrastructure, eight agents, orchestrator, twin, API, console | Breadth: every layer of a platform exists in some form |
| Hardening and reach | May to June | Resilience, multi-city, supply-chain security, audit chain, GCP deploy, design system, the console's honesty UX | Strong engineering habits; a topology no one person can run (F-22) |
| Verification | June | Gates, coverage truth, deploy truth, substance mandate | 68 checks; a watchdog that never saw the system (F-25) |
| Agency | June to July | The closed loop: a sensor, a standing world, actuation | Autonomy in form; one heuristic in fact (F-01) |
| Proof | July to November | The uplift harness and E5 | An honest negative result and its cause (F-13, F-13a) |
| Truth | November | This session | The map of what is real |

**The lesson, in one line.** The project built breadth before evidence, then built the evidence
and found the breadth hollow at the core. The next phase is the reverse of the first: **depth at
the core, reach at the edge.** Make the few decisions that matter genuinely better where the
evidence says they can be, prove it on real demand, and reach the world through something that
costs nothing per visitor.

**What the history earned and keeps.** The harness (the project's best asset); the colour
system and the console's honesty vocabulary (reported reusable as they are, M-36); the audit
chain and its public anchoring; the typed contracts and the safety tests that caught five of
five faults (F-31); the twin's seams for outside demand (ADR-052). **What it froze.** The
streaming and graph topology, the Helm chart, the training code without trained models (M-35),
the multi-city overlay. Frozen is not deleted: it is the documented production topology for an
operator who wants it later.

## 3. The vision, the target and the floor

- **The dream (2027 and after).** The open reference for honest, governed replenishment in fast
  retail: a twin calibrated to real demand that anyone can run; an open benchmark where rules,
  learned policies, language-model agents and people compete on the hard cases; a decision engine
  a small retailer can run on its own data, acting only where it has earned it; and published
  evidence, including where it fails.
- **The target for the release.** All four doors open and working; the world calibrated to real
  hourly demand with real perishability; SYNAPSE measurably better than the tuned rule in the
  stressed scenarios where theory says rules break, reported honestly where it is not; five days
  live; the static parts left running afterwards at no cost.
- **The floor, if the sessions run slow.** Watch, Play and the Proof; the calibrated world; an
  honest result whatever its sign; five days live.

Section 15 gives the odds and the evidence each will produce.

## 4. The product the world meets

### 4.1 The first minute

A visitor lands on one page that says, in plain words: two identical dark stores are running
right now, one run by a tuned rule and one by SYNAPSE; here is what each has sold, wasted and
missed so far; here is what we predicted before the start; and here is how you can check every
decision. Then four doors.

| Door | What the visitor does | Where it runs | What makes it frontier |
|---|---|---|---|
| **Watch** | Follows the live contest: day, orders, stockouts, waste, money, the decision being made now and why | One live server; snapshots through the CDN | Pre-registered claims, an always-valid running interval, and a public hash-chained decision log anchored daily; no live public contest with a tuned baseline was found (reported) |
| **Play** | Runs a store for a simulated day or week, ordering at each delivery slot, against the rule and SYNAPSE on the same demand; can switch on SYNAPSE's advice and amend it | The visitor's browser (Pyodide) | A human-in-the-loop replenishment experiment open to anyone, far beyond a classroom's size, in a perishable intraday store; anonymous traces shared only by opt-in |
| **Prove** | Drops in a sales file (or picks a real store from FreshRetailNet-50K) and sees, on a held-out stretch of their own history, how the rule and SYNAPSE's policies would have done, with intervals, and a suggested order plan | The visitor's browser; the file never leaves it | Honest backtesting with censored-demand recovery, privacy by construction |
| **Compete** | Downloads the benchmark, writes a policy, submits it; sees the leaderboard of rules, SYNAPSE, learned and language-model entrants, the people from Play, and the hindsight bound | Static leaderboard; evaluation in isolated sandboxes | An open benchmark for perishable, intraday, hub-coupled replenishment with a tuned rule and an oracle; none combining these was found (reported) |
| **Proof** | Reads what was claimed before the start, the map of where each part helps, the negative results and their causes, and how to verify | Static | The project's honesty, made the product |

### 4.2 What stays after the five days

The live contest stops; its full record, final analysis and decision log stay. Play, Prove,
Compete and the Proof are static and keep running on the free CDN indefinitely (inferred from
the CDN's free terms, LOG reported block). A five-day event becomes a lasting public good.

### 4.3 What the visitor can never do

Change the live contest. Fairness and safety both require it: the public watches the live stores
and plays in its own. The floor has no public write path at all (section 8, bet B6).

## 5. The science underneath

### 5.1 The decision kernel

- **What.** A small package, `synapse_kernel`, extracted from code that exists: the twin engine,
  the tuned (s, S) rule, the structure-aware base-stock arm, the Sentinel's newsvendor logic, the
  objective and its metrics. Pure Python and NumPy only (M-33: the engine already needs only six
  light packages).
- **Why.** One kernel runs in three places: the proof harness, the live server and the browser.
  What visitors play against is what the proof measured.
- **Acceptance.** Exact parity with the harness on fixed seeds (the incumbent's cost equal to the
  last digit), as M-18 and M-23 already show is possible.

### 5.2 A truer world

| Change | Why | Evidence it is needed |
|---|---|---|
| Waste takes stock, batch by batch, by age (first in, first out) | Without it, over-ordering costs nothing and freshness has nothing to decide | F-30 |
| Many items with skewed demand and an intraday profile | Ten equal items hide fast and slow movers and the evening peak that caused the measured loss | F-13a, M-09 |
| Demand calibrated to FreshRetailNet-50K, with stockout-hidden demand recovered | Hourly sales and stock status for 863 perishable products in 898 stores (licence CC BY 4.0) | EX-03, LOG reported block |
| Trace-driven runs on real store histories | External validity: policies compared on demand that really happened | FRONTIER row 4 |
| A hub with limited stock and trucks serving several stores (target tier) | The one structure where coordination between agents can pay | F-29, T-001 |
| Shocks as pre-registered cells: demand spike, supplier default, monsoon, cold start | Where a static rule is weakest | `uplift/scenarios.py` |

Each change moves the baseline, so the tuned rule is re-tuned and the controls re-run, which now
takes minutes (F-14).

### 5.3 The agents, with jobs where they can matter

| Agent | Its job in the release | Mechanism | Status at the end of session 2 |
|---|---|---|---|
| Demand Prophet | The day's demand shape per item, fitted on real data with censoring recovered | Information | Fallback constant (F-02) |
| Inventory Sentinel | Order quantities from forecast, lead time and shelf life | Information | Binds every decision; mis-estimates the rate (F-13a) |
| Freshness Guardian | Batch ages and expected waste; markdown proposals (target tier) | Information | Refused by the harness request (F-03) |
| Supplier Trust | Lead-time distribution per supplier | Information | Configured prior (F-02) |
| Disruption Shield | Recognises the regime the store is in | Adaptation | Given no features (F-02) |
| Orchestrator | Incumbent-first arbiter, quantity guard, audit chain, outcomes | Governance | Argmax of self-reported confidence (F-04) |
| Hub allocator (target tier) | Splits scarce hub stock across stores | Coordination | Does not exist |
| Pricing Oracle | Markdowns of near-expiry stock (target tier) | Information | Refused by the harness request (F-03) |
| Routing Navigator | Deferred: the twin has no spatial model of delivery | - | Frozen |
| Sustainability | Reports waste and emissions as outcomes | Reporting | Fallback (F-02) |

Each agent earns its place by ablation, against a rule written before the run: a part that
changes no measured outcome in any pre-registered cell is shown as "not used in this workflow"
(DECISIONS D-5).

### 5.4 Governance that lets SYNAPSE act safely

- **Incumbent first.** The tuned rule decides unless the pre-registered map trusts a challenger
  for the regime the store is in and a deterministic guard passes its quantity (half to twice the
  rule's; DECISIONS D-2, D-4).
- **No dead ends.** Below the confidence floor the incumbent acts, so a decision never stops
  waiting for nobody (fixes F-08).
- **Every decision recorded with what then happened**, hash-chained, anchored daily in public
  (fixes F-10; reuses ADR-033).
- **The degraded flag is read**, not only recorded (fixes F-02a).

### 5.5 The claims, pre-registered before launch

| Claim | Cell | Test | What would prove it false |
|---|---|---|---|
| C1 SYNAPSE is never worse than the tuned rule by more than the guard allows | Every cell | Paired cost difference, upper bound of a 95% interval | An interval above the guard's bound |
| C2 SYNAPSE beats the tuned rule where demand shape matters | Primary cell, calibrated | Paired cost, held-out seeds | A 95% interval that includes zero |
| C3 SYNAPSE beats the rule in shocks | Demand spike, supplier default, monsoon | Same | Same |
| C4 Coordination pays in a constrained hub (target tier) | Hub cell | Coordinated allocator against proportional allocation | Same |
| C5 Live: the gap measured in public stays inside the pre-registered range | The live contest | An always-valid confidence sequence, monitored daily | The sequence leaving the range |
| C6 People with SYNAPSE's advice beat people alone and the rule (exploratory) | Play | Descriptive, by opt-in traces | Reported as found, either way |

The numbers that define "beats" are written in session 7 from the power analysis, before any
result on the new world is seen. A negative result is published as prominently as a positive
one, as the project has already done twice.

## 6. Architecture for the whole world

| Layer | What | Where | Scales to | Cost |
|---|---|---|---|---|
| Front door | Static site: Watch, Play, Prove, Compete, Proof | Cloudflare Pages, free plan | Any audience; static requests reportedly unlimited (snippet) | $0 |
| In-browser engine | Pyodide plus `synapse_kernel` in a Web Worker | The visitor's machine | One visitor at a time, each on their own machine | $0 |
| Live contest | The kernel's worlds on an accelerated clock, the real governed decision path in-process, the audit chain | One small VM on Google Cloud account A | Bounded: it serves one snapshot | About $12 to $25 for six days at e2-standard-2 rates (reported prices, inferred hours) |
| Snapshot delivery | A JSON snapshot every few seconds, cached at the edge with a short TTL | Cloudflare proxy in front of the VM, needs a domain (D-17) | Viewers hit the cache, not the server | About $10 a year for a domain |
| Fallback delivery | Hourly snapshots published as static files | Pages deploys (500 a month allowed, reported) | Any audience | $0 |
| Standby | A tested image and restore on account B; warm during the release | Google Cloud account B | Takes over in under 30 minutes (target) | About $10 |
| Heavy verification | Full suites, full-size proof runs, load tests, browser matrix | Docker cloud sandboxes, Large or XL | 8 to 16 vCPU, 16 to 32 GB | From the $250 credits (EX-06) |
| Benchmark evaluation | Submitted policies and language-model entrants, each in its own microVM | Docker cloud sandboxes | Isolation by construction | From the credits |
| Training | Demand-shape and censoring models on FreshRetailNet-50K | Colab (200 units) or a sandbox CPU | One-off | From the units |

**Speed budget (judgment from M-34 and the reported slowdown).** A simulated day takes about 0.44
s natively and an estimated 1.3 to 2.2 s in a browser. A visitor's day of play therefore runs as
fast as they can decide. Loading Pyodide with NumPy costs a few seconds once, cached afterwards.

**What does not ship.** Kafka, Neo4j, Redis, Feast, MLflow, Prometheus, Grafana, the Helm chart,
the language-model server in the hot path. The live server runs the governed decision path
in-process, as the harness already does (F-14), with Postgres or SQLite for the audit chain.

## 7. Resources, mapped

| Resource | Stated | Use | Planned spend | Caution |
|---|---|---|---|---|
| Google Cloud account A | $300 trial | Rehearsals, then production | Under $40 | Trial terms: "You haven't previously signed up for the Free Trial" (reported, quoted from Google's page); eight cores at a time; ends three months after start (EX-01) |
| Google Cloud account B | $300 trial | Standby, and production if its trial ends later | Under $30 | Same; whichever trial ends later hosts the release |
| Docker cloud sandboxes, three accounts | $250 each | Verification boxes for the sessions; benchmark and language-model evaluation | $150 to $400 | "Limit one per user and account"; claim by 2027-01-31; expires six months after claiming (EX-06) |
| Claude Code | Max plan; about $120 across ten sessions | The implementation sessions | All of it | The binding resource: see 9.2 |
| Colab | 200 units | Training the demand-shape and censoring models; optional policy learning | Under 100 units | Expiry not stated |
| Cloudflare | Free plan | Static site, CDN, DNS | $0 | Nothing polled may pass through a Worker (100,000 requests a day, reported) |
| A domain | Not yet held | Edge caching of live snapshots | About $10 a year | The only cash cost; D-17 |

**On the terms (stated plainly).** Google's trial is for customers who have not had one before,
and Docker's credit is one per user and account. If several accounts belong to one person, a
provider may end the trial or void the credit. The plan is built so that no single account is
essential: the front door, Play, Prove, Compete and the Proof live on the free CDN, and the live
contest can fall back to hourly static updates. Whether each account is eligible is the
operator's to confirm (D-16).

## 8. The calculated risks

| Bet | Upside | Downside | Odds (judgment) | Cost | Tripwire and fallback |
|---|---|---|---|---|---|
| B1 The twin runs in the browser | Zero marginal cost at any audience; private Prove | Slow or heavy on phones | 75% | Part of one session | If a day takes over 5 s on a mid laptop, Play runs on a server with rate limits, or on precomputed days labelled as such |
| B2 Calibrate to FreshRetailNet-50K | External validity; real perishable demand | Chinese fresh retail is not Indian quick commerce; censoring recovery is hard | 70% | One session | Declare the domain gap on the Proof page; keep the declared world as a second cell |
| B3 A live, pre-registered public contest | None like it found; attention earned by honesty | SYNAPSE may lose in public | 85% that it runs; the sign is unknown | One session plus hosting | A pre-registered loss is reported as one; incumbent-first bounds the size of any loss |
| B4 The world plays the store | A human-AI study at a scale no classroom reaches | Few players; noisy data | 60% for useful data | Part of two sessions | Results reported as exploratory |
| B5 An open benchmark | Others build on SYNAPSE; it becomes a reference | Few submissions in five days | 50% for any outside submission | One session | Seeded with every baseline and the people from Play |
| B6 No public write path | Fairness and safety by construction | Less interaction | 95% | None | The crowd-controlled store stays a dream |
| B7 Coordination in a hub | The fair test of the multi-agent premise | It may not pay | 40% for a clear win | Part of one session | Reported either way; cut first if the pace slips |
| B8 Language-model entrants on the benchmark | Tests the 2026 OR-plus-model finding in a harder setting | CPU inference is slow | 60% to run; result unknown | Docker credits | Fewer scenarios; reported as a pilot |

## 9. The sessions

### 9.1 The path

Eleven sessions, 2026-11-18 to 2027-01-18. Dates are targets; the tripwires decide cuts.
"Verified" means on the laptop or in a Docker sandbox before any labelled CI run, the fast regime
that the pace depends on (F-32).

| # | Dates | Outcome | Acceptance test | Tier |
|---|---|---|---|---|
| 3 | Nov 18 to 20 | Decide and land: definition of finished from this plan; D-14 to D-20; PRs #87, #91, #90, #89 merged in order with your yes; the ledger worktree committed; one Docker sandbox set up as the verification box | `main` green; the decision-core suite and the twelve-replicate proof run in the sandbox, timed | Floor |
| 4 | Nov 21 to 26 | The decision kernel extracted; the shape-aware challenger fitted on held-out seeds | Exact parity with the harness on twelve seeds; the challenger measured against the rule, pre-registered | Floor |
| 5 | Nov 27 to Dec 2 | The truer world: batches that spoil by age, skewed items with an intraday profile, demand calibrated to FreshRetailNet-50K with censoring recovered; the hub (target) | Spoilage rises with stock held (a test that fails today); calibration report against the data; rule re-tuned; controls pass | Floor (hub: target) |
| 6 | Dec 3 to 8 | Governance and challengers: incumbent-first arbiter and guard; outcomes recorded; the degraded flag read; perishable-aware and disruption-aware challengers; the Shield as regime detector | Tests written to fail before each change; ablation arms runnable | Floor |
| 7 | Dec 9 to 13 | The proof as a map: claims C1 to C6 pre-registered with their numbers; every cell run; trace-driven backtests on real store histories | Controls pass; the map with intervals reproduced by one command | Floor |
| 8 | Dec 14 to 19 | The browser lab: the kernel in Pyodide; Play with the advice condition; Prove on a file or a FreshRetailNet store | A simulated day under 3 s on a mid laptop; no network request carries the visitor's file (checked in the browser) | Floor (Prove: target) |
| 9 | Dec 20 to 25 | The public site: Home, Watch, Play, Prove, Compete, Proof, built static-first from the design system | Works with the live server down; three cold readers can say what it did, how they know and why it matters within five minutes | Floor |
| 10 | Dec 26 to 31 | The live contest service; first cloud rehearsal on account A; restore drill on account B | 48 hours unattended; snapshots fresh within 10 s at the edge; restore on B under 30 minutes; machines stopped after | Floor |
| 11 | Jan 1 to 6 | Compete: the benchmark packaged with every baseline; language-model entrants run in sandboxes | A test submission from an outside fork scores; the leaderboard renders | Target |
| 12 | Jan 7 to 12 | Hardening for the world: defaults removed, headers and limits, uptime checks that reach a phone, a runbook, a load test at ten times the expected peak, attribution and privacy notes | Each failure injected once and recovered; the load test passes with under 1% errors at the edge | Floor |
| 13 | Jan 13 to 18 | Dress rehearsal (72 hours), claims frozen and published with their hash, go or no-go, launch on 2027-01-18 | The release bar of section 12 met in rehearsal | Floor |

**The five days: 2027-01-18 to 2027-01-23**, on whichever Google Cloud account's trial ends
later. A daily public note reports the running interval, labelled as interim. The final analysis
is published within 24 hours of the end.

### 9.2 Making ten sessions fit the Claude budget

- **One outcome a session**, with its acceptance test written first.
- **A small reading set**: this plan's row, the log's "How to resume", and the files the outcome
  touches. No session rereads the whole project.
- **Verification where it is cheap**: the laptop or a sandbox, never a wait on a labelled CI run
  for a result that can be had locally.
- **At most two subagents at a time**, each with a cap on calls (LOG D-03).
- **Commit at each verified step**, so a usage limit costs minutes, not a session.

### 9.3 Tripwires

| When | Check | If it fails |
|---|---|---|
| End of session 5 | Sessions 3 to 5 done by 2026-12-04 | Cut the hub and the language-model entrants; session 11 becomes a buffer |
| End of session 8 | B1's speed and size budget met | Play on a server or on precomputed days (B1's fallback) |
| End of session 10 | The rehearsal ran 48 hours | Production moves to account B; if both fail, the live contest publishes hourly static snapshots |
| Session 13 | The release bar met | Launch the static doors and publish the contest as a recorded run, labelled as such |

## 10. The launch week

- **Day 0 (Jan 17).** Claims frozen; their hash and the launch commit published. Uptime checks
  armed. Standby warm on account B.
- **Days 1 to 5 (Jan 18 to 22).** One check a morning and one an evening against section 12; a
  short public note each day; nothing changed in the contest's decision code during the five
  days, by pre-registration.
- **Day 6 (Jan 23).** The live server stopped; the final analysis, the full decision log and its
  anchors published; the static doors left running.
- **Day 7 onward.** Both trial accounts emptied of running resources before their credits lapse.

## 11. Pre-mortem: it is 2027-01-25 and the release failed

| Cause, most likely first | How the plan answers it |
|---|---|
| Nobody came | The static doors keep working after the five days; a short write-up and a two-minute video in session 13; launch timed for a weekday morning in the US and evening in India (D-18) |
| A spike of visitors took the live server down | Visitors never reach the server: they read cached snapshots; play runs on their own machines |
| SYNAPSE lost in public | Pre-registered; incumbent-first bounds the loss; the result is reported as the honest test the release promised |
| An expert dismissed the world as a toy | Calibrated to real demand; the domain gap stated; the declared world kept as one cell, not the only one |
| The browser lab was too slow on phones | Phones get a lighter mode; the server fallback (B1) |
| A trial account was ended | No account is essential (section 7) |
| Sessions ran slow and the scope did not fit | Tripwires cut in a fixed order: the hub, the language-model entrants, Prove, Compete |
| A secret or a write path was abused | No secrets in the client; no public write path in the floor |
| A licence or privacy complaint | FreshRetailNet-50K attributed under CC BY 4.0; visitors' files never leave their browsers; play traces shared only by opt-in and without personal data |

## 12. The release bar, and the scorecard targets

| Frontier row (FRONTIER.md) | Today | At release (target) | How it is measured |
|---|---|---|---|
| 1 Cost against a tuned rule | 56% worse (M-23) | Never worse beyond the guard; better in stressed cells, pre-registered | Claims C1 to C3 |
| 2 Knowing where the rule loses | One cell, untuned bound | A map over all cells, with intervals | Session 7's map |
| 3 Internal validity | Level in design | Level, and pre-registered in public | Hash of the claims published before launch |
| 4 External validity | Declared world | Calibrated to real hourly demand; trace-driven backtests | Calibration report; backtests |
| 5 Reproduction by a stranger | Minutes, from an export | One command; anyone in a browser | Prove and Compete |
| 6 Assortment and demand | Ten uniform items | Skewed items with an intraday profile from data | The world's calibration report |
| 7 Operational structure | One store, waste a clock | Waste by age; shocks; a hub (target) | Tests that fail today |
| 8 A named user | None | Anyone with sales data, a student, a researcher | Use of the doors in the five days |
| 9 Architecture earns its complexity | One heuristic | Each part's contribution measured by ablation | The map |
| 10 Agents that act | Category errors | Each action appropriate and recorded with its outcome | Session 6's tests |
| 11 Path to production | None since June | Rehearsed twice, failover drilled | Sessions 10 and 13 |
| 12 Reliability | Nothing | Static doors 99.9%; live snapshots 99.5% over 120 h (36 minutes down); outage known within 2 minutes; restore under 30 minutes | Uptime checks during the release |
| 13 Cost | About $70 estimated | Under $120 of credit; $10 cash for a domain | Billing pages |
| 14 First minute | Not seen with data | A visitor can say what happened and how they know within one minute | Cold readers in sessions 9 and 13 |
| 15 Checks able to fail | Safety yes, quality no | A thirty-second quality check on every change | The fast check from session 4 |
| 16 No exposure | Defaults published | None in the client; no public write path | Session 12's review |
| New: public verifiability | Audit chain exists, unused publicly | Every live decision hash-chained, anchors published daily | Anyone can verify the chain |

## 13. Frozen, cut or deferred, deliberately

- **Frozen in the repository, documented as the production topology:** Kafka, Neo4j, Redis,
  Feast, MLflow, Prometheus, Grafana, the Helm chart, Linkerd, KEDA and Flagger files, the k3s
  files, the Oracle compose path, the Mumbai overlay, the operator surfaces of the console
  (operations, steering, override, ingress, sign-in).
- **Deferred:** routing and riders (the twin has no spatial model); multi-city; training the
  deep models (no trained model exists, M-35, and none is needed for the release's claims);
  record inaccuracy beyond one stress cell; a language model in the hot path.
- **Cut if the pace slips, in this order:** the hub, the language-model entrants, Prove, Compete.

## 14. Decisions owed now

Details and options are in `DECISIONS.md` (D-14 to D-20). Each has a default this plan assumes.

| # | Decision | Default assumed |
|---|---|---|
| D-14 | The live contest's clock | Accelerated: one simulated day per real hour, 120 simulated days over the five |
| D-15 | Play traces | Collected only with opt-in, anonymous, released under CC BY 4.0 after the event |
| D-16 | Account eligibility, and which trial ends later | You confirm both trials and the Docker credits are eligible; the later-ending trial hosts the release |
| D-17 | A domain for edge caching | Yes, about $10 a year |
| D-18 | Launch timing and channels | 2027-01-18; a write-up, a short video, and posts where operations and machine-learning people read |
| D-19 | Licences for what is published | Code Apache-2.0 as now; derived data and traces CC BY 4.0 with attribution |
| D-20 | Language models in the release | Explanations generated from the computed numbers, no model in the hot path; models only as benchmark entrants |

## 15. Measured, intended and dreamed: the odds and how we will know

| Tier | Contents | Odds (judgment) | Basis | We will know by |
|---|---|---|---|---|
| Floor | Watch, Play, Proof; the calibrated world with waste by age; governance; five days live | About 80% | Every part reuses measured code paths (M-18, M-23, M-33, M-34); the riskiest piece (B1) has a fallback | The end of session 10 |
| Target | The floor plus Prove, Compete, the hub, disruption challengers, language-model entrants | About 50% | Depends on keeping the fast regime for eleven sessions (F-32); the record shows both regimes (M-27) | The tripwire at session 5 |
| Dream | The target plus outside submissions, a released human-AI dataset, a real retailer's data run through Prove with permission, a preprint | About 20% | Depends on audience and on people outside the project | A week after the release |

**What would change these odds.** Up: session 4 finishing inside five days; B1 passing its
budget in session 8 on the first try. Down: any session taking more than ten days; a provider
ending an account; FreshRetailNet-50K proving unusable for calibration.

**The single sentence the release should earn.** "SYNAPSE ran a dark store in public for five
days next to a tuned rule, on demand drawn from real stores, said in advance what it would
prove, and let anyone check every decision, play the store themselves, and test it on their own
data."
