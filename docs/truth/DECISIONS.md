# DECISIONS - what the operator owes, one memo each

**Status: 2026-11-17.** Each memo states the question, why it is owed now, the options, a
recommendation and what each answer changes. Each can be answered in a line. The evidence is in
[`TRUTH-MAP.md`](TRUTH-MAP.md) (F-nn) and [`LOG.md`](LOG.md) (M-nn, OA-n); the plan they feed is
[`DIRECTION.md`](DIRECTION.md).

Already answered by the operator and not repeated here: the cloud account and spending (Q-02,
LOG OA-1 to OA-3) and the reviewers' frame, the work as a whole (part of Q-03, OA-4).

---

## D-1 Who is the user the release is designed for? (Q-01)

**Why now.** The console's first five minutes (session 8) and the claims on it depend on it.
No user has been named anywhere (the knowledge base's synthesis, reading 1, confirmed in
`docs/knowledge/VERDICTS.md`).

**Options.** (a) A dark-store replenishment planner at a quick-commerce operator; the large
operators build their own systems (FRONTIER 1.3). (b) A smaller dark-store or regional grocery
operator who would buy rather than build. (c) No external user for the release: the reviewers
are the audience, and the product shown is the method.

**Recommendation: (b) as the named persona, shown through (a)'s workflow.** It is the user who
would plausibly adopt a third party's system, and its day is the replenishment day the twin
already models. Before session 8, if the operator can reach one such person, a 30-minute
conversation about what breaks in their replenishment today is worth more than any surface.

**What changes.** (a) or (b): the first screen leads with the store's day (fill rate, waste,
stockouts against the incumbent) and the reason for each order. (c): the first screen leads
with the proof.

**Answer in a line:** "persona (b)", "(a)", or "(c)".

---

## D-2 Does SYNAPSE act, or advise and earn the right to act? (Q-03)

**Why now.** It decides the shape of the decision path (session 7) and what the reviewers are
told the system does.

**Options.** (a) It acts on every decision, as designed. (b) It advises only; a person or the
incumbent rule acts. (c) Incumbent first: the tuned rule acts unless a challenger's action is
shown in the twin, at that state, to beat it and passes the guardrails.

**Recommendation: (c).** The tuned rule beat the consensus (F-13); a withheld decision is a
dead end today (F-08); the twin check already exists (F-06). (c) can never do much worse than
the incumbent, and every action it takes carries its own evidence.

**What changes.** (a) needs the agents to beat the rule first, which the evidence says will not
happen on the measured cell (F-29). (b) is safe but shows little. (c) is sessions 5 and 7.

**Answer in a line:** "(c)", or another letter.

---

## D-3 Is replenishment the one workflow to win first? (Q-07)

**Why now.** It sets what the ten sessions leave out.

**Evidence.** In practice the system already is replenishment alone: every traced decision was
a reorder bound by one component (F-01).

**Recommendation: yes.** Pricing, routing and the rest stay in the repository, labelled with
what they measurably do in this workflow (DIRECTION section 4).

**Answer in a line:** "yes" or "no, also <workflow>".

---

## D-4 What error is acceptable for an autonomous reorder? (Q-08)

**Why now.** Without a number, "autonomy earned" cannot be tested, and the arbiter of D-2 has no
threshold.

**Options.** (a) Per cell: the challenger's executed actions may not raise the objective above
the incumbent's at the upper end of a 95% interval, and fill rate may not fall more than one
point below the incumbent's. (b) Per decision: no autonomous reorder more than twice or less than
half the incumbent's quantity without a person. (c) Both.

**Recommendation: (c),** with (b) as a guardrail at the action boundary, the place the knowledge
base's sources agree a check belongs (T-020).

**What changes.** The guardrail of (b) is a few lines and a test (session 5); (a) is the
pass mark of the proof map (session 7).

**Answer in a line:** "(c)", or the numbers you prefer.

---

## D-5 May a component, gate or document be retired when removing it changes no measured outcome? (Q-06)

**Why now.** The ablation arms of session 7 and the cut list of session 3 need the permission.
The watchdog has never observed the system (F-25) and eight alarms have stood open since July or
November.

**Recommendation: yes, by experiment and in writing.** A component leaves the release path when
a pre-registered ablation shows no change in any cell. A gate is retired when it cannot be made
to fail or tests only what a document says. Nothing is deleted from history: retired code
stays reachable through the archive tags the project already keeps.

**Answer in a line:** "yes" or "no".

---

## D-6 May the sprint history move out of `CLAUDE.md`? (Q-04)

**Why now.** `CLAUDE.md` is 68,472 bytes on `main` and loads into every session; about half is
history (knowledge base INS-014). Several of its statements are out of date (TRUTH-MAP section 4).

**Recommendation: yes,** to `docs/history/`, keeping the rules and the live error patterns, with
the `doc_truth` pins moved in the same change (session 10).

