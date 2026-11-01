---
inclusion: auto
name: engineering-learnings
description: Lessons from decision-quality-proof session 12 (2026-10-15 to 2026-11-01), each with its evidence - stating claims honestly, diagnosing failures from logs, systems couplings and certificates, sequencing, subagent batching, CI as the execution substrate, security on a public repository, and working with the operator. Load when planning or running a multi-step session, diagnosing a CI or measurement failure, dispatching subagents, or writing a claim, ledger or handoff.
---

# Engineering learnings: what session 12 taught, with the evidence for each

**What this file is.** Lessons, not rules. The four always-included steering files are the rules,
and they govern any conflict. Each lesson names its evidence (a finding in
`.kiro/specs/decision-quality-proof/tasks.md`, a run, or a measured number), so it can be checked,
and deleted if it turns out wrong. The concrete repository traps are recorded once, as `E-DQP-*`
in `CLAUDE.md`'s Accumulated Error Patterns; this file states the principles behind them.

**How to add to it.** One lesson per entry, stated so that a future session could fail it, with its
evidence beside it. Point to a finding; never copy its body.

## 1. Purpose: what the work is for

1. **The deliverable is the claim, and a negative claim is a complete result.** The spec existed to
   state one number honestly. It came out at -4.40 objective units against the tuned control,
   `baseline_wins`, and its cause (finding 112) tells the operator what to fix next. A positive
   number reached by relabelling would have told them nothing true.
2. **Measure the system as wired, not as designed.** Every agent reads its request one level too
   shallow, so consensus never read the world (finding 112). The agent tests passed because they
   send flat params (`tests/integration/test_agent_pipeline.py:69`); only the real closed loop,
   through the protocol's real envelope, exposed it. A test that bypasses the real interface tests
   a system that does not exist.
3. **Rank work by whose decision it changes.** Finding 112 decides where product effort goes next.
   Most findings change no decision; they are inventory. Before starting a unit of work, name the
   reader whose next decision it changes.
4. **Commit to how a result will be reported before it is known.** Task 25 required a negative
   headline to be reported as negative, with its cause, and never re-run until it moved. When the
   number came back negative, there was nothing left to decide, so nothing could be rationalised.

## 2. First principles: measure before arguing

5. **Decompose a cost into phases and unit costs, then compare it with what was observed.** A
   read-only estimate put E5 at about 1,670 s from measured unit costs; the run had used at least
   12,247 s when read. A 7.3x gap is not noise. It says the model is missing a term, so the next
   step is a measurement, not a revised model (finding 116).
6. **A measured unit cost carries the conditions it was measured under.** The cost probe's 0.047 s
   per consult included a 0.033 s DNS failure that later grew to 10.04 s (finding 116). Before
   reusing a measured cost, ask which environmental fact it silently depended on.
7. **Re-measure the unchanged revision to separate variance from regression.** Re-running the
   untouched P2 commit read LCP at 3,100 ms, which cleared P3's frontend change (finding 114).
   Readings from 2,292 to 3,100 ms against a 2,500 ms budget mean the budget sits inside the noise.
8. **Measure a threshold's noise before a decision rests on it.** The strict A/A run, one commit's
   effectiveness harness re-run once, gave the operator measured noise for open decision (a)
   instead of an argument about it.
9. **A digest names a tree; only behaviour shows that the tree reproduces.** The B-prime record
   carries a physics digest as a tripwire, while its reproduction re-measures arms E, E' and O and
   compares means with `==`. That equality held in E5's full closure, which installs numpy 1.26.4
   where B-prime ran on 2.4.6 (finding 111). numpy promises no stream stability across versions,
   so only the behavioural check could have shown it.

## 3. Critical thinking: diagnosis, falsification and honest verdicts

10. **Read the evidence before naming a cause, even when a hypothesis has sound arithmetic.** A
    read-only agent's careful estimate blamed logging for E5's overrun. The job log put 99.3% of
    the time on one failed Ollama lookup per decision (finding 116). The wrong hypothesis was
    plausible, and only the log could have settled it.
11. **Charge each timestamp gap to the event that ends it.** One streaming pass over a 556 MB,
    4.4 million-line log attributed the wall-clock to events, and showed a regime change at
    04:01Z that no average would reveal. Use it on any slow run that logs per event.
12. **When a check fires, design the cheapest measurement that tells the explanations apart.** The
    agreement rule reported `harness_mis_measuring` (finding 117). Two explanations remained: the
    harness mis-prices arm O, or two disjoint seed sets differ by chance. Clause (f) priced arm O
    both ways at three seeds and asserted `==`. It passed, so the gap is sampling, about 2.4
    standard errors.
