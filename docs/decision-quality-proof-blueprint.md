# Part I — Diagnosis what is actually

Part I — Diagnosis: what is actually wrong
Not “17 tasks remain.” Four findings, each evidenced.

1. The effort is inverted. Verification is larger than the thing verified: scripts/ 17,962 + tests/ 15,126 = 33k lines of proving vs agents/ 19,696 lines of intelligence. frontend/src at 32,087 lines is the single largest mass. The apparatus for proving things about the system is more developed than the system.
2. One file gates the entire intelligence half.
published_checkpoints.json
holds only **placeholder**. Consequences, all traced: every agent takes the degraded path → confidence = FALLBACK_CONFIDENCE, a constant → the real conformal machinery (which works, and whose test found a genuine ~80% under-coverage bug) has no input → C38, C40, C45, C46 SKIP → C69 FAILs. A single unpublished artifact collapses five gates and the entire confidence contract.
3. Zero of 64 gates have been proven capable of failing. C72: 14 declare a falsification, 49 declare none, none was ever probed. gate-mutations.yaml admits “C72’s registry row can never report PASS outside –sweep” — and no workflow runs –sweep. The accountability apparatus is itself unaccountable.
4. The finding nobody in this project has surfaced — and the most important one:

The uplift experiment cannot produce a meaningful number, even when run correctly, because the twin has no exploitable structure.

Read
engine.py
as an operations researcher would:

Property Code Consequence
Demand rng.exponential(1/(rate × demand_mult)) stationary Poisson
SKUs {f”sku_{i}“: 100.0 for i in range(10)} 10 independent, identical
Lead time rng.uniform(30,120) × lead_time_mult i.i.d., uncorrelated with demand
Delivery rng.uniform(10,45) + N(0,3) no rider pool, no queue, no capacity
Spoilage 0.01 × mult, reset to 1.0 decoupled from order quantity
For stationary Poisson demand, independent items, i.i.d. lead times, and no capacity coupling, a base-stock (s,S) policy is provably near-optimal. That is textbook inventory theory. The baseline arm is the optimal policy for this world.

So: run the uplift experiment today and it returns ~0 uplift. That result would be read as “the agents aren’t better.” It actually means the world is too easy to be better in. Publishing that number would be the most expensive mistake available to this project — a true measurement of a meaningless quantity.

And the M-Competition evidence sharpens it: 40 years of replicated results say complexity does not beat simplicity on point accuracy. Where a coordinating multi-agent system should win is decision quality under shocks, binding constraints, and multi-objective tradeoffs — precisely what inject_shock and GuardrailEngine exist for, and precisely what the current twin does not exercise.

Part II — Strategy
Make the instruments trustworthy, make the world worth deciding in, prove the measuring device can detect an effect, and only then measure — on real data, against a published benchmark.

Why this order, and not the obvious one. The task list implies train model → measure uplift. That sequence produces a model whose value cannot be demonstrated and a number that cannot be interpreted. Phases 0–2 are not overhead; they are what make Phase 4’s number mean something.

Alternatives rejected:

Alternative Why rejected
Finish the remaining audit tasks, ship Closes checkboxes, leaves all four findings intact
Train the model first (fastest visible win) Yields a model, no evidence it helps; the uplift number is still noise
Replace the twin with a real data feed No live retail data source exists at $0; loses controlled shock injection, which is where consensus should win
More frontend 32k lines already correctly report “nothing to trust yet.” Marginal value ≈ 0 until (a) is real
Tradeoff accepted: ~10 weeks before a headline number, instead of ~2. In exchange, the number is defensible against a hostile expert.

Part III — The plan
Phase 0 — Make the instruments trustworthy (1 week, unblocks all measurement)
Task 1: Prove one gate can fail, then prove all fourteen can. Add python -m scripts.audit.gate_fault_injection –sweep as a blocking step in truth-gates.yml. Do not first declare the 49 missing operators — 49 unverified declarations convert a visible gap into false assurance, the exact trade I-7 forbids and the reason 12.1 correctly left C67 undeclared. Prove the mechanism on the 14 that already declare one; expect survivors.

