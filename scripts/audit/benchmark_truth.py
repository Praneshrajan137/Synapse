"""The external benchmark record is honest: metric identity, non-bare baseline, and a
pre-registered expectation at an ancestor revision (R8.5-R8.8, R8.11, R8.14, R8.15, R8.18).

Feature: decision-quality-proof, tasks 19.4, 19.6, 19.7. Design table row `BenchmarkRecord`
(design.md:1642, "a bare number is a violation (R8.6)").

There is no benchmark gate anywhere in the tree before this module, so this is the whole of
the mechanism. It reads two committed artifacts and reports on both:

* ``infrastructure/ml/training_runs.json`` -- where training and scoring executed, with the
  three R8.15 cost exclusions stated as separate declared facts, plus the scored runs and the
  :class:`BenchmarkRecord` each one carries.
* ``infrastructure/quality/benchmark-expectations.yaml`` -- the pre-registered expectation,
  committed at a revision that must be a **strict ancestor** of the scoring run's revision.

Why two artifacts rather than one
---------------------------------

The expectation must be committed *before* the result exists, so it cannot share a file with
the result: a single artifact would be rewritten by the run that it is supposed to predict,
and the ancestry check would compare a revision against itself. R8.14 is the requirement, and
the file split is what makes it enforceable rather than aspirational.

The four shapes this module refuses, each named because each is a way to look green
-----------------------------------------------------------------------------------

1. **A bare baseline number.** R8.6 asks the record to carry the published baseline; R8.8
   forbids an unconfirmed value being asserted as fact. A bare ``baseline: 0.16`` satisfies
   the first and violates the second, so the *type* admits no bare number:
   :class:`ConfirmedBaseline` requires a source, a title, a read date and a reader, and
   :class:`UnconfirmedBaseline` structurally **cannot carry a value at all** -- its ``value``
   field is typed ``None``. There is no third shape, so "write the number and move on" is not
   an available edit. That is the same construction ``ShapeEstimate`` uses to stop an
   ``unavailable`` shape shipping numbers (``data_fabric/ingest/m5.py``).

2. **A rank.** R8.18: a differing split, aggregation level or metric definition makes a result
   **not leaderboard-comparable**, which is a different statement from a worse rank.
   :class:`Comparability` therefore refuses a ``rank`` on any record that declares a
   difference, and refuses ``leaderboard-comparable`` while any difference is declared. Today
   three distinct interval families are declared (see the artifact), so no rank is expressible.

3. **"Free" without the exclusions.** R8.15: "free" that does not exclude a billable account,
   a trial linked to a billing account, and purchased or granted credits admits a paid tier.
   :class:`ExecutionEnvironment` therefore carries the three exclusions as three separate
   required booleans and **derives** ``zero_cost`` from them. The record's own
   ``declared_zero_cost`` flag is never trusted -- it is only ever compared, by
   :meth:`ExecutionEnvironment.flag_disagrees`, exactly as ``DatasetLicence.confirmed`` is
   derived rather than read (``data_fabric/licence.py``). A boolean that can disagree with its
   own subject is a claim, not evidence.

4. **Vacuity.** A record file with no runs in it would let every clause above hold over an
   empty set. ``no-scored-run`` is therefore reported ``unavailable`` -> SKIP, never pass, and
   ``environment-absent`` likewise: R8.14's second half exists precisely because "the criterion
   can no longer be satisfied by never recording a prediction at all".

Ancestry is **strict**, and indeterminate is not a pass
------------------------------------------------------

``git merge-base --is-ancestor X X`` succeeds -- a commit is its own ancestor. R8.14 wants the
prediction committed *before* the result, so :func:`ancestry` requires the two revisions to
differ as well. A prediction landing in the same commit as the result it predicts does not stop
post-hoc rationalisation, which is the whole reason the clause exists.

**Ancestry alone is not enough, and this is the hole it leaves.** An operator can record an old
sha beside a statement rewritten today: ancestry passes, and the prediction was in fact written
after the result. :func:`prediction_at_revision` therefore reads the expectation back out of
history with ``git show <rev>:<path>`` and fails when the prediction there differs from the
prediction the artifact carries now. Ancestry says *when* the sha was committed; that read says
*what the prediction said there*.

When ancestry cannot be decided -- no git, no repository, an unknown revision, or a **shallow
clone** (``actions/checkout`` defaults to ``fetch-depth: 1``, and a depth-1 clone cannot answer
``--is-ancestor`` for an older revision) -- the outcome is ``indeterminate`` -> ``unavailable``
-> SKIP. It is emphatically not a pass: a gate that could not read its input has established
nothing (I-7). A job that wants this row to be decidable must check out enough history, and
the report says so in its own words rather than leaving a silent green.

What this module must never do
------------------------------

It must never invent a leaderboard number. The numeric M5 leaderboard scores are recorded as
**unverified** in this spec's own requirements (requirements.md:134: "the numeric leaderboard
scores were NOT verified and MUST be confirmed at implementation time"). A plausible figure
here would make the gate green, would be indistinguishable from a confirmed value to every
downstream reader, and would be a fabricated fact about somebody else's published result.

Run::

    python -m scripts.audit.benchmark_truth            # human summary
    python -m scripts.audit.benchmark_truth --json     # canonical machine JSON
    python -m scripts.audit.benchmark_truth --check    # exit-code only mode

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable. ``2`` is non-passing.
Every file is read with ``encoding='utf-8'`` (E-S13-07) and all console output is ASCII.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal

import structlog
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:  # importable when run as a bare script
    sys.path.insert(0, str(ROOT))

#: The run record, deliberately beside ``published_checkpoints.json``: both answer "what did
#: this project actually produce", and separating them would invite a reader to check one.
RUN_RECORD_FILE: Final[Path] = ROOT / "infrastructure" / "ml" / "training_runs.json"

#: The pre-registration. In ``infrastructure/quality/`` with the other committed
#: expectation artifacts, and NOT beside the run record, so the run cannot rewrite it.
EXPECTATION_FILE: Final[Path] = (
    ROOT / "infrastructure" / "quality" / "benchmark-expectations.yaml"
)

#: The one schema version each reader understands. An unrecognised version is
#: ``unavailable`` rather than a best-effort parse: a reader that guesses at a shape it does
#: not know reports on a document it did not understand.
SUPPORTED_SCHEMA_VERSION: Final[int] = 1

#: The pre-registration R8.14 requires. The vocabulary carries three members on purpose --
#: a single-member enum would make the field carry no information and the assertion below
#: could not fail. It CAN fail: editing the artifact to ``dominant`` reddens this gate.
PointAccuracyExpectation = Literal["competitive-not-dominant", "dominant", "worse"]

#: The only expectation R8.14 admits, and the reason is a replicated external result rather
#: than a preference: the M-Competitions' finding across four decades is that statistically
#: sophisticated methods do not necessarily beat simpler ones on point accuracy
#: (requirements.md:128-131).
REQUIRED_POINT_ACCURACY: Final[str] = "competitive-not-dominant"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 1
EXIT_UNAVAILABLE: Final[int] = 2

Verdict = Literal["pass", "fail", "unavailable"]
Ancestry = Literal["strict-ancestor", "same-revision", "not-ancestor", "indeterminate"]

_EXIT_CODES: Final[Mapping[str, int]] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}
_SYMBOLS: Final[Mapping[str, str]] = {
    "pass": "[OK]",
    "fail": "[XX]",
    "unavailable": "[--]",
}

#: Rule -> verdict contribution. A table rather than inline branches so the
#: fail-versus-unavailable split is auditable at a glance and cannot drift per call site.
#: The split is the same one ``dataset_licence_truth`` makes: ``unavailable`` is "nobody
#: established this", ``fail`` is "this tree makes a false statement about itself".
_RULE_VERDICTS: Final[Mapping[str, Verdict]] = {
    # Nobody established it. Different repair, different person, never a pass.
    "run-record-absent": "unavailable",
    "run-record-unparseable": "unavailable",
    "schema-version-unrecognised": "unavailable",
    "expectation-absent": "unavailable",
    "expectation-unparseable": "unavailable",
    "expectation-revision-unrecorded": "unavailable",
    "environment-absent": "unavailable",
    "no-scored-run": "unavailable",
    "comparison-absent": "unavailable",
    "baseline-unconfirmed": "unavailable",
    "ancestry-indeterminate": "unavailable",
    # This tree wrote something that contradicts itself or its requirement.
    "schema-invalid": "fail",
    "rank-without-comparability": "fail",
    "comparability-overclaimed": "fail",
    "metric-identity-incomplete": "fail",
    "domain-gap-absent": "fail",
    "cost-exclusion-unmet": "fail",
    "zero-cost-overclaimed": "fail",
    "expectation-not-competitive": "fail",
    "expectation-not-ancestor": "fail",
    "expectation-same-revision": "fail",
    "expectation-mutated": "fail",
    "dependency-introduced": "fail",
}

_LOG = structlog.get_logger(__name__)

__all__ = [
    "EXIT_FAIL",
    "EXIT_PASS",
    "EXIT_UNAVAILABLE",
    "EXPECTATION_FILE",
    "REQUIRED_POINT_ACCURACY",
    "ROOT",
    "RUN_RECORD_FILE",
    "SUPPORTED_SCHEMA_VERSION",
    "Ancestry",
    "BenchmarkFinding",
    "BenchmarkRecord",
    "BenchmarkTruthReport",
    "Comparability",
    "ConfirmedBaseline",
    "DomainGap",
    "ExecutionEnvironment",
    "ExpectationFile",
    "ExpectedOutcome",
    "MetricIdentity",
    "PointAccuracyExpectation",
    "RunRecordFile",
    "TrainingRun",
    "UnconfirmedBaseline",
    "Verdict",
    "ancestry",
    "assess",
    "evaluate_record",
    "main",
    "prediction_at_revision",
    "run",
    "strip_comment_keys",
]


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _ascii(text: str) -> str:
    """Escape non-ASCII for the Windows console (ASCII-only output contract)."""
    return text if text.isascii() else text.encode("unicode_escape").decode("ascii")


def _first_line(text: str | None, *, fallback: str = "(none recorded)") -> str:
    """The first non-empty line of ``text``, or ``fallback``.

    Exists because :func:`assess` promises never to raise and ``"  ".strip().splitlines()[0]``
    is an ``IndexError``. A whitespace-only field in a committed artifact is a small thing to
    get wrong, and a gate that crashes reports nothing at all -- which is not a pass either.
    """
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return fallback


# ---------------------------------------------------------------------------
# The recorded facts
# ---------------------------------------------------------------------------


class MetricIdentity(BaseModel):
    """Which quantity was scored, and which published document defines it (R8.5).

    R8.5's reason is quoted in the requirement itself: "the Uncertainty-track metric" names
    no single computable quantity on its own. So a score is meaningless without three
    identifiers -- the metric, the document that defines it, and the split and aggregation
    level the score was computed over -- and all four fields here are required.

    ``defining_document_confirmed`` is separate from the document's identifier on purpose,
    and it is the same distinction the licence register makes: **naming where a document
    lives is not a claim to have read it.** A ``false`` here says the metric name below was
    carried forward from a recorded note rather than verified against the defining document,
    which is a limitation R8.7 requires the record to state rather than hide.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str
    metric_name: str
    defining_document_id: str
    defining_document_uri: str
    defining_document_confirmed: bool
    #: How the metric name above was obtained. Required even when confirmed, so the record
    #: states *how* it knows rather than only *that* it knows.
    provenance: str
    split_id: str
    aggregation_level: str
    #: The interval family the score covers, as declared. Empty is admitted (a point metric);
    #: what is not admitted is silence about which family, which is why the key is required.
    quantile_levels: tuple[float, ...]

    @property
    def incomplete_identifiers(self) -> tuple[str, ...]:
        """Identifier fields that are present but blank, in declaration order.

        A required-but-empty string is the loophole a ``required`` list alone leaves open:
        ``metric_id: ""`` satisfies the model and identifies nothing. Named rather than
        counted, so the report tells a reader which identifier to go and fill in.
        """
        named = (
            "metric_id",
            "metric_name",
            "defining_document_id",
            "defining_document_uri",
            "provenance",
            "split_id",
            "aggregation_level",
        )
        return tuple(name for name in named if not str(getattr(self, name)).strip())


