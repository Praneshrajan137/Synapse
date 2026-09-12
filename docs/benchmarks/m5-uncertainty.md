# M5 Uncertainty track — what this project has actually established

**Feature:** decision-quality-proof, task 19.5. **Requirements:** R8.5–R8.8, R8.12, R8.13, R8.18.

Read this page for one thing: **what has and has not been measured** against the published M5
Uncertainty track. Today the answer is that a comparison has been *set up* and nothing has been
*scored*, and this page says so rather than implying otherwise.

## How this page is maintained

Everything between `<!-- generated:begin -->` and `<!-- generated:end -->` below is **generated**
from the committed record in `infrastructure/ml/training_runs.json`, by
`scripts/audit/benchmark_gen.py`. Do not hand-edit it — the next `--check` will report the drift
and the next `--write` will overwrite it. Everything outside those markers, including this
section, is hand-authored and survives a regeneration byte-for-byte.

```
python -m scripts.audit.benchmark_gen            # == --check; diffs and exits 1 on drift
python -m scripts.audit.benchmark_gen --write    # rewrite the region only
```

The region is a projection rather than a transcription because three of this requirement's
clauses bind **every** document reporting a feed-derived score — R8.8 (an unconfirmed value is
never asserted as fact), R8.12 (the domain gap accompanies every feed-derived claim) and R8.13
(the two domains are described as distinct). A transcribed page satisfies those once, on the day
it is written. A projection satisfies them every time the check runs.

## What this page is not

- **Not a rank.** The recorded result is *not leaderboard-comparable*, which is a different
  statement from a worse position — see the generated section for the named differences.
- **Not a claim about quick-commerce demand.** The feed is daily grocery retail; this system
  serves 10-minute quick-commerce. Those are distinct domains, and the gap is stated below with
  the mechanical evidence for it rather than as an assurance.
- **Not a source for a baseline number.** No published baseline has been confirmed. There is no
  number on this page to quote, and that is deliberate: a plausible figure here would be
  indistinguishable from a confirmed one to every later reader.

<!-- generated:begin -->
## What is recorded

Subject: **comparison as set up (no scoring run has executed)**.