13. **Ask what a guard reduces to under what is already proven.** Once both paths agree per seed,
    a disjoint-seed agreement test can detect only sampling, and fires at its nominal 5% (conflict
    V). A well-formed guard can still be blind to the bias it is named for.
14. **Record a verdict exactly as its rule states it, and put your reading beside it.** R6.4 says
    the harness is then reported as mis-measuring, and it is, with clause (f)'s result beside it.
    Redesigning the rule is the operator's decision. Relabelling a verdict you disagree with is the
    defect this spec exists to remove.
15. **A prediction without data is UNREAD, neither held nor missed.** E5's first run wrote no
    artifact, so its headline prediction was marked UNREAD. Collapsing "no evidence" into either
    verdict corrupts the scorecard (I-7: absence of proof is never a pass).
16. **Tag every claim measured, read or inferred, in the sentence that makes it.** The tags let a
    reader weigh finding 118's cause (inferred) against its timings (measured) without re-reading
    the runs.
17. **A seed-dependent property failure is a real failure.** Stryker's dry run drew a fresh
    fast-check seed and found a `__proto__` counterexample the main test run never drew (finding
    120). A random-seed property test is a probabilistic gate; another job may be the one that
    samples the bug.
18. **When a count surprises you, suspect the counter first.** A per-test regex reported 81 results
    for a file that had 164, because parametrised test ids contain spaces. The corrected regex gave
    the true count before any conclusion was drawn from the wrong one.
19. **Calibrate a negative observation against a known positive.** An unauthenticated 404 for the
    repository meant "private" only after the same tool had fetched a known public repository; the
    run-timing API then showed 0 billable ms for every run that day.

## 4. Systems thinking: couplings and blast radius

20. **Know which files a certificate covers before touching anything.** The Power_Report is valid
    only while `POWER_SOURCE_SET`'s digest is unchanged. Both labelled runs started at the same
    head, so the controls' report described the revision E5 measured. E5's repair was chosen to sit
    outside the digest, an environment variable in `uplift.yml`; a code repair would have voided
    the report and forced the 22-job controls to re-run.
21. **A guarantee in a docstring is not a mechanism.** `uplift/consensus_arm.py:910` says the
    assembly opens no Ollama socket. That held for the orchestrator's client only, not for the
    Disruption Shield's reasoner (finding 116). Walk to the constructor of every component a
    guarantee claims to cover.
22. **Map the side effects of your own actions on shared infrastructure.** Re-running an older run
    of a PR-keyed workflow joined the newer run's concurrency group and cancelled its Stryker job
    (finding 115). Read a workflow's concurrency semantics before re-running or pushing.
23. **Shared mutable fixtures couple tests that look independent.** Starlette's
    `websocket_connect` wrote handshake headers into a module-level dict, and two unrelated nginx
    tests then failed demanding `sec-websocket-key`. A read-only mapping fixed it at the
    declaration, not at the call sites.
24. **State that outlives the call that read it creates races.** A 401 on an anonymous call could
    clear a preview grant that arrived while that call was failing. The repair: a 401 ends only
    the session whose token the failing call sent.
25. **When a harness meets a product defect, make the defect visible instead of absorbing it.** An
    order for an unstocked SKU crashed the twin (finding 113). Letting runs fail would have left
    the contrast incomplete, and fixing only the harness transport would have measured a system
    that does not exist. Classifying the order `untranslatable` keeps it counted and applies
    nothing.
26. **Protect byte-pinned artifacts from line-ending conversion.** The B-prime record and the
    Power_Report are committed unedited with `-text` in `.gitattributes`, so a Windows checkout
    cannot change the bytes their digests pin.

## 5. Forward thinking: sequencing and reversibility

27. **Sequence work so the expensive certificate stays valid.** The order was: commit the claim's
    evidence (P5), re-run E5 at that head, state the claim (P6), and only then allow the code
    repair that voids the Power_Report. Repairing first would have cost a controls re-run and
    blocked the claim.
28. **Write each CI round's predictions down before the push.** Five rounds carried written
    predictions, and their misses (P1 2, P2 1, P3 3, P4 4, P5 2) produced most of the session's
    findings: 105, 106, 113, 114, 115, 116, 117, 118 and 120. A surprise that was never predicted
    in writing is easy to explain away.
29. **Prefer reversible workarounds, and remove them once the cause is fixed.** Every shell command
    failed because the sandbox tried to grant paths that did not exist. Empty placeholder files
    unblocked the work, and were deleted once the operator turned the sandbox off.
30. **Between two honest repairs, choose the stricter.** Refusing metric contract v1 outright was
    stricter than a compatibility path. Classifying an unstocked-SKU order `untranslatable` was
    stricter even in the canonical world, where the order would have added stock that no demand
    reaches (finding 113). The stricter repair is the one that cannot hide a defect.