class ConfirmedBaseline(BaseModel):
    """A published baseline somebody actually read, with the provenance to prove it (R8.6).

    Every field is required, and that is the whole point: this is the *only* shape in which a
    number may be recorded, so a number cannot arrive without a source, a title, a read date
    and a named reader. R8.6's "confirmed value with its source and read date" is implemented
    as a type rather than as a convention, because a convention is what a hurried edit skips.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["confirmed"]
    value: float
    source_uri: str
    source_title: str
    read_date: str
    read_by: str

    @property
    def confirmed(self) -> bool:
        """True. Present so callers need not branch on the tag to ask the question."""
        return True

    @property
    def renderable_value(self) -> float | None:
        """The number a generated document may state as fact (R8.8). Always present here."""
        return self.value


class UnconfirmedBaseline(BaseModel):
    """An explicitly unconfirmed baseline, which **cannot carry a number** (R8.6-R8.8).

    ``value`` is typed ``None`` rather than ``float | None``. That is the load-bearing line
    in this module: an unconfirmed entry is not a confirmed entry with a missing field, it is
    a different fact, and Pydantic refuses ``value: 0.16`` here at construction. R8.8's "shall
    not be asserted as fact in any generated document" then holds by construction rather than
    by the generator remembering -- :attr:`renderable_value` is ``None``, so there is nothing
    for a renderer to print even if it tried.

    ``limitation`` is R8.7 in one field: "IF the exact published leaderboard values cannot be
    confirmed at implementation time, THEN the recorded comparison SHALL state that
    limitation." Required, so the limitation cannot be omitted while the entry still parses.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["unconfirmed"]
    value: None = None
    #: What stops the confirmation being obtained mechanically. Stops a null reading as a
    #: mystery rather than as a task.
    blocked_on: str
    #: What an operator must do to turn this into a :class:`ConfirmedBaseline`.
    procedure: str
    #: The limitation the comparison states (R8.7).
    limitation: str

    @property
    def confirmed(self) -> bool:
        return False

    @property
    def renderable_value(self) -> None:
        """``None`` -- there is no number here to render as fact (R8.8)."""
        return None