**Answer in a line:** "yes" or "no".

---

## D-7 In what order does the work in flight land, and who merges?

**Why now.** The repair of finding 112 has been open and green since 2026-11-02; session 13 of
the proof spec exists only as uncommitted files; session 1's knowledge base and this session's
record are unpushed (LOG M-07, M-22).

**Recommendation.** In session 4: #87 (the repair), then #91 (the trace, stacked on it), then
#90 (gate defects), then #89 (frontend) once its own checks are green; the `ledger` worktree's
four files committed on their branch with their placeholders filled or marked; then
`docs/knowledge-base` and `docs/truth-session-2` pushed and merged as documents. Merging changes
`main`, so each merge is yours to approve.

**Answer in a line:** "approved", or the order you prefer.

---

## D-8 What runs at the release?

**Options.** (a) The full stack of 23 services and the language model. (b) A thin slice: the
twin, the orchestrator with its agents in-process, the API, the console, Postgres and a TLS
proxy.

**Recommendation: (b).** No command starts (a) anywhere today (F-19); its declared memory alone
nearly fills the largest machine the trial allows (F-22); the agents already run in-process in
the harness. The rest stays in the repository, labelled as not deployed.

**Answer in a line:** "(b)" or "(a)".

---

## D-9 Which changes to the twin come before the next proof?

**Options.** (a) None. (b) Waste that takes stock and depends on age. (c) (b), plus skewed
demand over more items with its shape fitted to FreshRetailNet-50K, a dataset under CC BY 4.0
from a Chinese online grocer (LOG EX-03). (d) (c), plus record inaccuracy as a stress cell.

**Recommendation: (c).** (b) removes the category error an expert would see first (F-30); the
skew gives the item-class slice the proof lacks (F-29). Each change moves the baseline, so the
tuned rule is re-tuned and the controls re-run, which now costs minutes locally (F-14). (d)
waits.

**Answer in a line:** a letter.

---

## D-10 What does the proof claim at the release?

**Why now.** The proof spec's pre-commitments forbid re-running a number until it moves. A new
claim under a new pre-registration is not that, but it is a change of the spec's terms.

**Options.** (a) Keep the single headline on the primary cell. (b) A map pre-registered by cell
(the primary cell, the four adversarial scenarios, the new structures), fitted on one set of
seeds and judged on another, with task 25's and task 31.12's negative claims kept as they stand.

**Recommendation: (b).** On the primary cell no policy without hindsight on record clears the
margin (F-29), so (a) can only report a loss or a tie.

**Answer in a line:** "(b)" or "(a)".

---

## D-11 The cloud: when to spend, and whether to upgrade before the release

**Why now.** The trial's credit lapses three months from the account's start, near the
release's last day, and the provider may end a trial at any time (LOG EX-01).

**Recommendation.** Spend three times: a 24-hour rehearsal in session 9, a 48-hour dress
rehearsal in session 12, and the release, about $70 of machine time in all (DIRECTION section 7).
Before the release, consider upgrading the account to paid: the unused credit stays until the
same date, the eight-core limit lifts, and machines keep running if the trial would otherwise
end; anything beyond the credit is then billed to the card, so a budget alert matters more.
Keep a fallback host: the repository already carries an Oracle Always Free target.

**Answer in a line:** "upgrade before release" or "stay on trial", and whether a fallback host is
wanted.

---

## D-12 Access at the release

**Options.** (a) Public, view-only, as ADR-057 configures the open preview. (b) Sign-in for the
ten reviewers. (c) Public view-only, with sign-in for steering and approvals.

**Recommendation: (c).** Reviewers can look without friction and act only when signed in; the
published default credentials are rotated or removed first (FRONTIER row 16).

**Answer in a line:** a letter.

---

## D-13 Which facts become mechanical, as `CLAUDE.md` requires?

**Why now.** `CLAUDE.md` asks that a load-bearing fact found once be made checkable, so it is not
re-derived. This session was not authorised to edit `CLAUDE.md` or add gates. Candidates:

1. A script that drives the twin's Monte Carlo check on Windows needs a `__main__` guard;
   without it worker processes re-run the script (LOG M-20).
2. The tier router sends any request without its four tier keys to tier 2 (LOG V-01).
3. The live path enacts every proposer's own proposal, not the selected one (LOG V-03).
4. Waste in the twin is a clock that takes no stock (F-30), until D-9 changes it.
5. A local proof check exists: a twelve-replicate miniature of E5 runs in about thirty seconds
   (LOG M-23).
6. One test module needs `python-jose`, which a fresh `.venv` may lack (LOG M-26).

**Recommendation.** Items 1, 2 and 6 as error patterns in `CLAUDE.md`; items 3 and 4 fixed in
code rather than documented (sessions 5 and 6); item 5 wired as a fast check (session 4).

**Answer in a line:** "approved" or the items to drop.
