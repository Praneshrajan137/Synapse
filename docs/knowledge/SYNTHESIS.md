# SYNTHESIS - the ten insights that matter most for sessions 2 and 3

> **After session 2 (2026-11-17).** Session 2 tested each reading below against the code. Five
> hold, four were corrected and one stays open; the verdicts, with their evidence, are in
> [`VERDICTS.md`](VERDICTS.md). The largest corrections: the consensus lost by 1.45 after the
> repair of finding 112, not 4.40, and where traced one component made every decision; the
> proof runs on the laptop in minutes, so verification need not wait on CI; and in the twin,
> waste does not depend on any decision. The ten entries themselves still stand as the corpus's
> ranking.

Session 1 read all 242 files in `C:\Documentation` (18 folders, finished 2026-11-15) and
distilled them into 60 ledger entries, 20 tensions, 8 questions for the operator and 61 research
items. This page ranks the ten entries that should most change what the next sessions do. The
evidence for each is in [`LEDGER.md`](LEDGER.md).

**Two cautions.** The readings of SYNAPSE here draw mostly on the `decision-quality-proof`
documents, `CLAUDE.md` and spot measurements. The operator notes that the project is far wider
than those documents, so every reading is provisional until session 2 tests it against the whole
codebase. And every source is a model-written summary of a talk: the ideas are well attested,
the figures are not.

## How the ranking was made

Two measures, as planned in the README. **Convergence:** how many of the 18 folders, and how many
documents, support an entry, counted from `LEDGER.md` on 2026-11-15. **Leverage:** whether the
entry changes the definition of finished, the proof or the scope (high), a design or a process
(medium), or only asks for an audit of something already present (low); this is my judgment.
An entry made late in the reading had fewer folders left to confirm it, so a late entry with a
measured repository fact behind it is ranked on leverage. Related entries sit under the
strongest one.

## The ten

1. **Name the user, the workflow, and what happens after the demo** (INS-018, with INS-017).
   18 of 18 folders, 63 documents: the most repeated idea in the corpus. SYNAPSE has no named
   user (Q-01), so finished cannot yet be defined (Q-03). The ten reviewers of the release will
   ask who this serves. Owed first, by interview as Q-01 now describes.
2. **Earn the complexity against the tuned rule, where the rule breaks** (INS-001, with INS-059).
   Few folders, but this is the project's measured state: on the declared twin's primary,
   unshocked cell the consensus arm cost 4.40 objective units more per 24-hour replicate than
   the tuned control, verdict `baseline_wins`, cause finding 112 (read, `HANDOFF.md`). Session 2
   reads the re-run after the fix (R-01, R-02, R-33) and where the tuned rule loses most to the
   oracle (R-58). If nowhere, the case for eight agents rests on something else (T-001).
3. **Land on one workflow first** (INS-045). 14 folders, 36 documents. Seventy days and ten
   implementation sessions allow replenishment alone, the other agents left as they are until
   it wins (Q-07).
4. **A proof that can fail, against a scorer a practitioner accepts, read by slice** (INS-033,
   with INS-044 and INS-003). 15, 12 and 14 folders. E5 shows the harness can fail, to its
   credit. Still owed: where the objective's weights came from and whether a store manager would
   rank outcomes the same way (R-29), and results by scenario cell and item class (R-38, R-58).
5. **A twin earns belief only when it is realistic and fitted** (INS-031, with INS-060, INS-058
   and INS-055). 11 folders, plus three measured gaps: ten items each demanded equally often,
   one stock number per item with no gap between record and shelf, and no move between stores.
   Each gap removes a case where a policy could win or fail (R-59, R-55, R-53, T-012). Fitting
   it to real data first needs a dataset (R-13).
6. **Grant autonomy by reversibility and blast radius, earned on a shadow record** (INS-009,
   with INS-022). 15 and 12 folders. Escalation is gated on confidence (I-5), and reversibility
   is not named in `orchestrator/` (measured by text search). The corpus gates by what an action
   can break and whether it can be undone, and promotes autonomy on a measured record beside the
   existing rule (R-27, R-32, Q-08). A shadow advisor is the lowest-risk first release.
7. **Operate the twin store yourself with SYNAPSE advising** (INS-035). 13 folders, 40
   documents. It is also a natural shape for the five-day showcase (own reading): a store day
   run in the twin while the ten watch the system advise, give its reasons and be overruled.
8. **Verification is the constraint; give agents a production-like run they can drive**
   (INS-012, with INS-013). 15 and 14 folders. Plan each implementation session around what it
   can verify against a running stack (R-08, R-57).
9. **Deletion is an experiment** (INS-030, with INS-014). 14 folders each. Remove a gate, rule,
   document or agent, rerun the fixed evaluation, and keep it out if nothing measured changes.
   This needs the operator's permission (Q-06, Q-04).
10. **Show what reaches the customer, the reasons, and only what ran** (INS-056, with INS-038
    and INS-034). 7, 15 and 14 folders. The console leads with the system's own activity, while
    customers feel fill rate and stockouts avoided (R-39). An approver must be able to change any
    part of a plan (R-28). Every claim must match what executed; `CLAUDE.md`, possibly out of
    date, says six of eight agents' `execute()` methods still do not act on the world.

## Not in the ten, and why

INS-008 and INS-027 are well supported but describe what SYNAPSE already does; they need an
audit (R-07, R-18), not a decision. INS-039 matters once a user exists. INS-021 and INS-040 are
choices of model, parked until the proof shows a model is needed. INS-020, INS-029 and INS-048
are working habits the house rules already carry.

## What the corpus says against SYNAPSE

- Coordination between agents often costs more than it returns, and teams of agents shrink as
  models improve (T-001).
- The durable asset may be the harness, not the agents. There are now three precedents: a
  simulation-tooling company, a payments fix that became a company, and environments with
  checkers sold to labs (T-004).
- The twin is declared, where the corpus's comparable proofs fit their simulators to real
  history (T-012).
- Much has been built that nobody has yet asked for (T-013).

## The release, as the operator stated it on 2026-11-15

Five days on GCP for ten high-profile people, funded by the untouched $300 trial credit, which
expires in 70 days, about 2027-01-24. By the repository's own cost note the five days cost
roughly $35 to $45 (estimate, not re-priced), so the expiry date, not the balance, is the limit.
The release must start by about 2027-01-19, with twelve sessions before it. During the five days
the VM must not stop daily as it does now (R-61). Q-02 holds the arithmetic.

## Where session 2 starts

With the operator's answers to Q-01, Q-03, Q-06, Q-07 and Q-08, as far as they can be given.
Then the whole project, read first through R-01, R-59, R-55, R-58, R-29 and R-61, testing each
reading of SYNAPSE on this page against the code.