class Comparability(BaseModel):
    """Whether this result may be compared to the published leaderboard at all (R8.18).

    R8.18 draws a line a rank cannot express: if the split, the aggregation level or the
    metric definition differs from the published competition's, the honest report is **not
    leaderboard-comparable**, not a worse position. A rank against a different quantity is a
    category error dressed as a measurement.

    The validator below enforces both directions, which is what makes the field mean
    something: a declared difference forbids both ``leaderboard-comparable`` and a ``rank``,
    and claiming comparability while naming a difference is refused rather than reconciled.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["leaderboard-comparable", "not-leaderboard-comparable"]
    #: Every declared difference from the published competition's setup, named. Non-empty
    #: means not comparable; empty plus ``leaderboard-comparable`` is the only comparable
    #: shape, and it still requires a confirmed baseline before a rank is admitted.
    differences: tuple[str, ...]
    rank: int | None = None

    @model_validator(mode="after")
    def _rank_requires_comparability(self) -> Comparability:
        if self.differences and self.status == "leaderboard-comparable":
            raise ValueError(
                "a record naming "
                f"{len(self.differences)} difference(s) from the published competition "
                "cannot also declare itself leaderboard-comparable (R8.18): "
                + "; ".join(self.differences)
            )
        if self.rank is not None and self.status != "leaderboard-comparable":
            raise ValueError(
                "a not-leaderboard-comparable result carries no rank (R8.18): a rank "
                "against a differently-defined quantity is a category error dressed as a "
                "measurement"
            )
        if not self.differences and self.status == "not-leaderboard-comparable":
            raise ValueError(
                "not-leaderboard-comparable must NAME the difference that makes it so; an "
                "unexplained incomparability is indistinguishable from an excuse"
            )
        return self

    @property
    def comparable(self) -> bool:
        return self.status == "leaderboard-comparable"


class DomainGap(BaseModel):
    """The documented gap between the feed's domain and this system's (R8.12, R8.13).

    R8.13 requires the two to be described as **distinct domains** in every document that
    reports a feed-derived score, so ``distinct_domains`` is required and a ``false`` is
    refused at construction. That looks like a field with one admissible value, and it is --
    but the alternative is worse: an optional flag defaulting to ``true`` would let a record
    omit the statement and still render, which is the exact defaulting R8.1's sibling clause
    forbids. Refusing ``false`` makes the claim unavoidable rather than unfalsifiable; what
    can fail is the *presence* of the block, which :func:`evaluate_record` reports.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    feed_domain: str
    system_domain: str
    distinct_domains: bool
    #: The gap in the domain's own words, rendered beside every feed-derived claim (R8.12).
    statement: str
    #: The sharpest single piece of evidence for the gap, so the statement is not an
    #: assertion. ``data_fabric/ingest/m5.py``'s intra-day shape reports ``unavailable``
    #: because daily aggregates cannot yield an hour-of-day curve -- that is the evidence.
    evidence: str

    @model_validator(mode="after")
    def _domains_are_distinct(self) -> DomainGap:
        if not self.distinct_domains:
            raise ValueError(
                "R8.13 requires the Real_Data_Feed's domain and quick-commerce demand to be "
                "described as DISTINCT domains in every document reporting a feed-derived "
                "score; a record declaring them non-distinct cannot satisfy it"
            )
        if not self.statement.strip() or not self.evidence.strip():
            raise ValueError(
                "the domain gap needs both a statement (R8.12) and the evidence for it; an "
                "unevidenced gap statement is an assertion, not a documented gap"
            )
        return self


class BenchmarkRecord(BaseModel):
    """One score, with everything that makes it interpretable (R8.5-R8.8, R8.12, R8.18).

    ``score`` is ``float | None``. ``None`` is not a placeholder for a number somebody forgot:
    it is "no scoring run has produced a value", which is the honest state of this repository
    until a training run lands, and it is reported ``unavailable`` -> SKIP rather than pass.
    A record whose score is ``None`` still carries a full metric identity, baseline entry,
    comparability statement and domain gap, because those are properties of the *comparison
    being set up* and are checkable before any number exists. That is what stops this gate
    being unavailable-by-construction until the largest block of work in the spec completes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: float | None
    #: Why ``score`` is null, required when it is. A null with no reason is indistinguishable
    #: from a dropped field.
    score_absent_reason: str | None = None
    metric: MetricIdentity
    baseline: ConfirmedBaseline | UnconfirmedBaseline
    comparability: Comparability
    domain_gap: DomainGap
    #: Lower-is-better for pinball/CRPS-family metrics, higher-is-better for coverage. Which
    #: one is required, because "better" is not derivable from a number alone.
    direction: Literal["lower-is-better", "higher-is-better"]

    @model_validator(mode="after")
    def _absent_score_states_why(self) -> BenchmarkRecord:
        if self.score is None and not (self.score_absent_reason or "").strip():
            raise ValueError(
                "score is null with no score_absent_reason: a null that does not say why is "
                "indistinguishable from a field somebody dropped (I-7)"
            )
        if self.score is not None and (self.score_absent_reason or "").strip():
            raise ValueError(
                "score_absent_reason is set beside a present score; the record would be "
                "explaining the absence of a value it carries"
            )
        return self

    @property
    def scored(self) -> bool:
        """Whether a scoring run has actually produced a value."""
        return self.score is not None

    def canonical_json(self) -> str:
        """Canonical JSON: ``sort_keys=True``, no whitespace. Stable across runs."""
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )


class ExecutionEnvironment(BaseModel):
    """Where training and scoring executed, with the three R8.15 exclusions (R8.11, R8.15).

    **The three exclusions are three fields, not one word.** R8.15 says so in its own reason:
    "free" without them admits a paid tier. A free trial on a hyperscaler requires a card, a
    grant of credits is a purchase somebody else made, and both are routinely described as
    "free". So the record states each separately, :attr:`zero_cost` is **derived** from all
    three, and ``declared_zero_cost`` is only ever compared against the derivation by
    :meth:`flag_disagrees` -- never read. This is ``DatasetLicence.confirmed``'s construction
    reused, for the same reason: a boolean that can disagree with its own subject is a claim.

    ``new_dependencies`` carries R8.11 (I-1). The requirement is that training introduces no
    paid API, SDK, dependency or host; task 19.7 adds none, and the honest way to record that
    is an explicitly empty tuple beside a note on where the prohibition is enforced -- rather
    than silence, which is indistinguishable from nobody having checked.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    environment_id: str
    locus: Literal["ci-pipeline", "external-gpu-no-billing"]
    detail: str
    #: The three R8.15 exclusions. Each is a claim about the environment that a reader can
    #: check against the provider's own terms, which is why each is separate and named.
    billable_account_required: bool
    trial_linked_to_billing_required: bool
    purchased_or_granted_credits_used: bool
    #: The record's own summary claim. Never trusted; see :meth:`flag_disagrees`.
    declared_zero_cost: bool
    #: How the three exclusions above were established, so the record says how it knows.
    cost_basis: str
    #: Paid APIs, SDKs, dependencies or hosts this environment introduces (R8.11, I-1).
    #: Empty is the only value CI admits, and it is stated rather than assumed.
    new_dependencies: tuple[str, ...] = ()
    dependency_basis: str

    @property
    def unmet_exclusions(self) -> tuple[str, ...]:
        """Which of R8.15's three exclusions do **not** hold, by name.

        This is the whole of the zero-cost rule, and it is derived from the three declared
        facts rather than read from the summary flag. Named rather than counted: "one
        exclusion unmet" tells a reader to go looking, "purchased_or_granted_credits_used"
        tells them what to fix.
        """
        unmet: list[str] = []
        if self.billable_account_required:
            unmet.append("billable_account_required")
        if self.trial_linked_to_billing_required:
            unmet.append("trial_linked_to_billing_required")
        if self.purchased_or_granted_credits_used:
            unmet.append("purchased_or_granted_credits_used")
        return tuple(unmet)

    @property
    def zero_cost(self) -> bool:
        """True only when all three exclusions hold. **Derived, never read.**"""
        return not self.unmet_exclusions

    def flag_disagrees(self) -> bool:
        """True when ``declared_zero_cost`` claims more than the three exclusions support.

        Asymmetric on purpose, exactly as ``DatasetLicence.flag_disagrees`` is: over-claiming
        (``declared_zero_cost: true`` beside an unmet exclusion) is a false self-statement and
        a FAIL. Under-claiming (all three exclusions hold, flag still false) is an operator
        being cautious about somebody else's billing terms, and failing that would punish the
        honest half of the work.
        """
        return self.declared_zero_cost and bool(self.unmet_exclusions)