Tests: the sweep’s own report is the test. Each of the 14 must show its mutant killed. A survivor is a gate that does not enforce — file it as a defect against that gate, not against the sweep.
Demo: C72 moves from SKIP: no falsification was probed to a probe count with named survivors. For the first time in this repo’s history, a gate is proven to fail when its subject breaks.
Task 2: Execute the 2,000 unverified frontend lines. cd frontend && pnpm install && pnpm typecheck && pnpm typecheck:spec && pnpm vitest run spec/effectiveness/**tests** src/surfaces/**tests**. Five fast-check property files were authored and never compiled or run; getDiagnostics is silent in this workspace (proven by probe). Property 31 sits under src/, so it is inside pnpm build’s tsc pass, and build gates e2e, e2e-visual, e2e-harness, mobile-lighthouse, effectiveness-ratchet, fe-invariants — one type error there skips the entire console-effectiveness spine.

Tests: a fast-check counterexample is a success — it means the property works. Fix the subject, not the property.
Demo: five files reporting real pass counts, and a green pnpm build that is green for a checked reason.
Task 3: Replace hardcoded numRuns with an inherited profile. fc.configureGlobal({ numRuns: Number(process.env.FC_PROFILE_RUNS ?? 20) }) in
setup.ts
; delete { numRuns: 100 } from all five files (a per-call value overrides the global, so adding the global alone changes nothing); flip the inventory gate to forbid hardcoded numRuns, mirroring its max_examples rule.

Why: the Python side inherits from conftest.py profiles (dev=10 local, 500 CI). I codified numRuns >= 100 into a gate, which violates I-0 on a throttling laptop. This restores symmetry.
Demo: FC_PROFILE_RUNS=10 pnpm vitest run is laptop-cheap; CI runs 500.
Task 4: Fix C64 properly, and un-bend the README. Rename the 10 non-propagating steps to carry ADVISORY, updating their blocking-steps.yaml declarations in the same commit (the coupling is not a blocker; moving both halves together is this repo’s own convention). Then fix doc_truth::_claim_readme_headline_counts to compensate for its own recursion guard, and restore README to the counts make verify-claims actually prints. Better still — and this supersedes my earlier proposal: put the headline inside generated:begin/end markers so no human ever transcribes it. That removes the transcription step that created the fixpoint.

Demo: C64 PASS. README states a number a human can reproduce with one command.
Phase 1 — Make the world worth deciding in (3–4 weeks — the real work)
Design rule for this phase: every element added must answer “which agent decision does this make matter, and which one currently cannot matter?” Nothing is added for realism’s sake.

Task 5: Write
ADR-055-twin-decision-relevance.md
before any code. Record the finding from Part I with its inventory-theory justification, the five structures to add, the agent decision each unlocks, and the falsifiable claim: after this phase, a base-stock (s,S) policy is measurably sub-optimal on this twin.

Demo: a reviewable decision record that makes the rest of the phase falsifiable rather than aesthetic.
Task 6: Non-stationary demand. Replace constant-rate Poisson with a time-varying intensity: intra-day double peak, day-of-week, promotion pulses, weather shock. Calibrate the shape from M5-derived seasonality, not invented literals.

Unlocks: demand_prophet. Forecasting has zero value under stationary demand — this is the single change that makes the flagship agent’s output actionable.
Tests: property — a perfect-foresight policy must beat (s,S) by a detectable margin. If it cannot, the non-stationarity is too weak to matter.
Demo: an intensity plot over 14 simulated days, and a measured (s,S) regret > 0.
Task 7: Capacity and queueing. A finite rider pool and finite pick stations, with simpy.Resource. Delivery time becomes queue-dependent, not uniform(10,45). Also fix the docstring that claims an OSRM travel estimate the code never makes.

Unlocks: routing_navigator and dispatch prioritisation. With infinite capacity, dispatch policy is a no-op.
Tests: property — under load, utilisation → wait time must be monotone and super-linear near saturation (a queueing signature). This is the structure that punishes uncoordinated decisions.
Demo: a utilisation/wait curve showing the knee.
Task 8: Correlated lead times and supplier state. Lead time correlated with demand (busy suppliers are slow) and auto-correlated across days; per-supplier reliability that supplier_trust can learn.

Unlocks: supplier_trust, inventory_sentinel safety-stock decisions. Under i.i.d. lead times a static safety stock is optimal.
Tests: property — a supplier-aware reorder policy beats a supplier-blind one.
Demo: uplift of supplier-aware over supplier-blind, measured.
Task 9: Perishability coupled to order quantity, and SKU substitution. Spoilage as a function of age-at-arrival and order size (bulk ordering raises spoilage); cross-SKU substitution so a stockout partially diverts demand.

Unlocks: freshness_guardian, pricing_oracle, and the genuine multi-objective tension — spoilage vs stockout vs holding cost vs SLA — where consensus should beat single-objective rules.
Tests: property — no single-objective policy is Pareto-optimal across all four KPIs. This is the mathematical precondition for consensus to have room to win.
Demo: a Pareto frontier with the four single-objective policies plotted off it.
Phase 2 — Validate the measuring instrument (1–2 weeks — the scientific core)
This phase exists because of a gap in the audit spec itself. R2.6 specifies a negative control. Nobody specified a positive control. Without one, a zero result is uninterpretable: is the system not better, or is the instrument blind?

Task 10: Negative control — the instrument must not hallucinate an effect.

gherkin

Given the Consensus_Arm is replaced by a byte-identical copy of the Baseline_Arm
When the Uplift_Harness runs at MIN_POWERED_REPLICATES per arm
Then the 95% interval of headline uplift contains zero
And the Uplift_Gate does not report a proven gain
Demo: a false-positive rate consistent with the stated α.
Task 11: Positive control — the instrument must detect a known effect. (NEW) Inject a structure with a known optimal policy, run an oracle arm that exploits it against the baseline, and require detection.

gherkin

Given the twin carries a known-exploitable demand seasonality
And an Oracle_Arm plays the analytically optimal policy for it
When the Uplift_Harness runs at MIN_POWERED_REPLICATES per arm
Then headline uplift is positive with its 95% interval excluding zero
And the measured effect is within tolerance of the analytic optimum
Why this is the most important task in the plan: it converts “we measured zero” from an ambiguous non-result into a real finding, because the instrument is now known to have the power to see an effect of that size. Without it, Phase 4 is unfalsifiable.
Tests: a power curve — effect size vs detection probability at the chosen replicate count.
Demo: “this harness detects a ≥X% effect with ≥80% power at N replicates.” That sentence is what makes Phase 4 publishable.
Task 12: Make the honest predicate the production path. uplift/uplift_floor.py::is_proven_uplift and ratchet_to_measured are imported only by three test files — tested and unreachable. Route
uplift_truth.py
through is_proven_uplift; honour incomplete, within_fidelity_bound, and replicate count; exit 2 (unavailable) rather than 0 on an incomplete artifact.

Tests: mutation — replacing is_proven_uplift with a stub returning the opposite verdict must change the gate’s exit code (R2.4). Today it would not.
Demo: the committed {“headline_uplift”: 0.0, “incomplete”: true} artifact flips C60 from PASS to UNAVAILABLE. The tautology dies.
Phase 3 — Real intelligence on real data (3–4 weeks)
Task 13: Ingest M5 (Walmart) as the non-synthetic source. ~42,000 hierarchical daily series, 3,049 products × 10 stores × 3 states. Free, and it satisfies R4 (“the loop has only ever run on its own simulation”) with a real dataset rather than a synthetic feed.

Why M5 specifically: it is the only choice that gives an external published leaderboard, and its Uncertainty track scores quantiles — mapping exactly onto demand_prophet’s CRPS/pinball training and conformal intervals. It converts “we trained a model” into “our model scores X against a published benchmark.”
Tests: the existing non-synthetic-ingestion property (Property 29) becomes genuinely exercised rather than passing over a stub.
Demo: a real forecast for a real Walmart SKU, with provenance recording feature_source as the M5 feed.
Task 14: Train and benchmark demand_prophet on M5 Uncertainty. Free GPU (Kaggle T4×2, ~30h/week) per the existing runbook. Record the measured score against the published leaderboard, including the seasonal-naive baseline. Verify the exact leaderboard values at implementation time — I confirmed the competition structure and winners externally but not the numeric scores.

Why this is the highest-integrity move available: it makes the intelligence claim externally auditable instead of self-certified. And per the M-Competition’s own replicated finding, expect the sophisticated model to be competitive, not dominant on point accuracy — plan the narrative around calibration quality and the Uncertainty track, where conformal intervals genuinely shine.
Tests: held-out coverage_p90 ≥ 0.85 (INV-DP-002) recomputed by the gate, not trusted from the sidecar.
Demo: a leaderboard-relative score, and C38/C40 flipping SKIP → PASS.
Task 15: Publish the checkpoint and let five gates flip themselves. Publish to HF Hub, land the real registry entry. The runbook and validators already exist.

Why sequenced here and not first: published now, its value is undemonstrable; published after Phases 1–2, its contribution to decision quality is measurable.
Demo: one commit flips C38, C40, C45, C46 SKIP → PASS and clears the C69 FAIL. The confidence contract becomes real: confidence stops being FALLBACK_CONFIDENCE and starts being 1/(1+mean_rel_width) from a live conformal interval. That is the moment the honest-degradation machinery starts doing the job it was built for.
Phase 4 — Measure, ratchet, anchor (1–2 weeks)
Task 16: Run the powered experiment in the job that evaluates it. Regenerate the artifact in the same CI job as the gate (R2.7); refuse any artifact read from version control (R2.8).

Demo: a real headline uplift with a confidence interval, from a completed, powered, fidelity-bounded run — on a twin where being smart is possible and with an instrument proven able to detect it.
Task 17: Ratchet the floor to the measured lower bound. Only through ratchet_to_measured against a PoweredProof from the same job.

Demo: UPLIFT_FLOOR above 0.0 for the first time, admitted by evidence rather than by edit.
Task 18: Anchor the chain externally. C67 reports chain=unverifiable, 0 anchor file(s). Publish anchors to a free external log (OpenTimestamps/Rekor). A tamper-evidence chain nobody outside can check is a strong internal control and a weak external claim.

Demo: a third party verifies the audit chain without trusting this repo.
Part IV — Three decisions I need from you
1. Do you accept the ~10-week sequence, or do you need a visible win sooner? If sooner: Phase 0 (1 week) + Task 15 (publish a model) gives five gates flipping green in ~2 weeks. But the uplift number stays meaningless. I recommend the full sequence and I’d rather say so than optimise for your approval.

1. Is the M5/Walmart benchmark acceptable as “real data”? It is retail demand, not quick-commerce — daily, not 10-minute. The alternative is synthetic-but-realistic, which forfeits the external benchmark. My judgment: take the benchmark; document the domain gap explicitly rather than pretending it away.
2. AD-12 / real-stack (carried over, still open). The JTBD suite requires window.__atlasHarness, which by AD-12 exists only in dist-e2e. Recommendation: inject it via Playwright addInitScript instead of bundling — that dissolves the tension entirely rather than amending the ADR.

Part V — How we will know it worked
Not “tests pass.” These:

Claim Evidence that settles it
The gates enforce ≥1 mutant killed per declared falsification, in CI
The world rewards intelligence (s,S) regret > 0; no single-objective policy on the Pareto frontier
The instrument can see Power curve: ≥80% detection of a ≥X% effect at N replicates
The model is real M5 Uncertainty score vs published leaderboard; coverage_p90 ≥ 0.85 recomputed
Decisions are better Uplift interval excluding zero, from a regenerated powered artifact
Accountability is external A third party verifies the chain
Part VI — Deliberately not doing
New frontend features. 32k lines already correctly report “nothing to trust yet.”
Declaring the 49 missing falsification operators. Unverified declarations are worse than a visible gap (I-7).
Kubernetes/Helm breadth. C12/C13 are honest skeletons; a single GCP VM matches the $0 constraint.
Fixing C44. Windows-only FileNotFoundError on a pnpm path; Linux CI is unaffected. Guard the walk, don’t chase it.
Deleting .gl_scratch/uplift-wt/ (a committed second copy of the tree) — worth doing, but it is hygiene, not leverage. Batch it into Phase 0 only if it costs minutes.
Two things I want to flag honestly before you decide. My Part I finding #4 rests on reading engine.py plus inventory theory — it is an analytical argument, not a measured one. Task 6’s (s,S)-regret test is what would falsify it, and it should be run early; if (s,S) regret is already meaningfully positive on today’s twin, Phase 1 shrinks substantially. And I did not verify the M5 numeric leaderboard scores, only the competition’s structure and winners.

Does this plan look good, or would you like me to adjust anything — in particular the Phase 1 scope, which is the largest and the one I’d most expect you to push back on?

Est. Credits Used: 24.04
Elapsed time: 11m 25s

Checkpoint
Restore
now create the spec to implement this entire plan , wisely

Kiro

Thought complete
I’m noticing a tension between my role as a planning agent that shouldn’t make edits and the implicit instruction to tell the user the spec is complete and ready for implementation. Let me think through what I’m actually supposed to do here. The planning agent constraint is about not modifying the system or codebase itself, but creating spec documents like requirements.md, design.md, and tasks.md is the core deliverable of planning work—that’s not implementation, that’s the planning artifact. The implicit rules are more specific to this workflow and directly instruct me to produce the spec and inform the user they can review tasks.md, so that takes precedence over the general planning agent constraint. I’m checking my available tools and realizing I don’t have file-writing capabilities in this turn—no fsWrite or str_replace. That means I’ll need to delegate the actual file creation to a sub-agent that can write, likely using invoke_sub_agent with one of the available agents like spec-task-execution. I’m weighing whether to delegate to `fast-task-workflow` with explicit instructions to write the spec verbatim, or just deliver the complete content inline since sub-agents have been unreliable this session. The safest approach is to give the user the full, ready-to-paste spec content upfront and be transparent that I can’t write files directly this turn. Actually, dispatching three separate sub-agents to write each file with exact content is cleaner — they handle the mechanical writing while I keep the intellectual work of authoring the spec itself. That way the user gets actual files on disk rather than just text to copy. I’ll dispatch each sub-agent with a detailed brief containing the findings, requirements with EARS criteria, and the task list with objectives, letting them author the full documents to match the repo’s standards rather than trying to dictate thousands of lines verbatim. Coherence is critical for a spec—requirements, design, and tasks need to reference each other precisely. I’ll fix the requirement and element numbering in my brief upfront so all three documents can be authored in parallel without mismatched IDs, then I’ll define the full structure: R1–R10 with titles, design elements E1–E5, properties P1–P20, and tasks 1–18 organized by phase. Starting with the feature name `decision-quality-proof` and laying out the requirements: R1 covers falsifiable gates, R2 addresses frontend verification execution, R3 handles inherited budgets, R4 manages blocking propagation and claim handling, R5 ensures the twin rewards intelligence across multiple dimensions, and R6 validates the uplift instrument. Continuing with R7 through R10: the uplift gate must check for proven uplift and reject incomplete work, the flagship model trains on real data with external benchmarking, a published checkpoint solidifies the confidence contract, and the audit chain remains externally verifiable. I’m also mapping out five design elements—the falsifiability harness, twin decision-relevance structures, controlled experiment with power analysis, M5 ingestion and benchmarking, and publication with external anchoring—then organizing tasks 1-18 across phases 0-4. Now I’m drafting detailed briefs for three authoring agents to execute this plan, then I’ll let the user know the spec is ready and they can review the tasks file.
I have no write tool in this turn, so I’ll own the content decisions — which are the hard part and already made — and delegate transcription to authoring-only agents. To keep the three documents coherent, I’m fixing the requirement/task numbering myself so nothing has to be reconciled afterward.

Feature name: decision-quality-proof — the spec’s purpose is proving decision quality, not auditing again.

1 tool call
Sub-agent: fast-task-workflow

Included Steering
Included Steering

claude-rules-authority.md

local-compute-budget.md

39 tool calls
Read Files

requirements.md
Read Files

CLAUDE.md

claude-rules-authority.md
Read Files

engine.py
Command
c:
git grep -n “rng.exponential|f"sku_{i}": 100.0|rng.uniform(30.0, 120.0)|rng.uniform(10.0, 45.0)|decay_rate = 0.01|spoilage_threshold = 0.3|OSRM travel time estimate|OSRM-estimated” – digital_twin/simulation/engine.py
fatal: unable to resolve revision: sku_
:.0.exe

Grep Search
Getting exact line numbers for the twin-structure citations the requirements document must carry.
Grep Search
Getting exact line numbers for the twin-structure citations with a simpler pattern.
Grep Search
Getting the remaining line numbers for spoilage decay and the literal initial inventory.
Read Files

gate-mutations.yaml

result.json

published_checkpoints.json
Command
c:
Get-ChildItem -Path artifacts -Recurse -Force | Select-Object FullName, Length | Format-Table -AutoSize
FullName Length
——– ——
C:
Grep Search
Verifying the R7 claims about read_measured_uplift, UPLIFT_FLOOR, is_proven_uplift and ratchet_to_measured line numbers and reachability.
Command
c:
Select-String -Path “scripts/audit/uplift_truth.py” -Pattern “def read_measured_uplift|is_proven_uplift|UPLIFT_FLOOR|require_fresh_run|EXIT_|incomplete|def main|def evaluate” -Encoding utf8 | ForEach-Object { “$($*.LineNumber): $($*.Line.Trim())” }
13: to :data:`~uplift.uplift_floor.UPLIFT_FLOOR`. With a committed floor of `0.0` and a
14: committed artifact carrying `{"headline_uplift": 0.0, "incomplete": true, 24: :func:`uplift.uplift_floor.is_proven_uplift` -- the predicate that was written to prevent 26: admitted only through :func:`uplift.uplift_floor.ratchet_to_measured` against a proof 31: * :data:`EXIT_PASS` (`0`)        --`is_proven_uplift`holds against the floor. 32: * :data:`EXIT_REGRESSION` (`1`)  -- a powered, complete, in-bound measurement that 34: * :data:`EXIT_UNAVAILABLE` (`2`) -- everything else. Inadmissible evidence, an 78: from uplift.uplift_floor import (  # noqa: E402 80: UPLIFT_FLOOR, 83: is_proven_uplift, 100: EXIT_PASS = 0 101: EXIT_REGRESSION = 1 102: EXIT_UNAVAILABLE = 2 279: by :func:`run`, so an`EXIT_UNAVAILABLE`always names why the measurement was 337: f"(R2.1 boolean `incomplete`, R2.2 integral replicates-per-arm, R2.3 finite " 400: verbatim (R2.1`incomplete`, R2.2`< MIN_POWERED_REPLICATES`, fidelity). 406: :class:`~uplift.uplift_floor.PoweredProof` :func:`verdict` derives from. 473: def verdict(proof: PoweredProof | None, *, floor: float = UPLIFT_FLOOR) -> int: 474: """Derive the exit code from :func:`uplift.uplift_floor.is_proven_uplift` (R2.4). 476:`EXIT_PASS`iff`is_proven_uplift(proof, floor)`. Otherwise`EXIT_REGRESSION`479: and`EXIT_UNAVAILABLE`for everything else. 487: exits`EXIT_UNAVAILABLE`, not`EXIT_PASS`.`is_proven_uplift`requires a 491: Replacing`is_proven_uplift`with a stub returning the opposite verdict changes the 494: if is_proven_uplift(proof, floor): 495: return EXIT_PASS 497: return EXIT_UNAVAILABLE 498: if not proof.is_powered or proof.incomplete or proof.within_fidelity_bound is not True: 499: return EXIT_UNAVAILABLE 501: return EXIT_UNAVAILABLE 503: return EXIT_REGRESSION 504: return EXIT_UNAVAILABLE 508: proof: PoweredProof | None, code: int, *, floor: float = UPLIFT_FLOOR 511: if code == EXIT_PASS and proof is not None: 517: if code == EXIT_REGRESSION and proof is not None: 529: if proof.incomplete: 530: return "the run is incomplete, so its headline number is not a measurement" 539: f"is_proven_uplift requires a strictly positive headline at or above floor " 551: previous: float = UPLIFT_FLOOR, 555: Delegates to :func:`uplift.uplift_floor.ratchet_to_measured`, which rejects a lower 577: Only an admitted artifact whose verdict is :data:`EXIT_PASS` yields`PASS`, so the 597: if code == EXIT_PASS: 599: if code == EXIT_REGRESSION: 612: "exit_code": code, 615: "is_proven_uplift": is_proven_uplift(proof, floor), 621: "uplift_floor": floor, 632: require_fresh_run: bool = False, 638: Without`–check``this is a reporting run and always returns :data:`EXIT_PASS`, 642: context = resolve_run_context(generating_job=require_fresh_run, artifact=target) 644: # A skip and an inadmissible artifact are both EXIT_UNAVAILABLE for the *step*: a 647: code = verdict(admission.proof) if admission.admitted else EXIT_UNAVAILABLE 657: payload = _payload(admission, code, UPLIFT_FLOOR) 668: print(f"     floor {UPLIFT_FLOOR}; exit code {code}") 676: return EXIT_UNAVAILABLE 678: return EXIT_PASS 703: help="check whether UPLIFT_FLOOR may be raised to PP against this run's proof", 714: require_fresh_run=args.require_fresh_run, 721: "EXIT_PASS", 722: "EXIT_REGRESSION", 723: "EXIT_UNAVAILABLE", 728: "UPLIFT_FLOOR", Command c:\Users\Pranesh\Projects\synapse Select-String -Path ".github/workflows/uplift.yml" -Pattern "name:|uses:|run:|on:|schedule|require-fresh-run|uplift.cli" -Encoding utf8 | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" } 15: #   *`–require-fresh-run`is the caller declaring "I ran the harness in this run". 47: name: SYNAPSE Uplift Proof 49: on: 50: schedule: 54: - cron: "0 3 * * *" 73: name: Powered uplift harness + C60 verdict (one job -- shared run) 74: runs-on: ubuntu-latest 81: - uses: actions/checkout@v4 83: - name: Set up Python 3.11 84: uses: actions/setup-python@v5 86: python-version: "3.11" 89: - name: Install dependencies 90: # Same dependency closure as ci.yml::uplift-verify, and for the same reason: 97: run: | 107: - name: Run the powered uplift harness (writes the C60 evidence) 116: run: python -m uplift.cli --full --output artifacts/uplift/result.json 118: - name: C60 uplift gate -- verdict from THIS run's evidence 123: run: python -m scripts.audit.uplift_truth --check --require-fresh-run 125: - name: Upload the uplift evidence 133: uses: actions/upload-artifact@v4 135: name: uplift-result Command c:\Users\Pranesh\Projects\synapse Select-String -Path "uplift/uplift_floor.py" -Pattern "^UPLIFT_FLOOR|^MIN_POWERED_REPLICATES|^def is_proven_uplift|^def ratchet_to_measured|^def " -Encoding utf8 | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" } 47: UPLIFT_FLOOR: float = 0.0 54: MIN_POWERED_REPLICATES: int = 1000 69: def ratchet(previous: float, proposed: float) -> float: 204: def is_proven_uplift(proof: PoweredProof | None, floor: float = UPLIFT_FLOOR) -> bool: 247: def ratchet_to_measured( Command c:\Users\Pranesh\Projects\synapse Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts" -File | ForEach-Object { $c = (Get-Content $_.FullName | Measure-Object -Line).Lines; $n = (Select-String -Path $_.FullName -Pattern "numRuns" -Encoding utf8).Count; "$($_.FullName.Replace('C:\Users\Pranesh\Projects\synapse\','')) lines=$c numRuns=$n" } Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@bufbuild\protob uf'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...fbuild\pro     tobuf:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@cyclonedx\cdxge n-plugins-bin'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...gen-plugin     s-bin:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@cyclonedx\cdxge n-plugins-bin-windows-amd64'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...n-windows-     amd64:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@gar\promisify'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...\@gar\prom     isify:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@isaacs\fs-minip ass'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...acs\fs-min     ipass:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@isaacs\string-l ocale-compare'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...-locale-co     mpare:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@keyv\serialize' . At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...@keyv\seri     alize:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\agent'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...s\@npmcli\     agent:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\arborist '. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...npmcli\arb     orist:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\fs'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...ules\@npmc     li\fs:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\git'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...les\@npmcl     i\git:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\installe d-package-contents'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...ackage-con     tents:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\map-work spaces'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...\map-works     paces:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\metavuln -calculator'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...vuln-calcu     lator:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\move-fil e'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...pmcli\move     -file:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\name-fro m-folder'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...ame-from-f     older:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\node-gyp '. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...npmcli\nod     e-gyp:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands     .GetChildItemCommand Get-ChildItem : Could not find a part of the path 'C:\Users\Pranesh\Pro jects\synapse\frontend\node_modules\.pnpm\node_modules\@npmcli\package- json'. At line:1 char:1 + Get-ChildItem -Path frontend -Recurse -Include "*.property.test.ts"  - ... + ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     + CategoryInfo          : ReadError: (C:\Users\Pranes...li\package     -json:String) [Get-ChildItem], DirectoryNotFoundException     + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.C … (output truncated) Grep Search Locating the five fast-check property test files and their hardcoded numRuns values for R2 and R3. File Search Finding the fast-check property test files referenced in R2 and R3. Command c:\Users\Pranesh\Projects\synapse git grep -c "numRuns" -- "frontend/src/**/*.property.test.ts" "frontend/spec/**/*.property.test.ts" "frontend/tests/**/*.property.test.ts" frontend/spec/contract-fidelity/__tests__/schema-less.property.test.ts:3 frontend/spec/effectiveness/__tests__/fixture-factory.property.test.ts:4 frontend/spec/effectiveness/__tests__/harness-determinism.property.test.ts:7 frontend/spec/effectiveness/__tests__/schema-less.property.test.ts:5 frontend/spec/effectiveness/__tests__/unhandled-path.property.test.ts:4 frontend/src/app/__tests__/primary-surfaces.property.test.ts:1 frontend/src/design-system/compounds/__tests__/provenance-degraded.property.test.ts:2 frontend/src/design-system/compounds/__tests__/provenance-status.property.test.ts:4 frontend/src/domain/__tests__/agent-state.property.test.ts:5 frontend/src/domain/__tests__/escalation-violations.property.test.ts:4 frontend/src/lib/__tests__/agent-state.property.test.ts:4 frontend/src/lib/__tests__/apply-once.property.test.ts:4 frontend/src/lib/__tests__/audit-export.property.test.ts:3 frontend/src/lib/__tests__/contract-coverage.property.test.ts:8 frontend/src/lib/__tests__/effectiveness-ratchet.property.test.ts:8 frontend/src/lib/__tests__/expected-review-value.property.test.ts:10 frontend/src/lib/__tests__/fault-transition.property.test.ts:4 frontend/src/lib/__tests__/interruption-precision.property.test.ts:5 frontend/src/lib/__tests__/jitter-retry.property.test.ts:6 frontend/src/lib/__tests__/json-canonical.property.test.ts:5 frontend/src/lib/__tests__/log.property.test.ts:3 frontend/src/lib/__tests__/operator-identity.property.test.ts:3 frontend/src/lib/__tests__/oversight.property.test.ts:16 frontend/src/lib/__tests__/posture-banner.property.test.ts:3 frontend/src/lib/__tests__/query-keys.property.test.ts:3 frontend/src/lib/__tests__/reconcile.property.test.ts:6 frontend/src/lib/__tests__/reconnect-backoff.property.test.ts:4 frontend/src/lib/__tests__/replay-council.property.test.ts:3 frontend/src/lib/__tests__/replay-phase.property.test.ts:4 frontend/src/lib/__tests__/replay-tool-visibility.property.test.ts:3 frontend/src/lib/__tests__/replay-transparency.property.test.ts:2 frontend/src/lib/__tests__/ring-buffer.property.test.ts:4 frontend/src/lib/__tests__/trust-track-record.property.test.ts:9 frontend/src/lib/__tests__/universal-state.property.test.ts:3 frontend/src/lib/__tests__/virtual-window.property.test.ts:5 frontend/src/state/__tests__/escalation-at-most-once.property.test.ts:4 frontend/src/surfaces/operations/__tests__/burn-honesty.property.test.ts:4 frontend/src/surfaces/operations/__tests__/calibration-power.property.test.ts:6 frontend/src/surfaces/operations/__tests__/chain-integrity.property.test.ts:3 frontend/src/surfaces/operations/__tests__/decision-confidence.property.test.ts:3 frontend/src/surfaces/operations/__tests__/outcome-mix.property.test.ts:3 frontend/src/surfaces/operations/__tests__/synthetic-exclusion.property.test.ts:3 frontend/src/transport/__tests__/schema-boundary.property.test.ts:2 :\Windows\System32\WindowsPowerShell\v1.0\powershell.exe\ Command c:\Users\Pranesh\Projects\synapse git grep -n "Property 3[1-6]\|degradation-rendering\|Properties 31" -- ".kiro/specs/purpose-achievement-audit/tasks.md" | Select-Object -First 60 dit/tasks.md" | Select-Object -First 60                                  Grep Search Finding which five frontend property test files implement predecessor-spec Properties 31-36 for R2 and R3. Command c:\Users\Pranesh\Projects\synapse git ls-files ".kiro/specs/purpose-achievement-audit/"; git log --oneline -1 :\Windows\System32\WindowsPowerShell\v1.0\powershell.exe\045f44c (HEAD -> main, origin/main, origin/HEAD) feat(uplift): wire real consensus arm into the uplift harness :\Windows\System32\WindowsPowerShell\v1.0\powershell.exe\ List Directory Checking what spec artifacts exist for the predecessor spec so I can locate Properties 31-36 and the five frontend property files. Command c:\Users\Pranesh\Projects\synapse Get-ChildItem ".kiro/specs/purpose-achievement-audit" | Select-Object Name, Length; Write-Output "--- properties 31-36 ---"; Select-String -Path ".kiro/specs/purpose-achievement-audit/design.md" -Pattern "^### Property 3[0-9]" -Encoding utf8 | ForEach-Object { "$($_.LineNumber): $($_.Line)" } Name            Length ----            ------ .config.kiro       113 design.md        82564 requirements.md 131370 tasks.md        106880 --- properties 31-36 --- 1226: ### Property 30: Actuation classification is behavioural and total (slow) 1239: ### Property 31: Degradation is rendered wherever degraded data is shown 1250: ### Property 32: The scorecard is complete or the job fails 1261: ### Property 33: The ratchet is sensitive to any degradation 1269: ### Property 34: Interruption precision responds to its inputs 1276: ### Property 35: An enforced invariant has an executed assertion 1285: ### Property 36: A baseline is a measurement, not a ceiling 1294: ### Property 37: Oracle-layer membership is earned, not declared Command c:\Users\Pranesh\Projects\synapse Select-String -Path ".kiro/specs/purpose-achievement-audit/tasks.md" -Pattern "Property 3[1-6]:|\.property\.test\.ts" -Encoding utf8 | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" } | Select-Object -First 60 263: - **Property 35: An enforced invariant has an executed assertion** 576: - **Property 32: The scorecard is complete or the job fails** 580: - Landed as`frontend/spec/effectiveness/**tests**/scorecard-completeness.property.test.ts`, 595: - **Property 33: The ratchet is sensitive to any degradation** 597: - Landed as`frontend/spec/effectiveness/**tests**/ratchet-sensitivity.property.test.ts`, 624: - **Property 34: Interruption precision responds to its inputs** 627:`frontend/spec/effectiveness/**tests**/interruption-precision-responsiveness.property.test.ts`, 644:`frontend/src/lib/**tests**/interruption-precision.property.test.ts`- bounds, empty-window 655: - **Property 36: A baseline is a measurement, not a ceiling** 657: - Landed as`frontend/spec/effectiveness/**tests**/baseline-measurement.property.test.ts`, 689: - **Property 31: Degradation is rendered wherever degraded data is shown** 691: - Landed at **`frontend/src/surfaces/**tests**/degradation-rendering.property.test.ts`**, not 696:`src/app/**tests**/primary-surfaces.property.test.ts`1090:`frontend/spec/effectiveness/**tests**/scorecard-completeness.property.test.ts`(32), 1091:`…/ratchet-sensitivity.property.test.ts`(33), 1092:`…/interruption-precision-responsiveness.property.test.ts`(34), 1093:`…/baseline-measurement.property.test.ts`(36), and - **outside 1094:`spec/effectiveness/`** -`frontend/src/surfaces/**tests**/degradation-rendering.property.test.ts`
Command
c:
$files = @(
  "frontend/spec/effectiveness/__tests__/scorecard-completeness.property.test.ts",
  "frontend/spec/effectiveness/__tests__/ratchet-sensitivity.property.test.ts",
  "frontend/spec/effectiveness/__tests__/interruption-precision-responsiveness.property.test.ts",
  "frontend/spec/effectiveness/__tests__/baseline-measurement.property.test.ts",
  "frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts"
)
foreach ($f in $files) {
if (Test-Path $f) {
$lines = (Get-Content $f -Encoding utf8 | Measure-Object -Line).Lines
$nr = (Select-String -Path $f -Pattern “numRuns:” -Encoding utf8).Count
$tracked = (git ls-files $f)
    "$f lines=$lines  numRuns100=$nr tracked=$(if($tracked){‘yes’}else{‘NO’})”
} else { “$f  MISSING" }
}
frontend/spec/effectiveness/__tests__/scorecard-completeness.property.test.ts  lines=780  numRuns100=12  tracked=NO
frontend/spec/effectiveness/__tests__/ratchet-sensitivity.property.test.ts  lines=575  numRuns100=6  tracked=NO
frontend/spec/effectiveness/__tests__/interruption-precision-responsiveness.property.test.ts  lines=752  numRuns100=9  tracked=NO
frontend/spec/effectiveness/__tests__/baseline-measurement.property.test.ts  lines=661  numRuns100=13  tracked=NO
frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts  lines=469  numRuns100=10  tracked=NO
Command
c:\Users\Pranesh\Projects\synapse
Write-Output "=== tsconfig.json ==="; Get-Content "frontend/tsconfig.json" -Encoding utf8
Write-Output "=== package.json scripts ==="; Select-String -Path "frontend/package.json" -Pattern "\"(typecheck|typecheck:spec|build|test|spec:check|audit:licenses)\"" -Encoding utf8 | ForEach-Object { "$($*.LineNumber): $($*.Line.Trim())” }
=== tsconfig.json ===
{
“compilerOptions”: {
“target”: “ES2022”,
“lib”: [“ES2022”, “DOM”, “DOM.Iterable”],
“module”: “ESNext”,
“moduleResolution”: “Bundler”,
“jsx”: “react-jsx”,
“useDefineForClassFields”: true,
“allowImportingTsExtensions”: false,
“resolveJsonModule”: true,
“isolatedModules”: true,
“verbatimModuleSyntax”: true,
“noEmit”: true,
“skipLibCheck”: true,
“strict”: true,
“noImplicitAny”: true,
“strictNullChecks”: true,
“strictFunctionTypes”: true,
“strictBindCallApply”: true,
“strictPropertyInitialization”: true,
“noImplicitThis”: true,
“alwaysStrict”: true,
“noUnusedLocals”: true,
“noUnusedParameters”: true,
“noFallthroughCasesInSwitch”: true,
“noImplicitReturns”: true,
“noUncheckedIndexedAccess”: true,
“exactOptionalPropertyTypes”: true,
“noImplicitOverride”: true,
“noPropertyAccessFromIndexSignature”: false,
“esModuleInterop”: true,
“forceConsistentCasingInFileNames”: true,
“allowSyntheticDefaultImports”: true,
“baseUrl”: “./”,
“paths”: {
“@/*”: [”src/*”],
”@app/*”: [“src/app/*”],
“@surfaces/*”: [”src/surfaces/*”],
”@domain/*”: [“src/domain/*”],
“@transport/*”: [”src/transport/*”],
”@ds/*”: [“src/design-system/*”],
“@viz/*”: [”src/visualization/*”],
”@state/*”: [“src/state/*”],
“@hooks/*”: [”src/hooks/*”],
”@lib/*”: [“src/lib/*”],
“@i18n/*”: [”src/i18n/*”],
”@test/*”: [“src/test/*”]
},
“types”: [“vite/client”, “vitest/globals”, “node”]
},
“include”: [
“src”,
“src/test/**/*“,”vite.config.ts”,
“vitest.config.ts”,
“playwright.config.ts”,
“playwright.harness.config.ts”,
“spec/effectiveness/harness.ts”,
“spec/effectiveness/e2e-entry.ts”
],
“exclude”: [
“node_modules”,
“dist”,
“dist-e2e”,
“coverage”,
“playwright-report”,
“test-results”
]
}
=== package.json scripts ===
typecheck : The term ‘typecheck’ is not recognized as the name of a
cmdlet, function, script file, or operable program. Check the spelling
of the name, or if a path was included, verify that the path is
correct and try again.
At line:1 char:103
+ … t-String -Path “frontend/package.json” -Pattern
“"(typecheck|typeche …
+ ~~~~~~~~~
+ CategoryInfo : ObjectNotFound: (typecheck:String) [], C
ommandNotFoundException
+ FullyQualifiedErrorId : CommandNotFoundException
Read Files

package.json
Command
c:
Write-Output “=== tsconfig.spec.json exists? ===”; Test-Path “frontend/tsconfig.spec.json”
if (Test-Path “frontend/tsconfig.spec.json”) { Get-Content “frontend/tsconfig.spec.json” -Encoding utf8 }
Write-Output “=== frontend.yml jobs / needs / typecheck / vitest ===”
Select-String -Path “.github/workflows/frontend.yml” -Pattern “^ [a-z0-9-]+:|needs:|if:|pnpm typecheck|vitest|pnpm test|pnpm build|name:” -Encoding utf8 | ForEach-Object { “$($*.LineNumber): $($*.Line.TrimEnd())” }
=== tsconfig.spec.json exists? ===
True
{
// SYNAPSE Console – type-check project for the SPEC and E2E trees.
//
// purpose-achievement-audit task 12.2. `tsconfig.json`’s `include` is
//
// [“src”, “src/test/**/*“,”vite.config.ts”, “vitest.config.ts”,
// “playwright.config.ts”, “playwright.harness.config.ts”,
// “spec/effectiveness/harness.ts”, “spec/effectiveness/e2e-entry.ts”]
//
// so `pnpm typecheck` (`tsc --noEmit`) and the `tsc --noEmit` inside `pnpm build`
// / `pnpm build:e2e` never checked:
//
// * spec/effectiveness/arbitraries.ts, run-ratchet.ts, check-baseline.ts,
// real-stack-fidelity.ts, scorecard-emission.ts, scorecard-gate.ts,
// browser-worker.ts, handlers.ts, fixture-factory.ts, schema-registry.ts,
// stream-driver.ts, stream-transport.ts, scenarios/
*//*  the EIGHT property tests in spec/effectiveness/**tests**/
// * spec/contract-fidelity/** including its own property test
// * every e2e spec under tests/**
//
// `pnpm lint` is `biome check ./src`, so none of them were linted either. They
// execute under vitest and Playwright, esbuild-transpiled with no type check, so a
// type error surfaces only if a run happens to reach that line. A directory CI runs
// but never checks is exactly the class of finding this audit exists to make
// mechanical.
//
// WHY A SEPARATE PROJECT INSTEAD OF WIDENING `tsconfig.json`‘s `include`
// ———————————————————————
// Blast radius. `pnpm build` is `tsc --noEmit && vite build`, so widening the base
// `include` puts these files inside the BUILD’s type check. In `frontend.yml`,
// `build` needs `quality`, and `e2e`, `e2e-visual`, `e2e-harness` and
// `mobile-lighthouse` all need `build`; `effectiveness-ratchet` needs
// `e2e-harness`, and `fe-invariants` needs [quality, e2e, e2e-visual,
// e2e-harness]. One pre-existing error in one e2e spec would therefore skip the
// entire console-effectiveness spine – the harness run record, the scorecard, the
// ratchet, the FE-INV attestation – and every one of those would render as NOT
// EXECUTED. This project isolates the new signal: it fails on its own, and nothing
// downstream depends on it.
//
// This is NOT a narrowed glob chosen to dodge files suspected of being dirty. It
// covers strictly MORE than widening the base `include` would have: `spec/**` and
// `tests/**` in full.
//
// EXPECTED RED ON THE FIRST CI RUN, and that is honest (I-7)
// ———————————————————
// These files have never been compiled. This project inherits `strict`,
// `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noUnusedLocals`,
// `noUnusedParameters`, `noImplicitReturns` and `verbatimModuleSyntax` from the
// base config and applies them to code that has only ever been transpiled. Errors
// in the four older property tests (`fixture-factory`, `harness-determinism`,
// `schema-less`, `unhandled-path`) and in the e2e specs are EXPECTED and are
// pre-existing debt becoming visible – not a regression introduced by this file.
// The first `pnpm typecheck:spec` run in CI is the first real signal: it was
// authored, not executed (I-0 forbids the local run, and `getDiagnostics` returns
// no TypeScript signal in this workspace, so a clean local result would have
// proven nothing).
“extends”: “./tsconfig.json”,
“include”: [“spec/**/*.ts”, “tests/**/*.ts”],
“exclude”: [
“node_modules”,
“dist”,
“dist-e2e”,
“coverage”,
“playwright-report”,
“test-results”
]
}
=== frontend.yml jobs / needs / typecheck / vitest ===
1: name: SYNAPSE Frontend CI
4: push:
18: run:
22: quality:
23: name: Lint • Typecheck • Unit
29: - name: Setup pnpm
34: - name: Setup Node
41: - name: Install dependencies
44: - name: Biome lint
47: - name: TypeScript strict
48: run: pnpm typecheck
50: - name: Vitest unit + property tests
51: run: pnpm test:coverage
53: - name: Upload coverage
54: if: success() || failure()
57: name: frontend-coverage
60: - name: Upload Vitest run record (FE-INV attestation evidence, R8.7)
65: if: success() || failure()
68: name: fe-invariant-vitest-report
69: path: frontend/artifacts/test-reports/vitest.json
72: spec-typecheck:
73: name: TypeScript strict — spec/ + tests/ (the trees tsconfig.json never checked)
78: # (`harness.ts`, `e2e-entry.ts`). So `pnpm typecheck` and the `tsc --noEmit`
79: # inside `pnpm build` have never checked `arbitraries.ts`, `run-ratchet.ts`,
84: # either. They execute under vitest/Playwright, esbuild-transpiled without a type
88: # DELIBERATELY A STANDALONE JOB with no `needs:` and nothing depending on it.
89: # Widening the base `include` would have put these files inside `pnpm build`, and
111: - name: Install dependencies
113: - name: TypeScript strict (spec/ + tests/)
114: run: pnpm typecheck:spec
116: build:
117: name: Vite build + size budget
120: needs: quality
131: - name: Install dependencies
133: - name: Build
134: run: pnpm build
135: - name: Size budget
138: contract-fidelity:
139: name: Contract fidelity drift (Req 1)
142: needs: quality
153: - name: Install dependencies
155: - name: Contract fidelity drift report
161: if: success() || failure()
163: name: contract-drift-report
169: fe-invariants:
170: name: FE-INV registry coverage
173: # The gate reads EXECUTED, non-skipped assertions from the Vitest/Playwright
177: # by `quality` (Vitest) and `e2e` / `e2e-visual` / `e2e-harness` (Playwright),
182: needs: [quality, e2e, e2e-visual, e2e-harness]
185: - name: Setup Python
189: - name: Install gate dependencies
191: - name: Download Vitest run record
194: name: fe-invariant-vitest-report
196: - name: Download Playwright run records
202: - name: Validate FE-INV registry against executed assertions
212: –report frontend/artifacts/test-reports/vitest.json

217: e2e:
218: name: Playwright E2E + axe
221: needs: build
227: if: github.event_name == ’pull_request’ || startsWith(github.ref, ‘refs/tags/v’)
240: - run: pnpm build
241: - name: Playwright E2E (blocking)
257: # NOTE: `fe-invariants` declares `needs: [quality, e2e, e2e-visual, 261:         run: pnpm test:e2e --project=chromium 263:         if: always() 265:           name: playwright-report 268:       - name: Upload Playwright run record (FE-INV attestation evidence, R8.7) 271:         if: always() 274:           name: fe-invariant-playwright-e2e-report 278:   e2e-visual: 279:     name: Visual regression gate (Req 14) 282:     needs: build 298:     if: github.event_name == 'pull_request' || startsWith(github.ref, 'refs/tags/v') 316:       - run: pnpm build 317:       - name: Generate + commit Linux baselines if none are committed yet 330:             pnpm test:visual:update || true 341:       - name: Visual regression compare against committed baselines (real gate) 348:           PLAYWRIGHT_JSON_OUTPUT_NAME: artifacts/test-reports/playwright-visual.json 349:         run: pnpm test:visual 351:         if: always() 353:           name: visual-regression-report 356:       - name: Upload Playwright visual run record (FE-INV attestation evidence, R8.7) 357:         if: always() 360:           name: fe-invariant-playwright-visual-report 364:   e2e-harness: 365:     name: Effectiveness harness (Req 1.3, 3, 7) — deterministic 368:     needs: build 380:     if: github.event_name == 'pull_request' || startsWith(github.ref, 'refs/tags/v') 393:       - name: Build the e2e-mode bundle (the one that contains the harness) 394:         #`pnpm build:e2e`->`dist-e2e/`, served by`pnpm preview:e2e`on :3001 395:         # (task 11.1). The PRODUCTION bundle`pnpm build`produces cannot contain 399:         run: pnpm build:e2e 400:       - name: Task_Completion_Tests + Resilience_Scenarios (seeded, no live network) 405:         # This replaces`pnpm test:e2e –project=chromium task-completion.jtbd
423: PLAYWRIGHT_JSON_OUTPUT_NAME: artifacts/test-reports/playwright-harness.json
424: run: pnpm test:e2e:harness
425: - name: Upload Playwright harness run record (FE-INV attestation evidence, R8.7)
430: if: always()
433: name: fe-invariant-playwright-harness-report
436: - name: Upload effectiveness scorecard
438: if: success() || failure()
446: name: effectiveness-scorecard
452: if: always()
454: name: harness-playwright-report
458: effectiveness-ratchet:
459: name: Effectiveness ratchet (Req 4.3/4.4) — deterministic
462: needs: e2e-harness
483: if: github.event_name == ‘pull_request’ || startsWith(github.ref, ‘refs/tags/v’)
495: - name: Download fresh scorecard
503: name: effectiveness-scorecard
505: - name: Download harness run record (skip + zero-execution evidence, R8.6/R8.8)
509: # the old `pnpm test:e2e ... || true` step produced — is a failure here, so
513: name: fe-invariant-playwright-harness-report
515: - name: Effectiveness ratchet (fresh scorecard vs committed baseline)
521: - name: Effectiveness baseline is a measurement, not a ceiling (R8.10)
522: # Blocking. `if: success() || failure()` is NOT a discarding construct: the
529: if: success() || failure()
531: - name: Upload measured baseline candidate (commit this to clear R8.10)
532: if: success() || failure()
535: name: effectiveness-baseline
… (output truncated)
Command
c:
Write-Output “=== –sweep in workflows? ===”; git grep -n “sweep|gate_fault_injection” – “.github/workflows/” Makefile
Write-Output “=== unlabelled_discarding_steps / advisory in blocking-steps.yaml ===”; git grep -n “unlabelled_discarding_steps|unlabelled|ADVISORY|informational” – “infrastructure/quality/blocking-steps.yaml” | Select-Object -First 30
=== –sweep in workflows? ===
.github/workflows/mutation.yml:28: # full sweep is `if: github.event_name != 'pull_request'` and the fast gate was
.github/workflows/mutation.yml:40: # Sunday whole-file sweep catches that.
.github/workflows/mutation.yml:59: # 90-minute whole-file sweep on every merge commit.
.github/workflows/mutation.yml:86: # so a dev-requirements change cannot turn the walker sweep into a
.github/workflows/mutation.yml:225: # Sprint 13 §Phase 4.2 (C30): runs ONLY the changed-target mutmut sweep on
.github/workflows/mutation.yml:231: # remains the whole-file sweep for full reward/audit/guardrail debt.
.github/workflows/mutation.yml:233: # so the timeout covers the full changed-target sweep.
.github/workflows/mutation.yml:270: # See the whole-file sweep above: chain_walk.py imports `yaml` at module
.github/workflows/mutation.yml:366: # ceiling as the whole-file sweep above; see that step for why the
:.0.exe=== unlabelled_discarding_steps / advisory in blocking-steps.yaml ===
Command
c:
Get-ChildItem “infrastructure/quality” | Select-Object Name, Length
Write-Output “=== blocking-steps.yaml keys ===”
if (Test-Path “infrastructure/quality/blocking-steps.yaml”) { Select-String -Path “infrastructure/quality/blocking-steps.yaml” -Pattern “[1](about:blank#fn1)+:|unlabelled|advisory|ADVISORY|informational” -Encoding utf8 | ForEach-Object { “$($*.LineNumber): $($*.Line.TrimEnd())” } | Select-Object -First 40 }
Name Length
—- ——
schemas

audit-chain-bounds.yaml 4160

blocking-steps.yaml 15966
checkpoint-scope.yaml 7365

checkpoint-truth.yaml 9949

coverage-floors.yaml 6484

dead-modules.yaml 8563

doc-number-pins.yaml 14206
effectiveness-baseline.json 2735

effectiveness-precision.json 2418

fe-invariant-attestation.yaml 4917

gate-mutations.yaml 22850
oracle-layers.yaml 1837

ratchets.json 20694
replay-floors.yaml 2154

required-checks.yaml 14982
twin-verdict-bounds.yaml 5218

=== blocking-steps.yaml keys ===
9: # is NOT listed here must carry `ADVISORY` or `informational` in its step name
10: # (R11.3). ci.yml’s two honest advisory labels already satisfy it.
24: version: 1
26: steps:
107: # carry `informational` would have excused.
125: # `e2e` step’s `informational` label would have excused.
160: # step to carry `informational`, which is the precedent recorded above for the old
165: # is an honest advisory (`continue-on-error: true`, recorded under
166: # `unlabelled_discarding_steps` below), and `all_steps` would declare it blocking
167: # and turn a reviewed advisory into a FAIL by declaration. The narrow claim is the
220: pending: []
223: # Non-propagating steps whose names carry NO advisory marker (R11.3 violations).
229: unlabelled_discarding_steps:
235: Either rename to carry ADVISORY, or propagate: the step currently swallows
243: The inline comment already says “informational in P0; gated in P2” – the
267: honest fix is one word in the step name (ADVISORY or informational) so the
274: Genuinely informational by design: it MEASURES per-package coverage so an
278: “conditional - advisory (unlabelled)”. Rename to carry ADVISORY. Note the
Command
c:
$c = Get-Content "infrastructure/quality/blocking-steps.yaml" -Encoding utf8$start = ($c | Select-String -Pattern "^unlabelled_discarding_steps:" ).LineNumber$c[($start-1)..($c.Count-1)] | Select-Object -First 130
unlabelled_discarding_steps:
- workflow: .github/workflows/ci.yml
job: quality-gates
step_name: “Contract tests”
construct: ‘2>/dev/null || echo “No contract tests yet (Sprint 2)”’
remediation: >-
Either rename to carry ADVISORY, or propagate: the step currently swallows
a real contract-test failure and a collection error identically.
- workflow: .github/workflows/frontend.yml
job: build
step_name: “Size budget”
construct: “|| true”
remediation: >-
The inline comment already says “informational in P0; gated in P2” – the
honest fix is to move that word into the step name so the shape check can
read it.
# ————————————————————————-
# Recorded by purpose-achievement-audit task 12.1, from findings tasks 12.2 and
# 12.4 surfaced in files they did not own. Both are pre-existing R11.3 cases:
# `workflow_shape_truth` applies the name rule to EVERY non-propagating step, so
# each was already failing that gate with no record explaining why. Recording
# them here is not a suppression – nothing reads this section as a pass. It
# converts an unattributable red into an attributable one with a named
# remediation, which is the trade this section exists for.
#
# Neither step was renamed. `steps:` above declares step names by string, and a
# rename makes those declarations resolve to no step – which this same gate
# fails on. The fix is an operator decision, not a drive-by edit.
- workflow: .github/workflows/frontend.yml
job: e2e-visual
step_name: “Generate + commit Linux baselines if none are committed yet”
construct: “|| true”
remediation: >-
The `|| true` is defensible on its own terms: this step SEEDS baselines on a
first run, and the compare step below it is the real gate – a seeding
failure with no baseline to compare against would fail there anyway. The
honest fix is one word in the step name (ADVISORY or informational) so the
shape check can read the intent it already has.
- workflow: .github/workflows/ci.yml
job: training-smoke
step_name: “Measure per-package coverage under full ML stack (binds the 0.0 floors)”
construct: ‘continue-on-error: true, and `|| true` on coverage_per_package.py’
remediation: >-
Genuinely informational by design: it MEASURES per-package coverage so an
operator can bind the 0.0 floors via scripts/coverage_ratchet.py, and the
BLOCKING per-package floor check is the separate step in `quality-gates`
(declared in `steps:` above). GATE_SURFACE.md already renders it
“conditional - advisory (unlabelled)”. Rename to carry ADVISORY. Note the
new “R3.2 serving-resolution proof” step sits immediately BEFORE this one
precisely so its exit status is never discarded by this block (task 12.4).
Command
c:
Write-Output “=== README headline ===”; git grep -n “PASS.*FAIL.*PARTIAL.*SKIP.*TOTAL|generated:begin|generated:end” – README.md docs/state/CURRENT.md | Select-Object -First 20
Write-Output “=== doc_truth recursion guard + headline claim ===”; git grep -n “recursion|_claim_readme_headline_counts|SYNAPSE_DOC_TRUTH” – scripts/audit/doc_truth.py | Select-Object -First 20
=== README headline ===
README.md:24:Run `make verify-claims` for the live truth. Today it reports **51 PASS / 3 FAIL / 0 PARTIAL / 10 SKIP / 64 TOTAL**.
docs/state/CURRENT.md:15:
docs/state/CURRENT.md:119:`README.md` headline counts, from this same execution (R10.9): **52 PASS / 3 FAIL / 0 PARTIAL / 9 SKIP / 64 TOTAL**
docs/state/CURRENT.md:120:
docs/state/CURRENT.md:404:the `<!-- generated:begin -->` / `<!-- generated:end -->` markers is never touched by either
=== doc_truth recursion guard + headline claim ===
scripts/audit/doc_truth.py:23: timeout, an unparseable summary, a missing pin table, the recursion guard
scripts/audit/doc_truth.py:27: unrelated spec-threshold pin passing. The recursion guard itself was always
scripts/audit/doc_truth.py:648:# 900s timeout, an unparseable summary, a missing README, the recursion guard firing -
scripts/audit/doc_truth.py:657:#: skips *this* claim only (every other claim still runs), bounding the recursion at
scripts/audit/doc_truth.py:659:_NESTED_ENV: Final[str] = “SYNAPSE_DOC_TRUTH_NESTED”
scripts/audit/doc_truth.py:763:def _claim_readme_headline_counts() -> ClaimResult:
scripts/audit/doc_truth.py:767: recursion guard firing can no longer be masked by an unrelated passing pin.
scripts/audit/doc_truth.py:777: “nested inside a verify_claims run - recursion guard; the pin is checked by”
scripts/audit/doc_truth.py:819: _claim_readme_headline_counts,
Command
c:
Write-Output “=== FALLBACK_CONFIDENCE + conformal confidence ===”; git grep -n “FALLBACK_CONFIDENCE|mean_rel_width” – agents/demand_prophet/ packages/ | Select-Object -First 15
Write-Output “=== allow_local_substitution ===”; git grep -n “allow_local_substitution” | Select-Object -First 8
Write-Output “=== audit_anchors ===”; Get-ChildItem “infrastructure/audit_anchors” -ErrorAction SilentlyContinue | Select-Object Name | Select-Object -First 10
Write-Output “=== confidence_basis constant rule ===”; git grep -n “confidence_basis” – packages/synapse_common/provenance.py | Select-Object -First 12
Write-Output “=== INV-DP-002 coverage_p90 ===”; git grep -n “INV-DP-002” – agents/demand_prophet/spec.yaml | Select-Object -First 5
Write-Output “=== runbook exists ===”; Test-Path “docs/runbooks/train-and-publish-checkpoint.md”
=== FALLBACK_CONFIDENCE + conformal confidence ===
agents/demand_prophet/inference/pipeline.py:38:FALLBACK_CONFIDENCE = 0.5 # documented I-7 floor when no calibrated model is present
agents/demand_prophet/inference/pipeline.py:279: # degraded path it is the explicit FALLBACK_CONFIDENCE floor ΓÇö NOT an
agents/demand_prophet/inference/pipeline.py:332: confidence = FALLBACK_CONFIDENCE
agents/demand_prophet/inference/pipeline.py:334: mean_rel_width = float(np.mean(rel_widths)) if rel_widths else 1.0
agents/demand_prophet/inference/pipeline.py:335: confidence = round(float(1.0 / (1.0 + mean_rel_width)), 4)
agents/demand_prophet/tests/test_serving_calibration.py:7: * the degraded confidence is the honest FALLBACK_CONFIDENCE floor (fires I-5),
agents/demand_prophet/tests/test_serving_calibration.py:24: FALLBACK_CONFIDENCE,
agents/demand_prophet/tests/test_serving_calibration.py:197: assert all(f.confidence == FALLBACK_CONFIDENCE for f in forecasts)
=== allow_local_substitution ===
scripts/audit/published_checkpoint_truth.py:37: `source.allow_local_substitution` must be false. Either pin
scripts/audit/published_checkpoint_truth.py:204: allow_local_substitution: bool
scripts/audit/published_checkpoint_truth.py:1239: if active.source.allow_local_substitution:
scripts/audit/published_checkpoint_truth.py:1246: f”{_rel(POLICY_FILE)}::source.allow_local_substitution is true; ”
scripts/audit/published_checkpoint_truth.py:1349: f”{_rel(POLICY_FILE)}::source.allow_local_substitution is false, so an ”
=== audit_anchors ===
=== confidence_basis constant rule ===
packages/synapse_common/provenance.py:13: * `confidence_basis` ΓÇö how the accompanying `confidence` was derived
=== INV-DP-002 coverage_p90 ===
agents/demand_prophet/spec.yaml:25: - id: “INV-DP-002”
agents/demand_prophet/spec.yaml:182:- invariant_id: INV-DP-002
=== runbook exists ===
True
Command
c:
Write-Output “=== audit_anchors dir ===”; Test-Path “infrastructure/audit_anchors”; git grep -n “audit_anchors” – “.github/” “orchestrator/” “scripts/” | Select-Object -First 10
Write-Output “=== confidence_basis constant forbidden ===”; git grep -n “constant” – packages/synapse_common/provenance.py scripts/audit/confidence_basis_truth.py | Select-Object -First 12
Write-Output “=== C67 anchor gate ===”; git grep -n “unverifiable|anchor file” – scripts/audit/verify_claims.py | Select-Object -First 8
=== audit_anchors dir ===
False
.github/workflows/publish-audit-anchor.yml:5:# Sprint 9 commits a daily anchor under infrastructure/audit_anchors/.json
.github/workflows/publish-audit-anchor.yml:32:# push to main that touches infrastructure/audit_anchors/ (sign + publish).
.github/workflows/publish-audit-anchor.yml:38: - “infrastructure/audit_anchors/**”
.github/workflows/publish-audit-anchor.yml:106: git add infrastructure/audit_anchors/*.json
.github/workflows/publish-audit-anchor.yml:131: # infrastructure/audit_anchors/, not in the run that produced it. The anchor’s
.github/workflows/publish-audit-anchor.yml:147: changed=$(git diff --name-only HEAD~1 HEAD -- 'infrastructure/audit_anchors/*.json' || true)
.github/workflows/publish-audit-anchor.yml:191:          git add infrastructure/audit_anchors/*.sig infrastructure/audit_anchors/*.cert || true
orchestrator/audit/anchorer.py:130:ANCHOR_DIR: Final[Path] = REPO_ROOT / "infrastructure" / "audit_anchors"
=== confidence_basis constant forbidden ===
packages/synapse_common/provenance.py:15:    ``constant``. A constant confidence above the HITL threshold makes I-5
scripts/audit/confidence_basis_truth.py:3:``substance_truth.py`` (C33) catches a *constant* confidence. It cannot catch a
=== C67 anchor gate ===
scripts/audit/verify_claims.py:2244:    exactly two values, `anchored` and `unverifiable`, and NEITHER of them is
scripts/audit/verify_claims.py:2273:        f"chain={report.chain_status}, {len(report.anchors)} anchor file(s); {report.reason}",
Command
c:\Users\Pranesh\Projects\synapse
Write-Output "=== C37/C38/C40/C45/C46/C69 registry rows ==="; git grep -n '@register("C3[7-9]"\|@register("C4[0-9]"\|@register("C69"\|@register("C64"\|@register("C56"\|@register("C67"\|@register("C72"' -- scripts/audit/verify_claims.py
Write-Output "=== training_truth sentinel/optimizer AST flags ==="; git grep -n "sentinel\|un-stepped\|optimizer" -- scripts/audit/training_truth.py | Select-Object -First 10
Write-Output "=== register count ==="; (git grep -c "@register(" -- scripts/audit/verify_claims.py)
=== C37/C38/C40/C45/C46/C69 registry rows ===
:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe\=== training_truth sentinel/optimizer AST flags ===
scripts/audit/training_truth.py:12:  * ``hollow_loop`` - a training entrypoint that constructs an optimizer
scripts/audit/training_truth.py:15:    sentinel. This is the active lie and must reach zero.
scripts/audit/training_truth.py:53:# (pipeline_validated sentinel + hollow optimizer) to zero by giving it a real
scripts/audit/training_truth.py:83:def _constructs_optimizer(tree: ast.AST) -> bool:
scripts/audit/training_truth.py:150:    constructs_opt = _constructs_optimizer(tree)
scripts/audit/training_truth.py:157:                "returns the 'pipeline_validated' sentinel - the no-op-training lie (ADR-042)",
scripts/audit/training_truth.py:161:    # hollow_loop: builds an optimizer but never steps it (analytical agents are exempt).
scripts/audit/training_truth.py:166:                "constructs an optimizer but never calls .step()/.backward() - "
=== register count ===
scripts/audit/verify_claims.py:64
Fetch URL
https://en.wikipedia.org/wiki/Makridakis_Competitions
Fetch URL
https://en.wikipedia.org/wiki/Makridakis_Competitions
Fetch URL
https://en.wikipedia.org/wiki/Makridakis_Competitions
Command
c:\Users\Pranesh\Projects\synapse
Write-Output "=== simpy.Resource anywhere? ==="; git grep -n "simpy.Resource\|simpy.Container\|simpy.Store\|PriorityResource" -- "*.py" | Select-Object -First 10
Write-Output "=== unavailable -> SKIP mapping ==="; git grep -n "unavailable" -- scripts/audit/verify_claims.py | Select-Object -First 8
Write-Output "=== make_canonical_row ==="; git grep -n "def make_canonical_row" -- "*.py"
Write-Output "=== CURRENT.md generated region provenance ==="; Select-String -Path "docs/state/CURRENT.md" -Pattern "generated:begin|one registry execution|projected" -Encoding utf8 | ForEach-Object { "$($.LineNumber): $($.Line.Trim())” } | Select-Object -First 8
=== simpy.Resource anywhere? ===
=== unavailable -> SKIP mapping ===
scripts/audit/verify_claims.py:9:(exit `0` pass / `1` fail / `2` unavailable), so a CI step and this script
scripts/audit/verify_claims.py:48:# `pass`/`fail`/`unavailable` and, in `ratchet_truth` and
scripts/audit/verify_claims.py:50:# `unavailable`). The three-key mapping those rows used could not express the fourth
scripts/audit/verify_claims.py:55:# could not read its inputs (`unavailable`) and a gate whose subject is absent
scripts/audit/verify_claims.py:65: “unavailable”: “SKIP”,
scripts/audit/verify_claims.py:1262: `"C43"`, so an unavailable published-checkpoint probe landed on another
scripts/audit/verify_claims.py:1718: `unavailable` maps to SKIP, never PASS: since task 2.5 the aggregate reports
scripts/audit/verify_claims.py:1719: `unavailable` whenever a* required* claim could not be evaluated, and an `ok`
=== make_canonical_row ===
packages/synapse_common/audit_chain.py:62:def make_canonical_row(
:.0.exe=== CURRENT.md generated region provenance ===
15: 
22: Every row and every count below is projected from a single Check_Registry
206:** The counts live in the generated region above**, projected from one registry execution. They are deliberately not restated here: a second statement of the same numbers is a second thing to keep in sync, and the drift between them is audit finding R10. What follows is the narrative those counts sit in.
404: the `<!-- generated:begin -->` / `<!-- generated:end -->` markers is never touched by either
Command
c:
Write-Output “=== GuardrailEngine + inject_shock ===”; git grep -n “class GuardrailEngine|def inject_shock|inject_shock(” – “*.py” | Select-Object -First 8
Write-Output “=== WorldRuntime empty-inventory degrade ===”; git grep -n “initial_inventory” – digital_twin/world/runtime.py | Select-Object -First 8
Write-Output “=== C44 windows FileNotFoundError ===”; git grep -n “FileNotFoundError” – scripts/audit/module_liveness.py | Select-Object -First 6
Write-Output “=== conftest hypothesis profiles ===”; git grep -n “max_examples” – conftest.py | Select-Object -First 10
Write-Output “=== hardcoded max_examples violations ===”; git grep -ln “max_examples” – tests/uplift/ tests/verify/ | Select-Object -First 8
=== GuardrailEngine + inject_shock ===
digital_twin/simulation/engine.py:156: def inject_shock(
digital_twin/world/runtime.py:307: self._sim.inject_shock(**shock)
orchestrator/guardrails/rules.py:297:class GuardrailEngine:
=== WorldRuntime empty-inventory degrade ===
digital_twin/world/runtime.py:25: accept `start(external_demand=..., initial_inventory=...)`, because that is the call
digital_twin/world/runtime.py:155: opening = source.initial_inventory()
digital_twin/world/runtime.py:158: self._sim.start(external_demand=True, initial_inventory={})
digital_twin/world/runtime.py:160: “world_initial_inventory_absent”,
digital_twin/world/runtime.py:167: self._sim.start(external_demand=True, initial_inventory=dict(opening))
=== C44 windows FileNotFoundError ===
=== conftest hypothesis profiles ===
conftest.py:18:# Property-based tests inherit `max_examples` from the active profile instead
conftest.py:44: “dev”, max_examples=10, deadline=None, suppress_health_check=_SUPPRESS
conftest.py:47: “heavy”, max_examples=100, deadline=None, suppress_health_check=_SUPPRESS
conftest.py:50: “default”, max_examples=500, deadline=None, suppress_health_check=_SUPPRESS
conftest.py:53: “ci”, max_examples=500, deadline=None, suppress_health_check=_SUPPRESS
conftest.py:56: “nightly”, max_examples=5_000, deadline=None, suppress_health_check=_SUPPRESS
=== hardcoded max_examples violations ===
tests/uplift/test_adversarial_exit_success_property.py
tests/uplift/test_aggregation_integrity_property.py
tests/uplift/test_all_wins_guard_property.py
tests/uplift/test_all_wins_warning_property.py
tests/uplift/test_arm_aggregate_property.py
tests/uplift/test_arm_symmetry_no_leakage_property.py
tests/uplift/test_baseline_determinism_conformance.py
tests/uplift/test_baseline_pooling_property.py
Your connection was interrupted. Please try again in a moment.

Thought complete
The sub-agents keep failing, so I’m switching tactics. Since I don’t have write access this session, the best approach is to provide the complete spec content inline—ready to use—and be direct with the user about my limitations. Let me draft all three documents thoroughly and comprehensively. I’ll focus on requirements.md and tasks.md as the core deliverables, with design.md covering only the genuinely novel technical elements like the twin decision-relevance framework and control experiment design rather than restating what the repo already knows. I need to be disciplined about density and use proper EARS format for the requirements: “WHEN [event] THE [entity] SHALL [response]” structure.
Sub-agent dispatch has now failed three times this session. I’m not retrying it — and I have no write tool in this turn. So I’ll deliver the spec as complete, commit-ready content. This is the full intellectual artifact; saving it is mechanical.

Create .kiro/specs/decision-quality-proof/ with these three files.

File 1 — requirements.md
markdown

# Requirements Document

> **Decision Quality Proof** — the spec that makes SYNAPSE’s central claim measurable.
> 

## Introduction

The predecessor spec (`.kiro/specs/purpose-achievement-audit/`) diagnosed. This one
proves. Its thesis:

> SYNAPSE has built a credible apparatus for proving things about itself. This spec
makes that apparatus **provably able to fail**, makes the simulated world one where
**intelligence can pay**, proves the measuring instrument **can detect an effect**,
and only then measures decision quality — on **non-synthetic data**, against a
**published external benchmark**.
> 

### The load-bearing finding driving this spec is new

It is not inherited from the audit. It is analytical, and it is falsifiable:

> **The uplift experiment cannot produce a meaningful number even when run correctly,
because the twin has no exploitable structure.**
> 

Evidence, all from `digital_twin/simulation/engine.py`:

| Property | Code | Consequence |
| --- | --- | --- |
| Demand | `_order_arrival`: `rng.exponential(1.0 / (config.order_arrival_rate * demand_mult))` | **stationary Poisson** |
| Inventory | `start()`: `{f"sku_{i}": 100.0 for i in range(10)}` | **10 independent, identical SKUs** |
| Lead time | `_restock`: `rng.uniform(30.0, 120.0) * lead_time_mult` | **i.i.d., uncorrelated with demand** |
| Delivery | `_delivery`: `rng.uniform(10.0, 45.0) + rng.normal(0.0, 3.0)` | **no rider pool, no queue, no capacity** |
| Spoilage | `_spoilage`: `decay_rate = 0.01 * spoilage_rate_multiplier`, threshold `0.3`, reset `1.0` | **decoupled from order quantity** |

For stationary Poisson demand, independent items, i.i.d. lead times and no capacity
coupling, a base-stock `(s,S)` policy is provably near-optimal by standard inventory
theory. **The baseline arm is therefore the optimal policy for this world, and the
consensus arm cannot beat it except by chance.**

A zero uplift measured on today’s twin would be read as *“the agents are not better.”*
It would in fact mean *“the world is too easy to be better in.”* Publishing that number
is the most expensive mistake available to this project: a true measurement of a
meaningless quantity.

**Falsification of this finding:** the measured `(s,S)`-regret test in R5. If regret is
already materially positive on today’s twin, R5’s scope shrinks substantially. That test
is sequenced first in Phase 1 for exactly this reason.

### Corroborating external evidence

The Makridakis M-Competitions’ central, replicated finding is that *“statistically
sophisticated or complex methods do not necessarily provide more accurate forecasts than
simpler ones”*, while *combining* methods does outperform. The M5 competition used ~42,000
hierarchical Walmart series across two tracks — Accuracy and Uncertainty — with separate
winners (Accuracy: YeonJun In; Uncertainty: Russ Wolfinger and David Lander). *Source:
Wikipedia, “Makridakis Competitions”; verified during authoring. Numeric leaderboard
scores were NOT verified and must be confirmed at implementation time.*

Consequence for this project: **SYNAPSE should not expect consensus to dominate on point
accuracy.** Its plausible edge is decision quality under shocks, binding constraints and
multi-objective tradeoffs — exactly what `inject_shock` and `GuardrailEngine` exist for,
and exactly what the current twin does not exercise. The uplift hypothesis must be framed
that way or it is tested against the wrong prediction.

### Scope, method, limits

- **Method.** Static reading, plus one external source (above). No code was executed
while authoring (I-0).
- **This spec introduces no measured numbers.** Every threshold it references is to be
*produced* by a task and recorded by a gate, never stated in advance. Where a
requirement depends on a measurement that does not yet exist, it says so.
- **What this spec cannot establish.** Whether any test currently passes; the live
frontend type-check result; whether GitHub branch protection marks any job required.

### Verdict vocabulary

*demonstrably achieved · bounded scope · substantially achieved · implemented but not
integrated · integrated but not validated · validated only under limited conditions ·
plausible but unverified · contradicted by evidence · not achieved · not verifiable
locally.*

---

## Requirements

### Requirement 1: The gates are not proven able to fail

**User Story:** As the operator who trusts a green registry, I want each gate proven to
fail when its subject breaks, so that “52 PASS” describes enforcement and not merely
execution.

**The verified reality.** C72 reports `14 of 64 registered check(s) declare a falsification, 49 undeclared and excluded from PASS-eligibility; declaration is valid for 14 check(s) but no falsification was probed`. `infrastructure/quality/gate-mutations.yaml`
states outright that C72’s registry row can never report PASS outside `--sweep`, and no
workflow runs `--sweep` (verified by reading `truth-gates.yml`, `ci.yml`,
`integration.yml`, `mutation.yml` in full). **Zero of 64 gates have been mechanically
demonstrated to fail when their subject breaks.**

**Why it matters.** This is the earliest correctable cause in the repository. Every number
produced by every later requirement is only as trustworthy as the gate that reports it.

#### Acceptance Criteria

1. WHEN a commit is pushed to `main`, THE CI_Pipeline SHALL execute the gate-falsification
sweep in a step that carries no `continue-on-error` and no construct discarding its
exit status.
2. WHEN the sweep runs, THE sweep SHALL, for each check declaring a falsification, apply
that declared mutation and SHALL report the mutated check identifier together with
whether the mutation was **killed** or **survived**.
3. IF any declared falsification survives its mutation, THEN THE sweep SHALL exit non-zero
naming each surviving check identifier, and THE survival SHALL be recorded as a defect
against that check rather than against the sweep.
4. THE sweep SHALL NOT report PASS for any check whose falsification was not probed, and
WHERE a check declares no falsification, THE sweep SHALL report it as undeclared and
exclude it from PASS-eligibility.
5. IF the sweep cannot start, exceeds its time budget, or emits an unparseable report,
THEN THE gating step SHALL record a non-passing result.
6. THE 49 checks that declare no falsification SHALL NOT be given declarations that have
not been probed, because an unverified declaration converts a visible gap into false
assurance (I-7).

**Verdict: implemented but not integrated.**

**Falsification.** *What would prove this false:* a workflow step invoking
`gate_fault_injection --sweep` whose exit code gates a job. *Attempted:* read all four
candidate workflows in full. **[falsification attempted]**

---

### Requirement 2: Two thousand lines of authored frontend verification have never executed

**User Story:** As a reviewer, I want the console’s effectiveness properties actually run,
so that “authored and diagnostics-clean” stops being mistaken for “verified”.

**The verified reality.** Five fast-check property files (design Properties 31, 32, 33, 34,
36) were authored under an authoring-only constraint and never compiled or executed.
`getDiagnostics` returns **no TypeScript signal** in this workspace — proven by inserting a
deliberate type error and receiving an empty result, including for a file inside
`tsconfig.json`’s `include`.

`frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts` sits under `src/`,
which `tsconfig.json` includes, so it is inside `pnpm build`’s `tsc --noEmit`. In
`frontend.yml`, `build` gates `e2e`, `e2e-visual`, `e2e-harness`, `mobile-lighthouse`,
`effectiveness-ratchet` and `fe-invariants`. **One type error there skips the entire
console-effectiveness spine.**

#### Acceptance Criteria

1. WHEN the frontend CI job runs, THE CI_Pipeline SHALL execute `pnpm typecheck` and
`pnpm typecheck:spec`, and both SHALL propagate their exit status.
2. WHEN the frontend test job runs, THE CI_Pipeline SHALL execute all five declared
property files and SHALL report a per-file executed-assertion count.
3. IF a property file reports “no tests found”, THEN THE job SHALL record a non-passing
result, because a file matching no include pattern is not a pass.
4. WHERE a property reports a shrunk counterexample, THE counterexample SHALL be treated
as a defect in the subject under test, and THE property SHALL NOT be weakened to
accommodate it.
5. IF `pnpm typecheck` fails on a file under `src/**/__tests__/`, THEN THE failure SHALL be
reported as blocking the console-effectiveness spine, naming the downstream jobs that
will not execute.

**Verdict: not verifiable locally** at authoring time; the first CI run is the first
signal.

---

### Requirement 3: Example budgets are hardcoded on the TypeScript side

**User Story:** As the developer running tests on a 16 GB throttling laptop, I want the
fast-check budget inherited from a profile, so that a local run is cheap and a CI run is
thorough — the same contract Hypothesis already honours.

**The verified reality.** All five property files hardcode `{ numRuns: 100 }`, and
`tests/verify/test_property_inventory_consistency.py` now **enforces** `numRuns >= 100`.
The Python side inherits from the root `conftest.py` profiles (`dev`=10, `heavy`=100,
`ci`/`default`=500, `nightly`=5000), which is the entire I-0 mechanism. A gate was written
that mandates the violation.

#### Acceptance Criteria

1. THE fast-check example budget SHALL be configured once globally from an environment
profile via `fc.configureGlobal`, and THE default WHEN no profile is set SHALL be a
laptop-cheap value.
2. THE five property files SHALL carry no per-call `numRuns`, because a per-call value
overrides the global and adding the global alone changes nothing.
3. WHEN the property-inventory gate runs, THE gate SHALL fail on any hardcoded `numRuns`
in a declared TypeScript property file, mirroring its `max_examples` rule for Python.
4. WHEN the CI profile is selected, THE effective budget SHALL be at least 100 examples so
the pre-existing coverage obligation is preserved.

**Verdict: contradicted by evidence** — the gate mandates what the steering rule forbids.

---

### Requirement 4: Ten declared-blocking steps discard their exit status, and a published claim is transcribed by hand

**User Story:** As a maintainer, I want every non-propagating step either fixed or
honestly labelled, and every published number generated, so that red means red and no
document is bent to make a gate green.

**The verified reality.** C64 FAILs with `unlabelled-advisory=10` across 7 workflows.
`unlabelled_discarding_steps` in `infrastructure/quality/blocking-steps.yaml` is a **work
record the gate does not read**, so recording a step there does not change the verdict.

Separately, C56’s headline claim is self-referential: it validates `README.md`’s counts by
executing the suite, and its own status is inside the count it validates. Its recursion
guard makes the nested run self-exclude, so it enforces `51/3/0/10` while a top-level
`make verify-claims` prints `52/3/0/9`. **README currently states counts that no command a
human runs reproduces** — a document was bent to make a gate green, which is precisely the
inversion this project exists to prevent.

#### Acceptance Criteria

1. WHEN `workflow_shape_truth` runs, THE count of unlabelled non-propagating steps SHALL be
zero.
2. WHERE a step legitimately does not propagate, THE step name SHALL carry `ADVISORY` or
`informational`, and THE corresponding `blocking-steps.yaml` declaration SHALL be moved
in the same commit as the rename, because a declaration is matched by step-name string.
3. THE `README.md` headline counts SHALL be enclosed in a generated region and projected
from one registry execution, and THE region SHALL NOT be hand-editable without the
generator overwriting it.
4. IF the headline-counts claim cannot be evaluated, THEN THE aggregate SHALL be reported
unavailable and SHALL NOT be satisfied by an unrelated passing claim.
5. THE recursion-guard compensation SHALL be pinned by a test, so the adjustment cannot rot
silently if the guard’s behaviour changes.

**Verdict: partially achieved** — C64 is a known FAIL; the README inversion is new debt
introduced while closing the audit.

---

### Requirement 5: The simulated world does not reward intelligence

**User Story:** As a stakeholder asking whether multi-agent consensus is worth its
complexity, I want the twin to contain structure a coordinating system can exploit, so
that a measured uplift of zero is informative rather than inevitable.

**The verified reality.** The finding in the Introduction. Each added structure below must
name the agent decision it unlocks; nothing is added for realism’s sake.

#### Acceptance Criteria

1. WHEN the twin generates demand, THE demand intensity SHALL vary with intra-day, day-of-
week and promotional structure, and THE shape SHALL be calibrated from M5-derived
statistics rather than invented literals. *(Unlocks `demand_prophet`: forecasting has
zero value under stationary demand.)*
2. WHEN a perfect-foresight policy is run against the non-stationary twin, THE measured
regret of a base-stock `(s,S)` policy SHALL be strictly positive by a stated margin, and
IF it is not, THEN THE non-stationarity SHALL be reported as too weak to make forecasting
pay.
3. THE twin SHALL model finite rider and pick capacity as `simpy.Resource` pools, and THE
delivery wait SHALL be queue-dependent rather than an independent draw. *(Unlocks
`routing_navigator` and dispatch prioritisation: with infinite capacity, dispatch policy
is a no-op.)*
4. WHEN utilisation approaches saturation, THE relationship between utilisation and wait
time SHALL be monotone and super-linear, exhibiting a queueing signature.
5. THE twin SHALL correlate supplier lead time with demand and auto-correlate it across
days, and THE per-supplier reliability SHALL be learnable. *(Unlocks `supplier_trust`
and `inventory_sentinel`: under i.i.d. lead times a static safety stock is optimal.)*
6. WHEN a supplier-aware reorder policy is compared with a supplier-blind one, THE
supplier-aware policy SHALL achieve a strictly better KPI aggregate.
7. THE twin SHALL make spoilage a function of age-at-arrival and order size, and SHALL
divert a fraction of stocked-out demand to substitute SKUs. *(Unlocks
`freshness_guardian` and `pricing_oracle`.)*
8. WHEN the four single-objective policies (minimise stockout, minimise spoilage, minimise
holding cost, maximise SLA) are evaluated, THE set of Pareto-optimal policies SHALL
exclude every one of them. *(This is the mathematical precondition for a consensus
system to have room to win.)*
9. THE `_delivery` docstring’s claim of an “OSRM travel time estimate” SHALL be made true
or removed, because the code draws `rng.uniform(10.0, 45.0)` and makes no OSRM call.
10. WHILE these structures are added, THE neutral-default behaviour SHALL remain
reproducible for the existing determinism tests, or THE affected tests SHALL be updated
in the same change with their new expectations stated.

**Verdict: not achieved.**

**Falsification.** *What would prove this finding false:* a measured positive `(s,S)`
regret on the unmodified twin. *Not yet attempted — requires compute.* **[unchallenged]**

---

### Requirement 6: The measuring instrument has never been shown able to detect an effect

**User Story:** As a scientist reading an uplift result, I want the harness proven able to
detect a known effect of known size, so that a null result means “no effect” rather than
“blind instrument”.

**The verified reality.** The predecessor spec specified a **negative** control (its R2.6:
identical arms must yield an interval containing zero) and **no positive control**. This is
a gap in the audit spec itself. Without a positive control, a zero result is
uninterpretable.

#### Acceptance Criteria

1. WHEN the Consensus_Arm is replaced by a byte-identical copy of the Baseline_Arm and the
harness runs at the powered replicate count, THE 95% interval of headline uplift SHALL
contain zero, and THE Uplift_Gate SHALL NOT report a proven gain.
2. WHEN a known-exploitable structure is present and an Oracle_Arm plays the analytically
optimal policy for it, THE headline uplift SHALL be positive with its 95% interval
excluding zero.
3. THE measured oracle effect SHALL fall within a stated tolerance of the analytic optimum,
and IF it does not, THEN THE harness SHALL be reported as mis-measuring rather than the
oracle as under-performing.
4. THE harness SHALL publish a power curve stating the minimum detectable effect at the
chosen replicate count and the assumed variance.
5. WHILE no power curve exists, THE project SHALL NOT publish any uplift result, because an
unpowered null is not evidence of absence.
6. WHEN the same seed set is replayed in two separate operating-system processes, THE
harness SHALL produce byte-identical arm KPI aggregates.

**Verdict: not achieved** — and the positive control is a new obligation this spec adds.

---

### Requirement 7: The uplift gate certifies what its own input denies

**User Story:** As a stakeholder asking “are the decisions better?”, I want the gate to
answer from a completed, powered, fidelity-bounded experiment, so the answer is evidence
rather than a tautology.

**The verified reality.** Four facts, each read directly:

1. `uplift/uplift_floor.py:47` — `UPLIFT_FLOOR: float = 0.0`.
2. `artifacts/uplift/result.json` — `{"headline_uplift": 0.0, "incomplete": true, "fidelity": {"confidence": "unknown", "within_fidelity_bound": null}}`.
3. `scripts/audit/uplift_truth.py::read_measured_uplift` reads **only** `headline_uplift`;
it never consults `incomplete` or fidelity. The comparison is `0.0 < 0.0` -> false ->
`EXIT_PASS`.
4. `is_proven_uplift` (`uplift_floor.py:204`) and `ratchet_to_measured` (`:247`) are
imported **only by three test files** — tested and unreachable from production.

#### Acceptance Criteria

1. IF the evaluated artifact carries `incomplete` as `true`, omits it, or carries a
non-boolean value, THEN THE Uplift_Gate SHALL exit `EXIT_UNAVAILABLE` (`2`) printing the
reason.
2. IF the artifact records fewer replicates per arm than `MIN_POWERED_REPLICATES`, THEN THE
Uplift_Gate SHALL exit `2` printing both the recorded and required counts.
3. IF `within_fidelity_bound` is `null` or `false`, THEN THE Uplift_Gate SHALL exit non-zero
irrespective of the headline magnitude.
4. THE Uplift_Gate SHALL derive its verdict from `is_proven_uplift`, and WHEN
`is_proven_uplift` is replaced by a stub returning the opposite verdict, THE exit code
SHALL change.
5. THE CI_Pipeline SHALL regenerate the artifact by running the harness in the same job that
evaluates the gate, and IF the harness cannot run, THEN that job SHALL record a
non-passing result.
6. IF the artifact was read from version control, or its provenance revision, seed set or
arm identifiers differ from the run performed in the evaluating job, THEN THE gate SHALL
exit `2`.
7. WHEN `UPLIFT_FLOOR` is raised above `0.0`, THE raise SHALL be admitted only through
`ratchet_to_measured` against a `PoweredProof` built in the same job.
8. WHERE the gate exits with any code other than `0`, THE published PASS count SHALL exclude
it.

**Verdict: contradicted by evidence.**

---

### Requirement 8: No model has been trained on non-synthetic data, and no claim is externally benchmarked

**User Story:** As a sceptic, I want the flagship model scored against a published
leaderboard, so that “intelligent” is externally auditable rather than self-certified.

**The verified reality.** `artifacts/` contains only `uplift/`; there is no
`artifacts/checkpoints/`. Real training loops exist and are gated — C37 passes and
`scripts/audit/training_truth.py` AST-flags sentinel returns and un-stepped optimizers — but
they have produced no published artifact. No claim in this repository is compared with any
external benchmark.

#### Acceptance Criteria

1. THE flagship agent SHALL train on the M5 dataset, and THE ingestion SHALL record
`feature_source` provenance identifying the real feed rather than a stub.
2. THE training run SHALL record its score against the published M5 **Uncertainty**
leaderboard, including the seasonal-naive baseline, because that track scores quantiles
and maps directly onto this agent’s pinball/CRPS objective and conformal intervals.
3. IF the exact published leaderboard values cannot be confirmed at implementation time,
THEN THE recorded comparison SHALL state that limitation rather than asserting an
unverified number.
4. WHEN held-out coverage is evaluated, THE gate SHALL **recompute** `coverage_p90` from the
published sidecar’s predictions rather than trusting the recorded value, and THE floor
SHALL be `>= 0.85` (INV-DP-002).
5. THE training SHALL run at zero cost (I-1) on free GPU capacity per
`docs/runbooks/train-and-publish-checkpoint.md`, and no paid API or host SHALL be
introduced.
6. THE domain gap between daily retail demand and 10-minute quick-commerce SHALL be
documented explicitly, and SHALL NOT be presented as equivalent.

**Verdict: not achieved.**

---

### Requirement 9: One unpublished artifact collapses five gates and the confidence contract

**User Story:** As an operator reading a confidence value, I want it derived from a live
conformal interval, so that `confidence` measures something rather than reporting a floor.

**The verified reality.** `infrastructure/ml/published_checkpoints.json` holds only
`__placeholder__` with `status: "unpublished"`. Consequences, each traced:

- Every agent takes the degraded path, so `agents/demand_prophet/inference/pipeline.py`
emits `confidence = FALLBACK_CONFIDENCE` — a constant — instead of the conformal-derived
`1.0 / (1.0 + mean_rel_width)`.
- C38, C40, C45 and C46 all SKIP.
- C69 FAILs: `core-purpose-uplift` tasks 9 and 9.1 are marked `[x]` against the unchanged
placeholder.

The machinery for real confidence is built and tested; the input it needs does not exist.

#### Acceptance Criteria

1. WHEN a checkpoint is published and recorded, THE Model_Registry SHALL resolve it through
the production serving path returning an object whose `degraded` is `false` and whose
version string contains the recorded sha.
2. WHILE a real checkpoint is resolved, THE flagship pipeline SHALL emit a
`confidence_basis` of `CONFORMAL_INTERVAL` and a confidence that varies across SKUs.
3. IF the resolved artifact was produced by a smoke run, THEN THE check SHALL exit non-zero,
and THE detail SHALL distinguish a smoke artifact from an absent one.
4. THE `allow_local_substitution` flag SHALL remain `false`, and IF a recorded sha cannot be
fetched from the declared zero-cost source, THEN THE check SHALL NOT resolve a locally
built checkpoint in its place.
5. WHEN a registry entry records `final_crps`, THE check SHALL recompute it from the
published sidecar’s held-out predictions and SHALL exit non-zero beyond the declared
tolerance.
6. WHILE no checkpoint is published, THE pipeline SHALL report `degraded = true` on every
response and THE Atlas_Console SHALL render that degradation on every displaying surface.
7. WHEN a task record asserts a landed registry entry, THE task-completion check SHALL read
the registry and SHALL fail naming the record IF no validated non-placeholder entry
exists.

**Verdict: not achieved** for the published model; **demonstrably achieved** for the serving
path and for honest degradation in its absence.

---

### Requirement 10: The audit chain has no external verifiability

**User Story:** As an auditor who does not trust this repository, I want to verify the audit
chain independently, so that tamper-evidence is a claim I can check rather than one I must
accept.

**The verified reality.** C67: `chain=unverifiable, 0 anchor file(s); no anchor exists`.
Internal anchors under `infrastructure/audit_anchors/` exist; publication to an external
tamper-evidence log does not.

#### Acceptance Criteria

1. WHEN an anchor is produced, THE system SHALL publish it to a free external
tamper-evidence log.
2. WHEN a third party holds only the published anchor and the chain rows, THEY SHALL be able
to verify chain integrity without trusting this repository.
3. IF an anchor cannot be published, THEN THE check SHALL report unavailable naming the
reason, and SHALL NOT report a pass.
4. THE published anchor SHALL commit to the chain head, and THE anchor freshness SHALL be
gated against a declared maximum age.

**Verdict: not achieved.**

---

## PRESERVE — what must not be broken

Credited with citations, because a plan that damages these is a net loss:

- **The generated Truth Ledger.** `docs/state/CURRENT.md`’s `generated:begin/end` region is
projected from ONE `registry_gate` execution by `scripts/audit/ledger_gen.py`. The row set
*is* the registered identifier set; the counts *are* that execution’s counts. Very few
repositories anywhere do this.
- **The honest-degradation contract.** `packages/synapse_common/provenance.py` and its rule
that `confidence_basis` may never be `constant`, enforced by
`scripts/audit/substance_truth.py` (AST) at 0 violations across 8 pipelines.
- **The byte-pinned audit chain.** `orchestrator/audit/hash_chain.py::make_canonical_row`
and I-4 append-only discipline. Adding or removing a field requires a chain-rewrite
migration, not a silent bump (E-S9-02).
- **The twin’s refusal to invent opening stock.** `start(initial_inventory=...)` starts the
world genuinely empty for a non-seeded source rather than reporting invented inventory
(R4.9). I-7 discipline inside a simulator.
- **`unavailable -> SKIP`, never PASS** in the registry status mapping.
- **`ledger_gen.generated_region_bounds`**, which recognises a marker only when it owns its
line — the fix for a checker that could not tell prose *about* a marker from a marker.

## Non-goals

- No new frontend features. 32,087 lines already correctly report “nothing to trust yet”.
- No declaring the 49 unprobed falsification operators (R1.6).
- No Kubernetes/Helm breadth; C12/C13 are honest skeletons and a single GCP VM matches I-1.
- C44’s Windows-only `FileNotFoundError` on a deep pnpm path is **guarded, not chased**.
- No replacement of the twin with a live feed; no live retail source exists at $0, and
controlled shock injection is where consensus should win.

## Dependency order

R1–R4 are prerequisites for trusting any later measurement. R5 precedes R6. R6 precedes any
published result from R7. R8 precedes R9. R7 and R9 together precede any headline claim about
decision quality.
File 2 — design.md
markdown

# Design Document

> **Decision Quality Proof** — how the measurement becomes trustworthy.
> 

## Design principle

Every element answers one of two questions: *does this make a claim falsifiable?* or *does
this make a decision matter?* Nothing is added for realism, completeness, or polish.

## Architecture of the change

```mermaid
graph TD
    E1[E1 Gate falsifiability] --> E3
    E2[E2 Twin decision-relevance] --> E3[E3 Controlled experiment]
    E3 --> E5[E5 Measured uplift + ratchet]
    E4[E4 M5 ingest, train, publish] --> E5
    E1 --> E4
```

E1 must land first: it is what makes every later gate verdict mean something. E2 before E3
because an instrument validated on a flat world proves nothing. E4 in parallel with E2–E3
because training is wall-clock-bound on free GPU. E5 last.

---

## E1 — Gate falsifiability harness

**Decision.** Run `gate_fault_injection --sweep` as a blocking step in `truth-gates.yml`,
on the 14 checks that already declare a falsification. Do **not** declare the other 49
first.

**Why.** An unverified declaration converts a *visible* gap (49 undeclared, honestly
reported) into *false assurance* (49 declared, none probed). That is the exact trade I-7
forbids, and it is why task 12.1 of the predecessor spec correctly left C67 undeclared.

**Expected outcome, stated in advance:** some of the 14 will **survive**. A surviving
mutant is a gate that does not enforce. That is the finding, not a failure of the sweep.

**Cost control (I-0).** The sweep copies the tree and executes gates — category 2/3. It runs
on CI Linux runners only, never on the development machine (precedent E-S13-05: `mutmut`
validated on CI, never the Windows box).

---

## E2 — Twin decision-relevance

The five structures, each with the decision it unlocks and the property that proves it
landed.

| Structure | Agent decision unlocked | Falsifiable property |
| --- | --- | --- |
| Non-stationary demand (intra-day, day-of-week, promo, weather) | `demand_prophet` — forecasting is worthless under stationary demand | Perfect-foresight policy beats `(s,S)`; `(s,S)` regret > stated margin |
| Finite rider + pick capacity (`simpy.Resource`) | `routing_navigator`, dispatch priority — a no-op under infinite capacity | Utilisation → wait is monotone and super-linear near saturation |
| Lead time correlated with demand, auto-correlated across days; per-supplier reliability | `supplier_trust`, `inventory_sentinel` — static safety stock is optimal under i.i.d. lead times | Supplier-aware reorder beats supplier-blind |
| Spoilage as f(age-at-arrival, order size) | `freshness_guardian` — bulk-order/spoilage tension | Order size ↔︎ spoilage coupling is measurable |
| Cross-SKU substitution on stockout | `pricing_oracle`, and genuine multi-objective tension | **No single-objective policy is Pareto-optimal across stockout, spoilage, holding cost, SLA** |

**The last row is the load-bearing one.** It is the mathematical precondition for a
consensus system to have room to win. If any single-objective policy remains Pareto-optimal,
consensus is provably unnecessary and the experiment should not be run.

**Calibration source.** Seasonality and intermittency shapes derive from M5 statistics, not
invented literals. This ties E2 to E4 and keeps AD-13 (“every new threshold is a committed,
pinned constant”) satisfiable: shapes land in a committed policy file, not in `engine.py`.

**Backward compatibility.** Neutral defaults must reproduce today’s behaviour so the
existing determinism tests hold, or those tests are updated in the same change with new
expectations stated. Do not let a fidelity improvement silently invalidate a determinism
guarantee.

**Record first.** `docs/adr/ADR-055-twin-decision-relevance.md` states the inventory-theory
argument, the five structures, and the falsifiable claim *“after this phase a base-stock
`(s,S)` policy is measurably sub-optimal on this twin”* — before any code.

---

## E3 — The controlled experiment

This is the scientific core, and it closes a gap in the predecessor spec.

### Three arms, not two

| Arm | Purpose | Expected result |
| --- | --- | --- |
| Baseline | The transparent comparator: base-stock `(s,S)` | reference |
| Consensus | The system under test | unknown — that is the point |
| **Oracle** | **Positive control**: analytically optimal for an injected known structure | **must be detected** |

### Both controls, as BDD scenarios

```gherkin
Scenario: Negative control — the instrument does not hallucinate an effect
  Given the Consensus_Arm is replaced by a byte-identical copy of the Baseline_Arm
  When the Uplift_Harness runs at MIN_POWERED_REPLICATES per arm
  Then the 95% interval of headline uplift contains zero
  And the Uplift_Gate does not report a proven gain

Scenario: Positive control — the instrument detects a known effect
  Given the twin carries a known-exploitable demand seasonality
  And an Oracle_Arm plays the analytically optimal policy for that seasonality
  When the Uplift_Harness runs at MIN_POWERED_REPLICATES per arm
  Then headline uplift is positive with its 95% interval excluding zero
  And the measured effect is within tolerance of the analytic optimum
```

**Why the positive control is the most important single element in this spec.** Without it,
a zero uplift is ambiguous: the system may be no better, or the instrument may be blind.
With it, the harness can state *“this design detects a ≥X% effect with ≥80% power at N
replicates”* — and that sentence is what makes a null result publishable.

### Power analysis

Produce a power curve (effect size vs detection probability at the chosen replicate count
and observed variance). `MIN_POWERED_REPLICATES` is currently `1000`; the curve either
justifies it or replaces it with a derived number. **Until the curve exists, no uplift
result may be published** (R6.5).

### Determinism

Byte-identical arm aggregates across two OS processes for a fixed seed set (R6.6). Without
it, the interval is not reproducible and the ratchet is not defensible.

---

## E4 — M5 ingestion, training, publication

**Dataset decision.** M5 (Walmart), ~42,000 hierarchical daily series.

**Why M5 and not a synthetic-but-realistic generator:** it is the only option that supplies
an **external published leaderboard**, and its **Uncertainty track scores quantiles**, which
maps directly onto `demand_prophet`’s pinball/CRPS objective and its conformal intervals. It
converts “we trained a model” into “our model scores X against a published benchmark”.

**Prediction, stated in advance so the result cannot be rationalised afterwards.** Per the
M-Competitions’ replicated finding, expect the sophisticated model to be **competitive, not
dominant** on point accuracy. Plan the narrative around calibration quality and the
Uncertainty track, where conformal intervals genuinely earn their place. If the model
dominates, that is a surprise worth investigating, not a validation of complexity.

**Domain gap.** Daily retail demand is not 10-minute quick-commerce. Document it; do not
elide it (R8.6).

**Publication.** HF Hub, free. `docs/runbooks/train-and-publish-checkpoint.md` exists.
Publishing flips C38, C40, C45, C46 from SKIP to PASS and clears the C69 FAIL — and, more
importantly, makes `confidence` stop being `FALLBACK_CONFIDENCE` and start being
`1.0 / (1.0 + mean_rel_width)` from a live conformal interval.

**Sequencing rationale.** Published *before* E2/E3, the model’s contribution to decision
quality is undemonstrable. Published *after*, it is measurable. Same artifact, different
evidential value.

---

## E5 — Measured uplift, ratchet, external anchoring

- The harness regenerates the artifact **in the job that evaluates it**; an artifact read
from version control is refused (R7.5, R7.6).
- `uplift_truth` routes through `is_proven_uplift`. Mutation test: stubbing that predicate to
return the opposite verdict **must** change the gate’s exit code (R7.4). Today it would
not, because the predicate is unreachable.
- `UPLIFT_FLOOR` rises only via `ratchet_to_measured` against a `PoweredProof` from the same
job (R7.7).
- Anchors publish to a free external log; a third party verifies without trusting this repo
(R10).

---

## Property inventory

Properties are numbered continuing from the predecessor spec’s 37. Every property test
carries the tag `Feature: decision-quality-proof, Property {N}: {title}` on its own comment
line, and inherits its example budget from a profile — `max_examples` for Hypothesis,
`fc.configureGlobal` for fast-check. Never hardcoded (R3).

| # | Property | Validates |
| --- | --- | --- |
| 38 | Every declared falsification kills its mutant, and a survivor is named | R1.2, R1.3 |
| 39 | A check with no declared falsification is never PASS-eligible | R1.4 |
| 40 | The fast-check budget is inherited, never per-call | R3.1, R3.2 |
| 41 | Every non-propagating step is labelled and declared | R4.1, R4.2 |
| 42 | The headline region is generated and hand edits do not survive | R4.3 |
| 43 | Demand intensity is non-stationary over every generated horizon | R5.1 |
| 44 | `(s,S)` regret is strictly positive under non-stationarity | R5.2 |
| 45 | Utilisation → wait is monotone and super-linear near saturation | R5.4 |
| 46 | Supplier-aware reorder dominates supplier-blind | R5.6 |
| 47 | No single-objective policy is Pareto-optimal | R5.8 |
| 48 | Identical arms yield an interval containing zero | R6.1 |
| 49 | An oracle-exploitable effect is detected within tolerance | R6.2, R6.3 |
| 50 | Arm aggregates are byte-identical across processes for a fixed seed | R6.6 |
| 51 | An incomplete/under-powered/fidelity-unbounded artifact is unavailable, never a pass | R7.1–R7.3 |
| 52 | Stubbing `is_proven_uplift` changes the gate’s exit code | R7.4 |
| 53 | A version-controlled or provenance-mismatched artifact is refused | R7.6 |
| 54 | Recomputed `coverage_p90` meets its floor; a recorded value is never trusted | R8.4 |
| 55 | A smoke artifact is distinguishable from absent and from real, and never substituted | R9.3, R9.4 |
| 56 | A real checkpoint yields `CONFORMAL_INTERVAL` basis and SKU-varying confidence | R9.2 |
| 57 | An unpublishable anchor is unavailable, never a pass | R10.3 |

## Cross-cutting concerns

**CF-1 — the twin’s determinism tests.** E2 changes dynamics. Either neutral defaults
reproduce today’s behaviour exactly, or the affected tests are updated in the same change
with their new expectations stated. Resolve deliberately; do not discover it in CI.

**CF-2 — I-0 budget.** E3’s powered runs (1000 replicates × 3 arms) are category 4 and
belong in `uplift.yml` on CI. Locally: one scoped run, `HYPOTHESIS_PROFILE=dev`, never the
full sweep.

**CF-3 — ratchets.** Every new threshold (regret margin, power floor, coverage floor,
substitution rate) lands in a committed policy file under `infrastructure/quality/` with a
`ratchets.json` entry whose extractor is **verified by running it**, per AD-13 and the
precedent set when the `audit/chain-walk` ceiling shipped without one.

**CF-4 — the M5 licence.** Confirm the dataset’s terms permit this use before ingestion, and
record the finding. An unverified licence is a real risk, not a formality.
File 3 — tasks.md
markdown

# Implementation Plan: Decision Quality Proof

> Phases are ordered by *evidential dependency*, not convenience. Phase 0 makes every later
number trustworthy. Phase 1 makes the number possible. Phase 2 makes it interpretable.
Only Phase 4 produces a headline.
> 
> 
> **I-0 applies throughout.** Powered uplift runs, mutation sweeps, Playwright matrices and
> training are CI-only (categories 1–4). Locally: one scoped test run at a time,
> `HYPOTHESIS_PROFILE=dev`, never a watcher.
> 
- [ ]  0. Phase 0 — Make the instruments trustworthy
    - [ ]  0.1 Add the gate-falsification sweep as a blocking CI step
        - New step in `.github/workflows/truth-gates.yml` running
        `python -m scripts.audit.gate_fault_injection --sweep`; no `continue-on-error`, no
        `|| true`. Linux runners only (E-S13-05)
        - Expect survivors among the 14 declared falsifications and record each by name. A
        survivor is a defect against that gate, not against the sweep
        - Do **not** declare the other 49 operators
        - *Requirements: 1.1, 1.2, 1.3, 1.5, 1.6*
    - [ ]  0.2 Write property test for falsification completeness
        - **Property 38: Every declared falsification kills its mutant, and a survivor is named**
        - **Property 39: A check with no declared falsification is never PASS-eligible**
        - *Requirements: 1.2, 1.3, 1.4*
    - [ ]  0.3 Execute the five authored frontend property files
        - Wire `pnpm typecheck`, `pnpm typecheck:spec` and a scoped `vitest run` over
        `spec/effectiveness/__tests__` and `src/surfaces/__tests__` into `frontend.yml`
        - Treat a shrunk counterexample as a defect in the subject; treat “no tests found” as a
        failure
        - Record which downstream jobs a `src/**/__tests__` type error would skip
        - *Requirements: 2.1, 2.2, 2.3, 2.4, 2.5*
    - [ ]  0.4 Replace hardcoded `numRuns` with an inherited profile
        - `fc.configureGlobal({ numRuns })` from an env profile in `src/test/setup.ts`; delete
        per-call `{ numRuns: 100 }` from all five files
        - Flip `tests/verify/test_property_inventory_consistency.py` to forbid hardcoded
        `numRuns`, mirroring its `max_examples` rule
        - *Requirements: 3.1, 3.2, 3.3, 3.4*
    - [ ]  0.5 Write property test for budget inheritance
        - **Property 40: The fast-check budget is inherited, never per-call**
        - *Requirements: 3.1, 3.2*
    - [ ]  0.6 Fix the ten unlabelled non-propagating steps
        - Rename each to carry `ADVISORY`/`informational` **and** move its
        `blocking-steps.yaml` declaration in the same commit — declarations are matched by
        step-name string
        - `unlabelled_discarding_steps` is a work record the gate does not read; recording is
        not fixing
        - *Requirements: 4.1, 4.2*
    - [ ]  0.7 Move the README headline into a generated region
        - Enclose the counts in `generated:begin/end` projected by `ledger_gen`, so no human
        transcribes them
        - Fix `doc_truth::_claim_readme_headline_counts` to compensate for its own recursion
        guard, and pin the compensation with a test so it cannot rot
        - *Requirements: 4.3, 4.4, 4.5*
    - [ ]  0.8 Write property tests for step propagation and generated claims
        - **Property 41: Every non-propagating step is labelled and declared**
        - **Property 42: The headline region is generated and hand edits do not survive**
        - *Requirements: 4.1, 4.2, 4.3*
- [ ]  1. Checkpoint — instruments
    - Every gate verdict from here on is trustworthy only if 0.1 killed its mutants. Review
    the survivor list with the user before proceeding; a survivor may invalidate a claim
    elsewhere in the repo.
- [ ]  2. Phase 1 — Make the world worth deciding in
    - [ ]  2.1 Record ADR-055 before any code
        - `docs/adr/ADR-055-twin-decision-relevance.md`: the inventory-theory argument, the five
        structures, the agent decision each unlocks, and the falsifiable claim that `(s,S)`
        becomes measurably sub-optimal
        - *Requirements: 5.1, 5.3, 5.5, 5.7, 5.8*
    - [ ]  2.2 Measure `(s,S)` regret on the UNMODIFIED twin first
        - This is the falsification test for the spec’s central finding. If regret is already
        materially positive, Phase 1’s scope shrinks — report before building
        - *Requirements: 5.2*
    - [ ]  2.3 Implement non-stationary demand
        - Intra-day double peak, day-of-week, promotional pulses, weather shock. Shapes from
        M5-derived statistics into a committed policy file, not literals in `engine.py`
        - *Requirements: 5.1, 5.10*
    - [ ]  2.4 Write property tests for non-stationarity and regret
        - **Property 43: Demand intensity is non-stationary over every generated horizon**
        - **Property 44: `(s,S)` regret is strictly positive under non-stationarity**
        - *Requirements: 5.1, 5.2*
    - [ ]  2.5 Implement finite rider and pick capacity
        - `simpy.Resource` pools; delivery wait becomes queue-dependent. Make the `_delivery`
        docstring’s OSRM claim true or remove it
        - *Requirements: 5.3, 5.9, 5.10*
    - [ ]  2.6 Write property test for the queueing signature
        - **Property 45: Utilisation → wait is monotone and super-linear near saturation**
        - *Requirements: 5.4*
    - [ ]  2.7 Implement correlated lead times and per-supplier reliability
        - Correlated with demand, auto-correlated across days, learnable per supplier
        - *Requirements: 5.5, 5.10*
    - [ ]  2.8 Write property test for supplier awareness
        - **Property 46: Supplier-aware reorder dominates supplier-blind**
        - *Requirements: 5.6*
    - [ ]  2.9 Implement spoilage/order-size coupling and cross-SKU substitution
        - Spoilage as f(age-at-arrival, order size); stockouts divert a fraction of demand
        - *Requirements: 5.7, 5.10*
    - [ ]  2.10 Write property test for multi-objective tension
        - **Property 47: No single-objective policy is Pareto-optimal**
        - This is the precondition for consensus to have room to win. If it fails, stop and
        report — the experiment should not be run
        - *Requirements: 5.8*
- [ ]  3. Checkpoint — the world
    - Confirm Property 47 holds before building the experiment. Ask the user if it does not.
- [ ]  4. Phase 2 — Validate the measuring instrument
    - [ ]  4.1 Implement the negative control
        - Consensus arm replaced by a byte-identical copy of the baseline arm
        - *Requirements: 6.1*
    - [ ]  4.2 Implement the Oracle arm and the positive control
        - A known-exploitable structure plus its analytically optimal policy. The measured effect
        must fall within tolerance of the analytic optimum
        - *Requirements: 6.2, 6.3*
    - [ ]  4.3 Write property tests for both controls
        - **Property 48: Identical arms yield an interval containing zero**
        - **Property 49: An oracle-exploitable effect is detected within tolerance**
        - *Requirements: 6.1, 6.2, 6.3*
    - [ ]  4.4 Produce and commit the power curve
        - Effect size vs detection probability at the replicate count and observed variance.
        Either justify `MIN_POWERED_REPLICATES = 1000` or replace it with a derived value
        - *Requirements: 6.4, 6.5*
    - [ ]  4.5 Write property test for cross-process determinism
        - **Property 50: Arm aggregates are byte-identical across processes for a fixed seed**
        - *Requirements: 6.6*
    - [ ]  4.6 Route `uplift_truth` through `is_proven_uplift`
        - Honour `incomplete`, replicate count and `within_fidelity_bound`; exit 2 on any.
        Refuse a version-controlled or provenance-mismatched artifact. Regenerate in the
        evaluating job
        - *Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.8*
    - [ ]  4.7 Write property tests for the gate’s honesty
        - **Property 51: An incomplete/under-powered/fidelity-unbounded artifact is unavailable**
        - **Property 52: Stubbing `is_proven_uplift` changes the gate’s exit code**
        - **Property 53: A version-controlled or provenance-mismatched artifact is refused**
        - *Requirements: 7.1, 7.2, 7.3, 7.4, 7.6*
- [ ]  5. Phase 3 — Real intelligence on real data
    - [ ]  5.1 Confirm the M5 licence permits this use, and record the finding
        - *Requirements: 8.1*
    - [ ]  5.2 Implement M5 ingestion with real provenance
        - `feature_source` identifies the real feed, not a stub. Satisfies the non-synthetic
        ingestion obligation with a real dataset
        - *Requirements: 8.1*
    - [ ]  5.3 Train the flagship on M5 and record the external benchmark
        - Free GPU per the runbook (I-1). Record the score against the published M5 **Uncertainty**
        leaderboard including the seasonal-naive baseline. If exact leaderboard values cannot be
        confirmed, state that limitation rather than asserting a number
        - Expect competitive, not dominant, point accuracy — per the M-Competitions’ replicated
        finding. Do not rationalise the result afterwards
        - *Requirements: 8.2, 8.3, 8.5, 8.6*
    - [ ]  5.4 Recompute coverage in the gate rather than trusting the sidecar
        - *Requirements: 8.4*
    - [ ]  5.5 Write property test for recomputed coverage
        - **Property 54: Recomputed `coverage_p90` meets its floor; a recorded value is never
        trusted**
        - *Requirements: 8.4*
    - [ ]  5.6 Publish the checkpoint and land the registry entry
        - Flips C38, C40, C45, C46 SKIP → PASS and clears the C69 FAIL. `confidence` becomes
        conformal-derived rather than `FALLBACK_CONFIDENCE`
        - *Requirements: 9.1, 9.2, 9.7*
    - [ ]  5.7 Write property tests for artifact classification and confidence
        - **Property 55: A smoke artifact is distinguishable from absent and from real, and never
        substituted**
        - **Property 56: A real checkpoint yields `CONFORMAL_INTERVAL` basis and SKU-varying
        confidence**
        - *Requirements: 9.2, 9.3, 9.4, 9.5, 9.6*
- [ ]  6. Checkpoint — substance
    - Confirm the confidence contract is live: a real checkpoint resolving, `degraded == false`,
    and confidence varying across SKUs.
- [ ]  7. Phase 4 — Measure, ratchet, anchor
    - [ ]  7.1 Run the powered three-arm experiment in CI
        - `uplift.yml`; artifact regenerated in the evaluating job
        - *Requirements: 7.5, 6.4*
    - [ ]  7.2 Ratchet `UPLIFT_FLOOR` to the measured lower bound
        - Only via `ratchet_to_measured` against a `PoweredProof` from the same job
        - *Requirements: 7.7*
    - [ ]  7.3 Publish anchors to an external tamper-evidence log
        - *Requirements: 10.1, 10.2, 10.4*
    - [ ]  7.4 Write property test for anchor honesty
        - **Property 57: An unpublishable anchor is unavailable, never a pass**
        - *Requirements: 10.3*
    - [ ]  7.5 Register every new check and regenerate the generated documents
        - Add ratchet entries for every new threshold (regret margin, power floor, substitution
        rate) with extractors **verified by running them** (CF-3, AD-13)
        - Run `ledger_gen --write` and `gate_surface --write` last, after all registrations
        - *Requirements: 1.1, 4.3*
- [ ]  8. Final checkpoint
    - The claim this spec exists to support: **a headline uplift with a confidence interval,
    from a completed powered run, on a twin where being smart is possible, measured by an
    instrument proven able to detect an effect of that size, with a model benchmarked
    against a published leaderboard.**
    - Report honestly if the measured uplift is zero or negative. A null result from a
    validated instrument on a decision-relevant world is a **real finding** and far more
    valuable than the tautological PASS it replaces.
    The spec is complete: requirements.md (10 requirements, ~60 EARS criteria), design.md (5 design elements, 20 new properties, 4 cross-cutting concerns), tasks.md (36 tasks across 5 phases with 4 checkpoints). Save the three blocks above to .kiro/specs/decision-quality-proof/ and you can begin implementing by reviewing the tasks in tasks.md.

Three things I want to be straight about before you start.

I could not write the files — no write tool was available this turn, and sub-agent dispatch failed three times, so I stopped retrying rather than burn another attempt. The content above is complete and ready to commit verbatim.

Task 2.2 is deliberately sequenced to try to kill my own central finding. It measures (s,S) regret on the unmodified twin. If regret is already materially positive, my inventory-theory argument is wrong and Phase 1 shrinks a lot. Run it before building anything in Phase 1.

Task 8 pre-commits to reporting a null result. That matters more than it looks: the honest failure mode of this whole plan is doing the work and then rationalising a zero. A null uplift from a validated instrument on a decision-relevant world is the most valuable thing this project could learn — it would mean the four-tier consensus architecture is not earning its complexity, which is exactly the question the system was built to answer.

---

1. a-z_[↩︎](about:blank#fnref1)