## 6. Execution: throughput, agents and CI

31. **Count leaves discharged, never authored.** 24 leaves were discharged, each on its naming
    job's own run. Under this metric the fast path and the honest path were the same path.
32. **Dispatch width has a price under usage limits.** Dispatches wider than five finished 4 of 18
    agents, and batches of at most five finished 10 of 14. Under G8's alternating five and three,
    11 of 13 finished, and none was lost to the limit.
33. **Partition agents by coupling closure, under a written contract.** Each contract named the
    files an agent may and may not touch, the one place for its findings, "authoring only", and
    the couplings it owns. Up to five agents worked at once, and no two edited the same file.
34. **Resume a failed agent; never restart it.** Measure its partial work on disk (compile, lint,
    types, fast tests), write a resume note naming what failed, and re-dispatch. A restart repeats
    the work and can overwrite what was already right.
35. **Verify every agent's work independently of its report.** The shared-dict leak in lesson 23
    was found by running tests the agents had only described. A report is a claim about the work,
    not evidence of it.
36. **Review before committing, and reject a review finding only with a primary source.** An
    adversarial review found 13 defects in the login branch. Twelve were fixed; one, NFC against
    NFKC, was rejected by quoting NIST SP 800-63B-4 section 3.1.1.2. Disagreement backed only by
    preference is not a rejection.
37. **CI is the execution substrate; the laptop is for reading and authoring.** Every heavy
    workload ran on free public runners: the controls' 22 jobs, both E5 runs, vitest, Playwright
    and Stryker. Local work stayed at about 4,600 core-seconds, estimated, one process at a time.
38. **Run tests where they will be judged.** Vitest never runs on this laptop. Its first CI run on
    the login branch failed one test, which counted a React scheduler timer next to the hook's
    own. A first CI run is part of verification, not a formality after it.
39. **Make ledger edits mechanical.** Ledger changes went through scripts that refuse an anchor
    found other than exactly once, refuse CRLF, and refuse new lines over 100 characters. The
    guard caught an over-long header line before it was written.
40. **After any timeout or cancellation, sweep for orphaned processes.** A timed-out log download
    left a `gh` and a `python` process holding 640 MB; the sweep found and stopped them.
41. **Read the diff after every edit.** A replacement in `uplift.yml` silently dropped the
    `steps:` header, and reading the diff caught it before any check ran. A replacement must
    contain everything in the old text that you meant to keep.

## 7. Security on a public repository

42. **In a public repository every default is a published credential.** The console signed every
    visitor in as admin, with a password compiled into the bundle (finding 89). A secret lives only
    in server-side configuration the repository never holds, never in a `VITE_` variable, a
    compose default or an example env file.
43. **Open by default can still be least privilege.** Open mode issues a view-only preview grant on
    the public deployment, keeps sign-in built and dormant, and closes every anonymous write. The
    console opens without login, and nothing it can do anonymously changes state.
44. **When the first layer of a fix is configuration, add a second.** Internal-only orchestrator
    routes are denied at nginx and refused again by an edge guard in the service, so a single
    misconfigured proxy cannot reopen them.

## 8. Working with the operator

45. **Surface decisions with evidence and options; never resolve them silently.** Eleven open
    decisions were carried with their findings. Where the main agent made a choice itself, such as
    reorders-only levers for E5, it said so and gave the reason, so the operator could overturn it.
46. **Turn an operator's instruction into a written, testable rule.** "Five agents, then three"
    became G8, with its measured basis, its barrier between batches and the resume procedure. A
    remembered instruction decays; a written one binds the next session.
47. **When the environment fails, find the mechanism from the exact error, then ask.** The sandbox
    error named the path it could not grant. That led to the permissions file, a reversible
    workaround, and a precise question about a setting the operator owns.
48. **Report what is unverified as plainly as what is verified.** Every handoff kept a NOT-verified
    list: CI not yet read, a draft PR's untested code, estimated core-seconds, inferred causes. A
    reader can trust a claim only as far as they can see its limits.

## 9. Taste and judgment in documents

49. **One canonical home per fact; everything else points to it.** Findings live in `tasks.md`,
    design facts in ADRs and repository traps in `CLAUDE.md`. `HANDOFF.md` and the next-session
    prompt carry state and pointers. Two copies of a finding drift apart, and a reader cannot tell
    which one is right.
50. **Correct your own ledger when it is wrong, and say so in the line.** P3's measured block said
    that two failing jobs passed. P5's edit corrected it and recorded the correction in the line
    itself.
51. **Prose is not free.** A finding is written once, where a reader will look for it, and a
    derived document quotes only a headline and points to the rest. A document nobody finishes
    does not govern.