class TrainingRun(BaseModel):
    """One training-and-scoring run: where it executed, at which revision, and what it scored."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    #: The revision the scoring run was executed at. R8.14's ancestry is checked against this.
    revision: str
    executed_at: str
    environment_id: str
    #: ``None`` while the run is declared but has not produced a benchmark record.
    benchmark: BenchmarkRecord | None = None


class RunRecordFile(BaseModel):
    """The whole run record. ``environments`` is non-empty by this reader's rule.

    ``runs`` **may** be empty, and that is deliberate: no training run has executed yet, and
    a schema forbidding the empty list would force a fabricated run to make the file parse.
    The emptiness is reported as ``no-scored-run`` -> ``unavailable``, which is the honest
    reading -- and never as a pass, because every clause in this module would hold vacuously
    over an empty list. That is the vacuity R8.14's second half exists to close.

    **``comparison_setup`` is why this gate does real work before any run exists.** A metric
    identity, a baseline entry, a comparability disposition and a domain gap are properties of
    the *comparison being set up*, not of a number, so they are recordable and checkable today.
    Without this field every R8.5-R8.8, R8.12, R8.13 and R8.18 clause would be
    unavailable-by-construction until the largest block of work in the spec completed, and a
    gate that cannot fail until then is not yet a gate. It carries ``score: null`` with a
    stated reason; it is **not** a run, and it is deliberately not in ``runs``, because a
    record of a run that never happened is the fabrication I-7 forbids.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int
    environments: tuple[ExecutionEnvironment, ...]
    runs: tuple[TrainingRun, ...]
    comparison_setup: BenchmarkRecord | None = None
    notes: tuple[str, ...] = ()

    def environment(self, environment_id: str) -> ExecutionEnvironment | None:
        """The declared environment with this id, or ``None``. Never raises on a miss."""
        for candidate in self.environments:
            if candidate.environment_id == environment_id:
                return candidate
        return None

    def renderable_record(self) -> tuple[BenchmarkRecord | None, str]:
        """The record a document should describe, and the label for what it is.

        A scored run outranks the setup: once a number exists, the document reports the
        number. Until then it reports the comparison as set up, labelled as such, so a reader
        cannot mistake a configured comparison for a measured result (R8.7, R8.8).
        """
        for candidate in self.runs:
            if candidate.benchmark is not None and candidate.benchmark.scored:
                return candidate.benchmark, f"scored run {candidate.run_id}"
        if self.comparison_setup is not None:
            return self.comparison_setup, "comparison as set up (no scoring run has executed)"
        return None, "nothing recorded"


class ExpectedOutcome(BaseModel):
    """The pre-registered expectation, and the revision it was committed at (R8.14).

    ``falsifier`` is required. An expectation that names nothing which would prove it wrong is
    an opinion, and R8.14's purpose -- "so the result cannot be rationalised after the fact"
    -- is not served by a prediction that no outcome could contradict.

    **``revision`` is nullable, and that is not a loophole.** The commit sha this record lands
    at does not exist while the record is being written, so requiring it here would force a
    fabricated value into the artifact to make it parse -- the exact trade I-7 forbids. A null
    is a positive assertion that the revision has not been recorded yet; it yields
    ``expectation-revision-unrecorded`` -> ``unavailable`` -> SKIP, never a pass, and
    ``revision_procedure`` is required so the null reads as a task rather than a mystery.
    This is ``DatasetLicence``'s required-but-nullable construction reused.

    Recording the sha later cannot be used to backdate a prediction, because
    :func:`prediction_at_revision` reads this file *as it existed at that revision* and fails
    when the prediction there differs from the prediction here. Ancestry alone would leave the
    hole open: an old sha beside a rewritten statement satisfies ancestry and predicts nothing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    expectation_id: str
    #: The revision this record was committed at. Must be a STRICT ancestor of the run's.
    #: ``None`` until an operator records it; see the class docstring.
    revision: str | None = None
    #: How the revision above is obtained. Required even when the revision is recorded, so
    #: the record states how it knows rather than only that it knows.
    revision_procedure: str
    recorded_at: str
    point_accuracy: PointAccuracyExpectation
    statement: str
    falsifier: str
    basis: str

    @model_validator(mode="after")
    def _null_revision_names_its_procedure(self) -> ExpectedOutcome:
        if not self.revision_procedure.strip():
            raise ValueError(
                "revision_procedure is required: a null revision with no procedure is "
                "indistinguishable from a field somebody dropped, and a recorded one with no "
                "procedure does not say how it was obtained"
            )
        if not self.falsifier.strip():
            raise ValueError(
                "an expectation that names nothing which would prove it wrong is an opinion, "
                "and R8.14 exists so a result cannot be rationalised after the fact"
            )
        return self


class ExpectationFile(BaseModel):
    """The pre-registration document. Non-empty, because an empty one predicts nothing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int
    expectations: tuple[ExpectedOutcome, ...]
    notes: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Findings and the report
# ---------------------------------------------------------------------------