| Field | Value |
|---|---|
| Score | not measured - no scoring run has executed (No scoring run has executed. Model training is a category-4 workload under I-0 and never runs on the dev box; no CI job has produced a full train yet. A null here is the absence of a measurement, not a forgotten field.) |
| Direction | lower-is-better |
| Metric scored | `m5-uncertainty-wspl` -- Weighted Scaled Pinball Loss (WSPL) |
| Metric defined by | `kaggle-m5-forecasting-uncertainty-evaluation` (https://www.kaggle.com/competitions/m5-forecasting-uncertainty/overview/evaluation) |
| Defining document read | NO |
| Split | not-established: no held-out split has been defined for a scoring run, and the published competition's split has not been read from the defining document |
| Aggregation level | not-established: the published competition aggregates over 12 hierarchical levels; which levels a scoring run would report has not been decided, and asserting one here would be a guess |
| Interval family scored | 0.1, 0.5, 0.9 |
| Published baseline | not confirmed - no value recorded |
| Leaderboard comparability | **not-leaderboard-comparable** |
| Rank | none - see comparability |

How the metric identity was obtained: The metric name is carried forward from the note recorded in infrastructure/data/dataset-licences.yaml at task 7.1, which states that the M5 Uncertainty track scores Weighted Scaled Pinball Loss over the 50%, 67%, 95% and 99% intervals. It has NOT been verified against the defining document at the URI above - naming where a document lives is not a claim to have read it. R8.7 requires that limitation to be stated, and this field is where it is stated.

## The published baseline, and why no number appears above

The published baseline is **explicitly unconfirmed**. R8.7 requires that limitation to be stated and R8.8 forbids the value being asserted as fact, so no number is rendered here -- there is none in the record to render.

- **Blocked on:** The numeric M5 leaderboard scores are recorded as UNVERIFIED in this spec's own requirements (.kiro/specs/decision-quality-proof/requirements.md:134: 'the numeric leaderboard scores were NOT verified and MUST be confirmed at implementation time'). Confirming one requires a human to read the published leaderboard; the authoring session had no network access, and inventing a plausible figure would make this gate green while fabricating a fact about somebody else's published result.
- **Limitation:** R8.7: the exact published leaderboard values could not be confirmed at implementation time, so this record states that limitation rather than a number. No comparison to the published field is established, and no generated document may state a baseline value as fact (R8.8).
- **To confirm it:** 1. Open the defining document at metric.defining_document_uri and record the metric definition verbatim, then set metric.defining_document_confirmed to true. 2. Open the competition's public leaderboard, read the baseline score for the SAME metric, and record it as a confirmed baseline: replace this object with {status: confirmed, value: <the number>, source_uri: <the leaderboard URL>, source_title: <the page title>, read_date: <UTC date of the read>, read_by: <who read it>}. 3. Do not record a value read from a blog post, a paper's summary table, or a third-party mirror without recording THAT as the source - the source field is what makes the number checkable.

## Leaderboard comparability (R8.18)

This result is **not leaderboard-comparable**, and that is the honest report rather than a worse position. R8.18: a differing split, aggregation level or metric definition makes a rank a category error dressed as a measurement. The differences, each named:

- Metric definition: THREE DISTINCT INTERVAL FAMILIES are in play. The M5 Uncertainty track scores the 50%, 67%, 95% and 99% intervals (per the note in infrastructure/data/dataset-licences.yaml). This agent's training objective declares quantile_levels [0.1, 0.5, 0.9], an 80% RAW band (agents/demand_prophet/training/rewards.py:31). INV-DP-002 asserts a CONFORMAL-ADJUSTED 90% band at empirical coverage >= 0.85 (agents/demand_prophet/spec.yaml:25-26). A pinball loss over an 80% raw band is not the quantity a weighted scaled pinball loss over 50/67/95/99 measures, and reporting a rank across them would be a category error dressed as a measurement.
- Split: no held-out split has been defined for a scoring run, and the published competition's split has not been read from the defining document, so no like-for-like split exists to compare over.
- Aggregation level: the published competition aggregates over 12 hierarchical levels; which levels a scoring run would report has not been decided.

## The domain gap (R8.12, R8.13)

The Real_Data_Feed's domain and this system's domain are **distinct domains**. Every claim on this page derived from the feed carries that gap.

- **Feed domain:** Daily grocery retail demand: 3,049 products across 10 Walmart stores in 3 US states, one observation per series per day.
- **This system's domain:** 10-minute quick-commerce demand: sub-hourly arrival intensity across a city's dark stores, where the decision horizon is shorter than a single observation of the feed.

R8.12: the Real_Data_Feed and quick-commerce demand are DISTINCT DOMAINS, and every claim derived from the feed carries this gap. A score computed on daily grocery series says nothing directly about 10-minute quick-commerce demand; what transfers is the model's calibration machinery and the shape of its seasonality, not the demand process itself. R8.13: the two are described as distinct domains in every document reporting a feed-derived score, which is why docs/benchmarks/m5-uncertainty.md renders this block rather than paraphrasing it.

**Evidence for the gap, not an assertion of it:** The sharpest available evidence is mechanical rather than rhetorical: data_fabric/ingest/m5.py::intra_day_intensity_shape reports the intra-day intensity shape as UNAVAILABLE and carries no values, because the source's observation columns are daily totals and an hour-of-day shape is not recoverable from daily aggregates by any amount of arithmetic. The feed cannot express the grain the quick-commerce domain operates at. That is the gap, measured by a function that refuses rather than argued in prose.
<!-- generated:end -->

## The expectation this will be judged against

`infrastructure/quality/benchmark-expectations.yaml` records, **before** any score exists, that
a sophisticated model is expected to be *competitive rather than dominant* on point accuracy
(R8.14). `scripts/audit/benchmark_truth.py` checks two things about that record: that its
revision is a **strict** ancestor of the scoring run's, and — with `git show` — that the
prediction as committed at that revision matches the prediction the file carries now. Ancestry
alone would leave an old sha beside a rewritten statement looking like a pre-registration.

## Where the numbers will come from when they exist

`infrastructure/ml/training_runs.json` records where training and scoring executed, with R8.15's
three cost exclusions stated separately — no billable account, no trial linked to a billing
account, no purchased or granted credits. "Free" without those exclusions admits a paid tier, so
`benchmark_truth` derives the zero-cost verdict from the three declared facts and never reads the
record's own summary flag.