class BenchmarkFinding(BaseModel):
    """One finding, naming its rule, its requirement and the subject it is about."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    subject: str
    detail: str

    @property
    def verdict_contribution(self) -> Verdict:
        return _RULE_VERDICTS.get(self.rule, "fail")

    @property
    def fatal(self) -> bool:
        """True for somebody's **defect**, false for an **absence**.

        The distinction a reader acts on: a fatal finding is fixable in the change that
        introduced it, while a non-fatal one is work for somebody else entirely ("go and read
        the published document"). Both are non-passing.
        """
        return self.verdict_contribution == "fail"


class BenchmarkTruthReport(BaseModel):
    """Everything one execution of this gate observed."""

    model_config = ConfigDict(frozen=True)

    run_record_path: str
    expectation_path: str
    run_record_present: bool
    expectation_present: bool
    environments_declared: int
    runs_declared: int
    scored_runs: int
    #: ``(run_id, ancestry)`` per run whose ancestry was examined.
    ancestry_by_run: tuple[tuple[str, Ancestry], ...]
    #: ``(run_id, comparability status)``, so a reader sees the R8.18 disposition at a glance.
    comparability_by_run: tuple[tuple[str, str], ...]
    baseline_confirmed_runs: tuple[str, ...]
    baseline_unconfirmed_runs: tuple[str, ...]
    findings: tuple[BenchmarkFinding, ...]
    notes: tuple[str, ...]
    verdict: Verdict
    reason: str

    @property
    def exit_code(self) -> int:
        return _EXIT_CODES[self.verdict]

    @property
    def passing(self) -> bool:
        """``unavailable`` is not a pass (I-7)."""
        return self.verdict == "pass"


def _verdict_of(findings: tuple[BenchmarkFinding, ...]) -> Verdict:
    """``fail`` outranks ``unavailable`` outranks ``pass``.

    A false self-statement is a worse fact than an unread published document, and reporting
    the milder of the two when both hold would understate the defect.
    """
    contributions = {finding.verdict_contribution for finding in findings}
    if "fail" in contributions:
        return "fail"
    if "unavailable" in contributions:
        return "unavailable"
    return "pass"


# ---------------------------------------------------------------------------
# Ancestry (R8.14)
# ---------------------------------------------------------------------------


def ancestry(
    expectation_revision: str, run_revision: str, *, repo: Path = ROOT
) -> tuple[Ancestry, str]:
    """Whether ``expectation_revision`` is a **strict** ancestor of ``run_revision``.

    Four outcomes, and the fourth is the one that matters:

    * ``strict-ancestor`` -- the prediction was committed before the result. R8.14 satisfied.
    * ``same-revision`` -- both landed in one commit. ``git merge-base --is-ancestor X X``
      returns success, so a non-strict check would pass here; a prediction committed in the
      same change as the result it predicts does not stop post-hoc rationalisation, which is
      the entire reason R8.14 exists. Reported separately and failed.
    * ``not-ancestor`` -- the prediction is not in the run's history at all.
    * ``indeterminate`` -- git is absent, the directory is not a repository, a revision is
      unknown, or the clone is **shallow**. ``actions/checkout`` defaults to
      ``fetch-depth: 1``, and a depth-1 clone genuinely cannot answer this question for an
      older revision. That is ``unavailable`` -> SKIP: the check has established nothing, and
      a job that wants a decision must fetch enough history.

    Returns ``(outcome, detail)``. Never raises: a gate that crashes reports nothing, which
    is not a pass either.
    """
    if not expectation_revision.strip() or not run_revision.strip():
        return "indeterminate", "one of the two revisions is blank"
    if expectation_revision == run_revision:
        return (
            "same-revision",
            f"the expectation and the scoring run share revision {run_revision}",
        )
    try:
        probe = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "merge-base", "--is-ancestor", expectation_revision, run_revision],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return "indeterminate", f"git could not be executed: {_ascii(str(error))}"

    if probe.returncode == 0:
        return (
            "strict-ancestor",
            f"{expectation_revision} is an ancestor of {run_revision} and differs from it",
        )
    if probe.returncode == 1:
        return (
            "not-ancestor",
            f"{expectation_revision} is not in the history of {run_revision}",
        )
    # Any other code means git could not decide - an unknown revision, a shallow clone, or
    # not a repository. Distinguished from `not-ancestor` because the repairs differ: one is
    # "commit the prediction earlier", the other is "fetch more history".
    stderr = _ascii(probe.stderr.strip().replace("\n", "; ")) or "no stderr"
    return (
        "indeterminate",
        f"git exited {probe.returncode} rather than deciding ancestry ({stderr}); a shallow "
        "clone cannot answer this, and an undecided ancestry is not a satisfied one",
    )


def prediction_at_revision(
    revision: str,
    expectation_id: str,
    *,
    path: Path = EXPECTATION_FILE,
    repo: Path = ROOT,
) -> tuple[str | None, str]:
    """The ``point_accuracy`` this expectation recorded **at** ``revision``, or ``None``.

    Ancestry alone does not close R8.14. An operator can record an old sha beside a statement
    rewritten today: the ancestry check passes, and the "prediction" was in fact written after
    the result. So the prediction is read back out of history with ``git show`` and compared to
    the prediction the artifact carries now.

    Returns ``(point_accuracy_at_revision, detail)``. ``None`` means the question could not be
    answered -- git absent, revision unknown, shallow clone, or the file did not exist at that
    revision -- which is ``unavailable``, never a pass. Never raises.
    """
    try:
        relative = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return None, f"{path.as_posix()} is outside {repo.as_posix()}, so history is unreadable"
    try:
        shown = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "show", f"{revision}:{relative}"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"git show could not be executed: {_ascii(str(error))}"
    if shown.returncode != 0:
        stderr = _ascii(shown.stderr.strip().replace("\n", "; ")) or "no stderr"
        return None, (
            f"{relative} could not be read at {revision} (git exited {shown.returncode}: "
            f"{stderr}); a shallow clone cannot answer this"
        )
    try:
        historic = yaml.safe_load(shown.stdout)
    except yaml.YAMLError as error:
        return None, f"{relative} at {revision} is not parseable YAML: {_ascii(str(error))}"
    if not isinstance(historic, Mapping):
        return None, f"{relative} at {revision} does not contain a mapping"
    entries = historic.get("expectations")
    if not isinstance(entries, list):
        return None, f"{relative} at {revision} declares no expectations list"
    for entry in entries:
        if isinstance(entry, Mapping) and entry.get("expectation_id") == expectation_id:
            recorded = entry.get("point_accuracy")
            if isinstance(recorded, str):
                return recorded, f"{expectation_id} recorded {recorded!r} at {revision}"
            return None, (
                f"{expectation_id} at {revision} carries a non-string point_accuracy "
                f"({type(recorded).__name__})"
            )
    return None, f"{relative} at {revision} declares no expectation {expectation_id!r}"


# ---------------------------------------------------------------------------
# Per-record evaluation
# ---------------------------------------------------------------------------


def evaluate_record(record: BenchmarkRecord, subject: str) -> tuple[BenchmarkFinding, ...]:
    """Findings for one :class:`BenchmarkRecord`. Pure: no file IO, no subprocess.

    Pure so the property test for Property 73 can drive every branch at the profile's example
    budget without touching disk or git (I-0). The structural clauses -- no bare number, no
    rank without comparability, no non-distinct domains -- are enforced by the *types* and so
    cannot be reached here at all; what this function adds is the reporting for the states the
    types legitimately admit.

    **Not being leaderboard-comparable is not a finding.** R8.18 makes incomparability the
    honest report rather than a defect, so it is carried in the report's notes and in
    ``comparability_by_run``. What fails is a *rank* recorded beside it, or comparability
    claimed while the baseline is unconfirmed. A later reader tempted to "complete" this
    function by failing incomparability would turn honesty into a red gate, which is the
    incentive this project exists to remove.
    """
    findings: list[BenchmarkFinding] = []

    incomplete = record.metric.incomplete_identifiers
    if incomplete:
        findings.append(
            BenchmarkFinding(
                rule="metric-identity-incomplete",
                requirement="R8.5",
                subject=subject,
                detail=(
                    f"{len(incomplete)} metric identifier(s) are blank: "
                    f"{', '.join(incomplete)}. A score without the identity of the metric and "
                    "of the document defining it names no computable quantity"
                ),
            )
        )

    # Narrowed by `isinstance` rather than by `assert` or a `# type: ignore`: the dependency
    # on the union tag is then visible at the point that relies on it, and if a third baseline
    # shape is ever added this branch reports the absence rather than raising inside it.
    if isinstance(record.baseline, UnconfirmedBaseline):
        findings.append(
            BenchmarkFinding(
                rule="baseline-unconfirmed",
                requirement="R8.6, R8.7, R8.8",
                subject=subject,
                detail=(
                    "the published baseline is explicitly unconfirmed, so no comparison to it "
                    "is established and no generated document may state it as fact. Blocked "
                    f"on: {_first_line(record.baseline.blocked_on)}"
                ),
            )
        )

    if record.comparability.rank is not None and not record.comparability.comparable:
        # Unreachable through the model, which refuses this pair at construction. Kept because
        # a record can also be built field-by-field by a future caller that bypasses
        # validation (`model_construct`), and a guard that only holds while nobody makes a
        # mistake is not a guard.
        findings.append(
            BenchmarkFinding(
                rule="rank-without-comparability",
                requirement="R8.18",
                subject=subject,
                detail=(
                    "a rank is recorded on a result that is not leaderboard-comparable; R8.18 "
                    "requires the incomparability to be reported INSTEAD of a rank"
                ),
            )
        )

    if record.comparability.comparable and not record.baseline.confirmed:
        findings.append(
            BenchmarkFinding(
                rule="comparability-overclaimed",
                requirement="R8.6, R8.18",
                subject=subject,
                detail=(
                    "the record claims to be leaderboard-comparable while the published "
                    "baseline is unconfirmed; comparability to a value nobody has read is a "
                    "claim about a number that does not exist in this tree yet"
                ),
            )
        )

    return tuple(findings)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> tuple[object | None, str | None]:
    """``(payload, error)``. ``encoding='utf-8'`` (E-S13-07)."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, _ascii(str(error))


def _read_yaml(path: Path) -> tuple[object | None, str | None]:
    """``(payload, error)``. ``encoding='utf-8'`` (E-S13-07)."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        return None, _ascii(str(error))


def strip_comment_keys(payload: Mapping[str, object]) -> dict[str, object]:
    """Drop top-level keys beginning with ``$``, which JSON has no comment syntax for.

    ``infrastructure/quality/ratchets.json`` already carries a ``$note_on_absent_siblings``
    key for the same reason, so this is the repository's existing convention rather than a new
    one. Applied **only at the top level and only to a ``$`` prefix**, so the models keep
    ``extra='forbid'``: a mistyped real field such as ``enviroments`` still fails validation
    naming itself, which is what would be lost by widening to ``extra='allow'``.
    """
    return {key: value for key, value in payload.items() if not key.startswith("$")}


def _blank_report(
    run_rel: str,
    expectation_rel: str,
    findings: tuple[BenchmarkFinding, ...],
    reason: str,
    *,
    run_record_present: bool = True,
    expectation_present: bool = False,
) -> BenchmarkTruthReport:
    """A report for a state reached before anything could be counted."""
    return BenchmarkTruthReport(
        run_record_path=run_rel,
        expectation_path=expectation_rel,
        run_record_present=run_record_present,
        expectation_present=expectation_present,
        environments_declared=0,
        runs_declared=0,
        scored_runs=0,
        ancestry_by_run=(),
        comparability_by_run=(),
        baseline_confirmed_runs=(),
        baseline_unconfirmed_runs=(),
        findings=findings,
        notes=(),
        verdict=_verdict_of(findings),
        reason=reason,
    )


def load_run_record(
    path: Path = RUN_RECORD_FILE, expectation_path: Path = EXPECTATION_FILE
) -> RunRecordFile | BenchmarkTruthReport:
    """The parsed run record, or the final report for a state that stopped the read.

    A union return rather than a ``(value, error)`` pair: the two outcomes are mutually
    exclusive, and a pair forces the success path to construct a report it then discards --
    which is the shape that eventually gets returned by accident.

    Public because ``benchmark_gen`` needs the record itself, not a verdict over it, and a
    second reader in the generator would be a second thing to drift.
    """
    run_rel = _relative(path)
    expectation_rel = _relative(expectation_path)
    if not path.is_file():
        return _blank_report(
            run_rel,
            expectation_rel,
            (
                BenchmarkFinding(
                    rule="run-record-absent",
                    requirement="R8.15",
                    subject=run_rel,
                    detail=(
                        "no run record exists, so nothing states where training or scoring "
                        "executed; an absent record is not a zero-cost one"
                    ),
                ),
            ),
            f"{run_rel} does not exist, so no execution environment is recorded",
            run_record_present=False,
        )

    payload, error = _read_json(path)
    if error is not None:
        return _blank_report(
            run_rel,
            expectation_rel,
            (
                BenchmarkFinding(
                    rule="run-record-unparseable",
                    requirement="R8.15",
                    subject=run_rel,
                    detail=f"the run record could not be parsed: {error}",
                ),
            ),
            f"{run_rel} is not parseable, so no run could be read",
        )

    if not isinstance(payload, Mapping):
        return _blank_report(
            run_rel,
            expectation_rel,
            (
                BenchmarkFinding(
                    rule="run-record-unparseable",
                    requirement="R8.15",
                    subject=run_rel,
                    detail=f"the run record is {type(payload).__name__}, not a mapping",
                ),
            ),
            f"{run_rel} does not contain a mapping",
        )

    declared_version = payload.get("schema_version")
    if declared_version != SUPPORTED_SCHEMA_VERSION:
        return _blank_report(
            run_rel,
            expectation_rel,
            (
                BenchmarkFinding(
                    rule="schema-version-unrecognised",
                    requirement="R8.15",
                    subject=run_rel,
                    detail=(
                        f"schema_version is {declared_version!r} and this reader understands "
                        f"only {SUPPORTED_SCHEMA_VERSION}; a reader that guesses at a shape "
                        "it does not know reports on a document it did not understand"
                    ),
                ),
            ),
            f"{run_rel} declares an unrecognised schema_version",
        )

    try:
        return RunRecordFile.model_validate(strip_comment_keys(payload))
    except ValidationError as error:
        return _blank_report(
            run_rel,
            expectation_rel,
            (
                BenchmarkFinding(
                    rule="schema-invalid",
                    requirement="R8.5, R8.6, R8.15, R8.18",
                    subject=run_rel,
                    detail=_ascii(str(error).replace("\n", "; ")),
                ),
            ),
            f"{run_rel} does not satisfy the run-record model",
        )


def _load_expectations(
    path: Path, expectation_rel: str
) -> tuple[ExpectationFile | None, BenchmarkFinding | None]:
    """``(expectations, finding)``. A finding without expectations is terminal for R8.14."""
    if not path.is_file():
        return None, BenchmarkFinding(
            rule="expectation-absent",
            requirement="R8.14",
            subject=expectation_rel,
            detail=(
                "no expected-outcome record exists. R8.14 exists so the criterion can no "
                "longer be satisfied by never recording a prediction at all, so an absent "
                "record is the failure mode it names -- reported unavailable because nobody "
                "wrote a wrong prediction, there is simply no prediction"
            ),
        )
    payload, error = _read_yaml(path)
    if error is not None or not isinstance(payload, Mapping):
        detail = (
            f"the expectation record could not be parsed: {error}"
            if error is not None
            else f"the expectation record is {type(payload).__name__}, not a mapping"
        )
        return None, BenchmarkFinding(
            rule="expectation-unparseable",
            requirement="R8.14",
            subject=expectation_rel,
            detail=detail,
        )
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        return None, BenchmarkFinding(
            rule="schema-version-unrecognised",
            requirement="R8.14",
            subject=expectation_rel,
            detail=(
                f"schema_version is {payload.get('schema_version')!r} and this reader "
                f"understands only {SUPPORTED_SCHEMA_VERSION}"
            ),
        )
    try:
        loaded = ExpectationFile.model_validate(strip_comment_keys(payload))
    except ValidationError as error:
        return None, BenchmarkFinding(
            rule="schema-invalid",
            requirement="R8.14",
            subject=expectation_rel,
            detail=_ascii(str(error).replace("\n", "; ")),
        )
    if not loaded.expectations:
        return None, BenchmarkFinding(
            rule="expectation-absent",
            requirement="R8.14",
            subject=expectation_rel,
            detail=(
                "the expectation record declares no expectation at all, which is the same "
                "fact as an absent file: nothing has been predicted"
            ),
        )
    return loaded, None


def _environment_findings(
    environment: ExecutionEnvironment, subject: str
) -> tuple[BenchmarkFinding, ...]:
    """R8.15's three exclusions and R8.11's dependency clause, per declared environment."""
    findings: list[BenchmarkFinding] = []
    unmet = environment.unmet_exclusions
    if unmet:
        findings.append(
            BenchmarkFinding(
                rule="cost-exclusion-unmet",
                requirement="R8.15",
                subject=subject,
                detail=(
                    f"{len(unmet)} of R8.15's three cost exclusions do not hold: "
                    f"{', '.join(unmet)}. 'Free' without these exclusions admits a paid tier, "
                    "so this environment is not one training may execute in (I-1)"
                ),
            )
        )
    if environment.flag_disagrees():
        findings.append(
            BenchmarkFinding(
                rule="zero-cost-overclaimed",
                requirement="R8.11, R8.15",
                subject=subject,
                detail=(
                    "declared_zero_cost is true while "
                    f"{', '.join(unmet)} hold(s): the entry asserts a zero-cost execution its "
                    "own declared facts contradict, which is a false self-statement rather "
                    "than an incomplete one"
                ),
            )
        )
    if environment.new_dependencies:
        findings.append(
            BenchmarkFinding(
                rule="dependency-introduced",
                requirement="R8.11",
                subject=subject,
                detail=(
                    f"{len(environment.new_dependencies)} dependency/dependencies are declared "
                    f"as introduced by this environment: "
                    f"{', '.join(environment.new_dependencies)}. R8.11 (I-1) admits no paid "
                    "API, SDK, dependency or host; a dependency recorded here must be shown "
                    "to be unpaid where CI enforces the prohibition, not declared here"
                ),
            )
        )
    return tuple(findings)


def assess(
    run_record_path: Path = RUN_RECORD_FILE,
    expectation_path: Path = EXPECTATION_FILE,
    *,
    repo: Path = ROOT,
) -> BenchmarkTruthReport:
    """Read both artifacts, check every clause, and report. Never raises."""
    run_rel = _relative(run_record_path)
    expectation_rel = _relative(expectation_path)

    loaded = load_run_record(run_record_path, expectation_path)
    if isinstance(loaded, BenchmarkTruthReport):
        return loaded
    record = loaded
    expectations, expectation_finding = _load_expectations(expectation_path, expectation_rel)

    collected: list[BenchmarkFinding] = []
    if expectation_finding is not None:
        collected.append(expectation_finding)

    if not record.environments:
        collected.append(
            BenchmarkFinding(
                rule="environment-absent",
                requirement="R8.15",
                subject=run_rel,
                detail=(
                    "the run record declares no execution environment, so R8.15's three cost "
                    "exclusions hold over an empty set. Nothing is asserted by a record with "
                    "nothing in it"
                ),
            )
        )
    for environment in record.environments:
        collected.extend(
            _environment_findings(environment, f"{run_rel}::{environment.environment_id}")
        )

    ancestry_by_run: list[tuple[str, Ancestry]] = []
    comparability_by_run: list[tuple[str, str]] = []
    confirmed_runs: list[str] = []
    unconfirmed_runs: list[str] = []
    scored = 0
    notes: list[str] = [
        f"run record: {len(record.environments)} environment(s), {len(record.runs)} run(s) "
        f"in {run_rel}",
    ]
    for note in record.notes:
        notes.append(f"note: {_first_line(note)}")

    if not record.runs:
        collected.append(
            BenchmarkFinding(
                rule="no-scored-run",
                requirement="R8.5, R8.14",
                subject=run_rel,
                detail=(
                    "no training run is recorded, so no score and no ancestry could be "
                    "checked. Reported unavailable rather than pass: every clause in this "
                    "gate would hold vacuously over an empty run list, which is the vacuity "
                    "R8.14's second half exists to close"
                ),
            )
        )

    # The comparison setup is checked whether or not a run exists. Without this, every
    # R8.5-R8.8 / R8.12 / R8.13 / R8.18 clause would be unavailable-by-construction until a
    # training run landed, and a gate that cannot fail yet is not yet a gate.
    if record.comparison_setup is not None:
        collected.extend(
            evaluate_record(record.comparison_setup, f"{run_rel}::comparison_setup")
        )
        comparability_by_run.append(
            ("comparison_setup", record.comparison_setup.comparability.status)
        )
        if record.comparison_setup.baseline.confirmed:
            confirmed_runs.append("comparison_setup")
        else:
            unconfirmed_runs.append("comparison_setup")
        if not record.comparison_setup.scored:
            notes.append(
                "comparison_setup: no score yet - "
                + _first_line(record.comparison_setup.score_absent_reason)
            )
    elif not record.runs:
        collected.append(
            BenchmarkFinding(
                rule="comparison-absent",
                requirement="R8.5",
                subject=run_rel,
                detail=(
                    "neither a scored run nor a comparison_setup is recorded, so no metric "
                    "identity, baseline entry, comparability disposition or domain gap exists "
                    "for this gate to check. An empty file asserts nothing -- reported "
                    "unavailable because nobody wrote a wrong value, there is simply nothing "
                    "to read"
                ),
            )
        )

    # R8.14's "SHALL state that a sophisticated model is expected to be competitive rather than
    # dominant" is an obligation on the RECORD, not on a run. Checked in its own loop so it holds
    # before any run exists - inside the run loop it would be unreachable while `runs` is empty,
    # which is precisely the state this repository is in today.
    if expectations is not None:
        for expectation in expectations.expectations:
            if expectation.point_accuracy != REQUIRED_POINT_ACCURACY:
                collected.append(
                    BenchmarkFinding(
                        rule="expectation-not-competitive",
                        requirement="R8.14",
                        subject=f"{expectation_rel}::{expectation.expectation_id}",
                        detail=(
                            f"point_accuracy is {expectation.point_accuracy!r}; R8.14 requires "
                            f"the record to state {REQUIRED_POINT_ACCURACY!r}, because the "
                            "M-Competitions' replicated result is that sophisticated methods "
                            "do not necessarily beat simpler ones on point accuracy"
                        ),
                    )
                )

    for run_entry in record.runs:
        subject = f"{run_rel}::{run_entry.run_id}"
        if record.environment(run_entry.environment_id) is None:
            collected.append(
                BenchmarkFinding(
                    rule="environment-absent",
                    requirement="R8.15",
                    subject=subject,
                    detail=(
                        f"the run names environment {run_entry.environment_id!r}, which the "
                        "record does not declare, so where it executed is unrecorded"
                    ),
                )
            )
        if run_entry.benchmark is None:
            collected.append(
                BenchmarkFinding(
                    rule="no-scored-run",
                    requirement="R8.5",
                    subject=subject,
                    detail=(
                        "the run is declared but carries no benchmark record, so it has "
                        "scored nothing this gate can report on"
                    ),
                )
            )
        else:
            collected.extend(evaluate_record(run_entry.benchmark, subject))
            comparability_by_run.append(
                (run_entry.run_id, run_entry.benchmark.comparability.status)
            )
            if run_entry.benchmark.baseline.confirmed:
                confirmed_runs.append(run_entry.run_id)
            else:
                unconfirmed_runs.append(run_entry.run_id)
            if run_entry.benchmark.scored:
                scored += 1
            else:
                notes.append(
                    f"{run_entry.run_id}: no score yet - "
                    + _first_line(run_entry.benchmark.score_absent_reason)
                )

        if expectations is None:
            continue
        for expectation in expectations.expectations:
            outcome, detail = ancestry(
                expectation.revision or "", run_entry.revision, repo=repo
            )
            ancestry_by_run.append((f"{expectation.expectation_id}->{run_entry.run_id}", outcome))
            if expectation.revision is None:
                collected.append(
                    BenchmarkFinding(
                        rule="expectation-revision-unrecorded",
                        requirement="R8.14",
                        subject=f"{expectation_rel}::{expectation.expectation_id}",
                        detail=(
                            "the expectation records no revision, so its ancestry over the "
                            "scoring run cannot be decided and R8.14 is unestablished. "
                            "Procedure: "
                            + _first_line(expectation.revision_procedure)
                        ),
                    )
                )
            elif outcome == "not-ancestor":
                collected.append(
                    BenchmarkFinding(
                        rule="expectation-not-ancestor",
                        requirement="R8.14",
                        subject=f"{expectation_rel}::{expectation.expectation_id}",
                        detail=(
                            f"{detail}, so the prediction is not established to predate the "
                            "result and the result could have been rationalised after the fact"
                        ),
                    )
                )
            elif outcome == "same-revision":
                collected.append(
                    BenchmarkFinding(
                        rule="expectation-same-revision",
                        requirement="R8.14",
                        subject=f"{expectation_rel}::{expectation.expectation_id}",
                        detail=(
                            f"{detail}; a prediction committed in the same change as the "
                            "result it predicts does not stop post-hoc rationalisation, so "
                            "R8.14's ancestry is read strictly"
                        ),
                    )
                )
            elif outcome == "indeterminate":
                collected.append(
                    BenchmarkFinding(
                        rule="ancestry-indeterminate",
                        requirement="R8.14",
                        subject=f"{expectation_rel}::{expectation.expectation_id}",
                        detail=(
                            f"{detail}. Check out enough history for the job that reports this "
                            "row (actions/checkout defaults to fetch-depth: 1)"
                        ),
                    )
                )

            if expectation.revision is None:
                continue
            # Ancestry says WHEN the sha was committed. This says WHAT the prediction said
            # there. Without the second read, an old sha beside a rewritten statement
            # satisfies R8.14 while predicting nothing.
            historic, historic_detail = prediction_at_revision(
                expectation.revision,
                expectation.expectation_id,
                path=expectation_path,
                repo=repo,
            )
            if historic is None:
                collected.append(
                    BenchmarkFinding(
                        rule="ancestry-indeterminate",
                        requirement="R8.14",
                        subject=f"{expectation_rel}::{expectation.expectation_id}",
                        detail=(
                            f"the prediction as committed could not be read back: "
                            f"{historic_detail}. An unread prediction is not a pre-registered "
                            "one"
                        ),
                    )
                )
            elif historic != expectation.point_accuracy:
                collected.append(
                    BenchmarkFinding(
                        rule="expectation-mutated",
                        requirement="R8.14",
                        subject=f"{expectation_rel}::{expectation.expectation_id}",
                        detail=(
                            f"the artifact now records {expectation.point_accuracy!r} while "
                            f"revision {expectation.revision} recorded {historic!r}: the "
                            "prediction was rewritten after it was committed, which is the "
                            "post-hoc rationalisation R8.14 exists to prevent"
                        ),
                    )
                )

    ordered = tuple(collected)
    verdict = _verdict_of(ordered)

    for environment in record.environments:
        notes.append(
            f"{environment.environment_id}: locus {environment.locus}, zero_cost="
            f"{str(environment.zero_cost).lower()} derived from three exclusions"
        )
    for run_id, status in comparability_by_run:
        notes.append(f"{run_id}: {status}")

    if verdict == "pass":
        reason = (
            f"{scored} scored run(s) each carry a metric identity, a confirmed published "
            "baseline with its source and read date, a comparability disposition, and a "
            "documented domain gap; every expectation is a strict ancestor of the run it "
            "predicts and every execution environment meets all three cost exclusions"
        )
    elif verdict == "fail":
        rules = sorted({item.rule for item in ordered if item.fatal})
        reason = (
            f"the benchmark record makes a statement its own contents or its requirement "
            f"contradict ({', '.join(rules)}); this is a false self-statement, not an "
            "incomplete one"
        )
    else:
        rules = sorted({item.rule for item in ordered})
        reason = (
            f"nothing is established yet ({', '.join(rules)}): no leaderboard number was "
            "invented to fill the gap, so this reports SKIP rather than PASS - absence of "
            "proof is never a pass (I-7)"
        )

    _LOG.info(
        "benchmark_truth.assessed",
        verdict=verdict,
        environments=len(record.environments),
        runs=len(record.runs),
        scored=scored,
        findings=len(ordered),
    )

    return BenchmarkTruthReport(
        run_record_path=run_rel,
        expectation_path=expectation_rel,
        run_record_present=True,
        expectation_present=expectations is not None,
        environments_declared=len(record.environments),
        runs_declared=len(record.runs),
        scored_runs=scored,
        ancestry_by_run=tuple(ancestry_by_run),
        comparability_by_run=tuple(comparability_by_run),
        baseline_confirmed_runs=tuple(confirmed_runs),
        baseline_unconfirmed_runs=tuple(unconfirmed_runs),
        findings=ordered,
        notes=tuple(notes),
        verdict=verdict,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# CLI. `print` is acceptable here and nowhere else in this module.
# ---------------------------------------------------------------------------


def _print_report(report: BenchmarkTruthReport) -> None:
    symbol = _SYMBOLS[report.verdict]
    print(f"{symbol} benchmark-truth: {report.verdict.upper()} - {_ascii(report.reason)}")
    for note in report.notes:
        print(f"     - {_ascii(note)}")
    for finding in report.findings:
        print(
            f"  {_SYMBOLS[finding.verdict_contribution]} {finding.rule} "
            f"[{finding.requirement}] {_ascii(finding.subject)}: {_ascii(finding.detail)}"
        )


def run(*, as_json: bool = False, check: bool = False) -> int:
    """Evaluate and report. Returns ``0`` / ``1`` / ``2`` in both modes."""
    report = assess()

    if as_json:
        print(
            json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        )
        return report.exit_code

    _print_report(report)
    if not check:
        print(
            "(an unconfirmed published value carries no number by construction, and this gate "
            "reports SKIP until a human reads the defining document; it never invents a "
            "leaderboard score.)"
        )
    return report.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark_truth",
        description=(
            "Check that the recorded external benchmark carries its metric identity, a "
            "non-bare baseline, a comparability disposition, a documented domain gap, a "
            "pre-registered expectation at a strict ancestor revision, and an execution "
            "environment meeting all three R8.15 cost exclusions."
        ),
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return run(as_json=bool(args.as_json), check=bool(args.check))


if __name__ == "__main__":
    sys.exit(main())
