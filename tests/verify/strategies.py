"""Shared Hypothesis strategies for the purpose-achievement-audit enforcement spine.

Feature: purpose-achievement-audit, task 1.2. These generators are imported by the
gate-integrity property tests (design Properties 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12)
so each test states its property and nothing else, and so the input space is
constrained once, in one reviewed place, instead of per test.

Scope of this module:

* **check-result multisets** - ``check_results`` / ``check_result_multisets`` /
  ``registry_scenarios`` drive ``scripts/audit/registry_gate.py`` (E1.1) over the
  four-status vocabulary ``scripts.audit.verify_claims.STATUSES``.
* **narrative claim multisets** - ``claim_results`` / ``claim_result_multisets`` /
  ``masking_scenarios`` drive ``scripts.audit.doc_truth.evaluate_claims`` (E1.3) over
  the three-status claim vocabulary plus the ``required`` flag, including the
  "many ok siblings beside one unresolved required claim" shape Property 2 needs.
* **id sets** - ``check_ids`` plus the (registered, executed) divergence modes
  Property 1 quantifies over (missing ids, foreign ids, duplicates).
* **workflow / step shapes** - ``step_drafts`` / ``workflow_documents`` render real
  GitHub-Actions-shaped YAML carrying the four exit-status-discarding constructs, for
  ``workflow_shape_truth`` (E1.5) and ``gate_surface`` (E1.6).
* **document + source pin pairs** - ``pin_cases`` builds a ``doc-number-pins.yaml``
  row together with the document text and the mechanical source it pins against
  (E1.3 / AD-3).
* **threshold sequences** - ``threshold_sequences`` / ``named_threshold_sequences``
  for the monotone-ratchet property (E1.8).
* **coverage reports** - ``coverage_cases`` pairs a measured report with a floors
  table carrying the ``measured_at`` / ``source_run`` provenance task 4.1 writes.

Two rules this module obeys, both binding:

* **I-0** - no strategy here executes a gate, a subprocess, a container, or the real
  53-check suite. Every generator is pure data construction; the *tests* decide what
  to drive with it.
* **I-0 authoring rule** - ``max_examples`` is never set here and must never be set
  in the importing tests. The budget comes from the root ``conftest.py`` profiles
  (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Final, Literal

import yaml
from hypothesis import strategies as st

from scripts.audit.doc_truth import ClaimResult
from scripts.audit.verify_claims import STATUSES, CheckResult

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "ADVISORY_MARKERS",
    "CLAIM_STATUSES",
    "DISCARDING_CONSTRUCTS",
    "EXTRACTOR_KINDS",
    "PIN_KINDS",
    "STATUSES",
    "CoverageCase",
    "FloorEntry",
    "JobDraft",
    "MaskingScenario",
    "PinCase",
    "RegistryScenario",
    "StepDraft",
    "WorkflowDraft",
    "check_ids",
    "check_result_multisets",
    "check_results",
    "claim_result_multisets",
    "claim_results",
    "claim_statuses",
    "coverage_cases",
    "masking_scenarios",
    "named_threshold_sequences",
    "pin_cases",
    "registry_scenarios",
    "statuses",
    "step_drafts",
    "threshold_sequences",
    "workflow_documents",
]

# ---------------------------------------------------------------------------
# Check results and identifier sets (Properties 1, 9, 10)
# ---------------------------------------------------------------------------

# Identifiers are shaped like the real registry's (C1..C61) so a generated id is
# indistinguishable from a registered one to the code under test, and a "foreign"
# id is foreign because it is absent, not because it is malformed.
_ID_PREFIXES: Final[tuple[str, ...]] = ("C", "S", "X")


def statuses() -> st.SearchStrategy[str]:
    """One status from the emitted four-status vocabulary (``vc.STATUSES``)."""
    return st.sampled_from(STATUSES)


def check_ids(*, min_size: int = 0, max_size: int = 12) -> st.SearchStrategy[tuple[str, ...]]:
    """A set of distinct check identifiers, in registration order.

    Distinctness matters: the registry's own contract is that ids are unique, so a
    duplicate is a defect to be injected deliberately (see ``registry_scenarios``)
    rather than a background condition every example carries.
    """
    return st.lists(
        st.builds(
            "{}{}".format,
            st.sampled_from(_ID_PREFIXES),
            st.integers(min_value=1, max_value=99),
        ),
        min_size=min_size,
        max_size=max_size,
        unique=True,
    ).map(tuple)


def _title_for(cid: str) -> str:
    return f"synthetic check {cid}"


def check_results(
    *,
    cid: str | None = None,
    status: str | None = None,
) -> st.SearchStrategy[CheckResult]:
    """One :class:`~scripts.audit.verify_claims.CheckResult`.

    ``cid`` and ``status`` pin those fields when the caller already knows them
    (the registry-scenario builder does); otherwise both are drawn.

    ``title`` is derived from the *drawn* ``cid`` rather than drawn beside it, so a
    generated result is never internally inconsistent (a title naming one check while
    ``cid`` names another). Identity divergence is a defect this module injects
    deliberately, between ``registered_ids`` and a result's ``cid``
    (``registry_scenarios``' ``foreign`` mode, R10.5) - never by accident inside a
    single result.
    """
    cid_strategy = st.just(cid) if cid is not None else check_ids(min_size=1, max_size=1).map(
        lambda ids: ids[0]
    )
    status_strategy = st.just(status) if status is not None else statuses()
    details = st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        max_size=40,
    )
    return st.tuples(cid_strategy, status_strategy, details).map(
        lambda drawn: CheckResult(
            cid=drawn[0],
            title=_title_for(drawn[0]),
            status=drawn[1],
            detail=drawn[2],
        )
    )


def check_result_multisets(
    *,
    min_size: int = 0,
    max_size: int = 12,
) -> st.SearchStrategy[tuple[CheckResult, ...]]:
    """A multiset of check results: ids may repeat, statuses are unconstrained.

    A *multiset* rather than a set because Property 1 quantifies over result
    collections a defective registry could actually emit - including one id
    reported twice.
    """
    return st.lists(check_results(), min_size=min_size, max_size=max_size).map(tuple)


@dataclass(frozen=True)
class RegistryScenario:
    """One Check_Registry execution as a gate sees it (design E1.1).

    ``registered_ids`` is what ``@register`` declared; ``results`` is what the
    execution emitted. The two are allowed to diverge - that divergence is the
    subject of Requirements 1.7 and 10.5.
    """

    registered_ids: tuple[str, ...]
    results: tuple[CheckResult, ...]

    @property
    def executed_ids(self) -> tuple[str, ...]:
        """Identifiers the results actually reported, in emission order."""
        return tuple(result.cid for result in self.results)

    @property
    def missing_ids(self) -> tuple[str, ...]:
        """Registered identifiers no result reported, in registration order."""
        executed = set(self.executed_ids)
        return tuple(cid for cid in self.registered_ids if cid not in executed)

    @property
    def foreign_ids(self) -> tuple[str, ...]:
        """Reported identifiers that were never registered, in emission order."""
        registered = set(self.registered_ids)
        return tuple(cid for cid in self.executed_ids if cid not in registered)

    @property
    def status_counts(self) -> dict[str, int]:
        """An independent recompute of the four counts plus ``TOTAL``.

        Independent of the gate's own tally on purpose: a test comparing the gate's
        counts against these is comparing two implementations, not one.
        """
        counts = {status: 0 for status in STATUSES}
        for result in self.results:
            if result.status in counts:
                counts[result.status] += 1
        counts["TOTAL"] = len(self.results)
        return counts

    def as_registry(self) -> list[tuple[str, str, object]]:
        """Render a ``verify_claims._CHECKS``-shaped registration list.

        Only the registered ids are represented; the callables are placeholders,
        because a test that needs executable checks builds them from ``results``.
        """
        return [(cid, _title_for(cid), None) for cid in self.registered_ids]


# How a generated execution diverges from its registration, one mode per example.
_DivergenceMode = Literal["complete", "missing", "foreign", "duplicate", "empty"]
_DIVERGENCE_MODES: Final[tuple[_DivergenceMode, ...]] = (
    "complete",
    "missing",
    "foreign",
    "duplicate",
    "empty",
)


@st.composite
def registry_scenarios(
    draw: st.DrawFn,
    *,
    max_checks: int = 8,
    modes: Sequence[str] = _DIVERGENCE_MODES,
) -> RegistryScenario:
    """A (registered ids, emitted results) pair covering every divergence mode.

    Modes, drawn one per example:

    * ``complete``  - every registered id reported exactly once.
    * ``missing``   - at least one registered id reported by no result (R1.7).
    * ``foreign``   - a result carrying an id that was never registered (R10.5).
    * ``duplicate`` - one id reported twice.
    * ``empty``     - ids registered, zero results emitted (R1.6).

    Statuses are drawn freely, so the all-``SKIP`` and any-``FAIL`` cases the
    verdict order distinguishes arise naturally rather than being special-cased.
    """
    registered = draw(check_ids(min_size=1, max_size=max_checks))
    mode: str = draw(st.sampled_from(tuple(modes)))

    if mode == "empty":
        return RegistryScenario(registered_ids=registered, results=())

    reported = list(registered)
    if mode == "missing":
        drop = draw(st.integers(min_value=1, max_value=len(reported)))
        reported = reported[: len(reported) - drop]
    elif mode == "foreign":
        foreign = draw(
            check_ids(min_size=1, max_size=2).filter(
                lambda ids: all(cid not in registered for cid in ids)
            )
        )
        reported.extend(foreign)
    elif mode == "duplicate":
        reported.append(draw(st.sampled_from(registered)))

    # One result per reported id, each drawing its own status, so the all-SKIP and
    # any-FAIL cases the verdict order distinguishes arise from the draw itself.
    results = tuple(draw(check_results(cid=cid)) for cid in reported)
    return RegistryScenario(registered_ids=registered, results=results)


# ---------------------------------------------------------------------------
# Narrative-truth claim multisets (Property 2)
# ---------------------------------------------------------------------------

#: The three statuses one narrative claim can report (``doc_truth.ClaimStatus``).
#: Distinct from ``STATUSES`` above: a claim has no PARTIAL, and its ``skip`` is what
#: the ``required`` flag makes non-maskable (R1.6).
CLAIM_STATUSES: Final[tuple[str, ...]] = ("ok", "fail", "skip")

#: Claim names shaped like the real ones (the two bespoke claims plus pin ids), so a
#: generated name is a plausible key in a failure detail and is never empty - a claim
#: the aggregate cannot name is a different (and separately specified) defect.
_CLAIM_NAMES: Final[tuple[str, ...]] = (
    "headline-counts",
    "deploy-cadence",
    "pin-table",
    "coverage-target",
    "stryker-break",
    "kv-cache-floor",
    "spec-coverage-threshold",
    "blocking-verify-steps",
)


def claim_statuses() -> st.SearchStrategy[str]:
    """One status from the narrative-claim vocabulary."""
    return st.sampled_from(CLAIM_STATUSES)


def claim_results(
    *,
    name: str | None = None,
    status: str | None = None,
    required: bool | None = None,
) -> st.SearchStrategy[ClaimResult]:
    """One :class:`~scripts.audit.doc_truth.ClaimResult`.

    Any field the caller already knows is pinned; the rest are drawn. ``detail`` is
    always non-empty ASCII so an assertion that the aggregate quoted a claim's detail
    is testing the aggregate rather than the emptiness of the draw.
    """
    return st.builds(
        ClaimResult,
        name=st.just(name) if name is not None else st.sampled_from(_CLAIM_NAMES),
        status=st.just(status) if status is not None else claim_statuses(),
        required=st.just(required) if required is not None else st.booleans(),
        detail=st.text(
            alphabet=st.characters(min_codepoint=32, max_codepoint=126),
            min_size=1,
            max_size=40,
        ),
    )


def claim_result_multisets(
    *,
    min_size: int = 0,
    max_size: int = 8,
) -> st.SearchStrategy[tuple[ClaimResult, ...]]:
    """A multiset of claim results: names may repeat, statuses are unconstrained.

    A multiset because the aggregate is specified over whatever ``collect_claims``
    emits, and the pin table can legitimately produce several rows that resolve to the
    same status. The empty tuple is included: rule 1 of the aggregate is about it.
    """
    return st.lists(claim_results(), min_size=min_size, max_size=max_size).map(tuple)


@dataclass(frozen=True)
class MaskingScenario:
    """One unresolved required claim, a pile of ``ok`` siblings, and other noise.

    Shaped for design Property 2's quantifier: ``blocking`` holds at least one
    *required* claim that is ``fail`` or ``skip``, ``ok_siblings`` holds ``ok`` claims
    that must not be able to supply a passing verdict however many of them there are,
    and ``others`` holds claims that are never blocking on their own (an ``ok`` claim,
    or an optional ``skip``) so the blocking set stays the only cause.
    """

    blocking: tuple[ClaimResult, ...]
    ok_siblings: tuple[ClaimResult, ...]
    others: tuple[ClaimResult, ...]

    def with_ok(self, count: int) -> tuple[ClaimResult, ...]:
        """The claim set carrying the first ``count`` ``ok`` siblings."""
        return (*self.blocking, *self.others, *self.ok_siblings[:count])

    @property
    def claims(self) -> tuple[ClaimResult, ...]:
        """The full claim set, every ``ok`` sibling included."""
        return self.with_ok(len(self.ok_siblings))

    @property
    def required_unresolved(self) -> tuple[ClaimResult, ...]:
        """Every required claim in the full set that reports ``skip``."""
        return tuple(c for c in self.claims if c.required and c.status == "skip")

    @property
    def fails(self) -> tuple[ClaimResult, ...]:
        """Every claim in the full set that reports ``fail``."""
        return tuple(c for c in self.claims if c.status == "fail")


@st.composite
def masking_scenarios(
    draw: st.DrawFn,
    *,
    blocking_statuses: Sequence[str] = ("fail", "skip"),
    max_blocking: int = 2,
    max_ok: int = 5,
    max_others: int = 3,
) -> MaskingScenario:
    """A claim set that must not be able to reach ``ok``, plus its ``ok`` siblings.

    ``blocking_statuses`` narrows the drawn blocking status when a test is about one
    clause only - ``("skip",)`` isolates R1.6's non-maskable clause, where the removed
    defect lived ("return ok if any claim is ok").
    """
    blocking = tuple(
        draw(claim_results(status=draw(st.sampled_from(tuple(blocking_statuses))), required=True))
        for _ in range(draw(st.integers(min_value=1, max_value=max_blocking)))
    )
    ok_siblings = tuple(
        draw(claim_results(status="ok"))
        for _ in range(draw(st.integers(min_value=0, max_value=max_ok)))
    )
    # Never blocking on their own: an ``ok`` claim (either flag) or an OPTIONAL skip.
    # An optional ``fail`` is excluded here because rule 2 would make it the cause of
    # the verdict; the drift clause is exercised through ``blocking_statuses``.
    others = tuple(
        draw(st.one_of(claim_results(status="ok"), claim_results(status="skip", required=False)))
        for _ in range(draw(st.integers(min_value=0, max_value=max_others)))
    )
    return MaskingScenario(blocking=blocking, ok_siblings=ok_siblings, others=others)


# ---------------------------------------------------------------------------
# Workflow and step shapes (Properties 4, 11)
# ---------------------------------------------------------------------------

#: The four exit-status-discarding constructs E1.5 classifies (design Property 4).
DISCARDING_CONSTRUCTS: Final[tuple[str, ...]] = (
    "|| true",
    "|| echo",
    "; exit 0",
    "continue-on-error: true",
)

#: Markers that make a non-propagating step honest rather than a violation (R11.3).
ADVISORY_MARKERS: Final[tuple[str, ...]] = ("ADVISORY", "informational")

#: Trigger contexts ``gate_surface`` evaluates ``on:`` / ``if:`` against (E1.6).
_TRIGGERS: Final[tuple[str, ...]] = (
    "push:main",
    "pull_request",
    "tag:v*",
    "schedule",
    "workflow_dispatch",
)

_STEP_COMMANDS: Final[tuple[str, ...]] = (
    "python -m scripts.audit.verify_claims",
    "python -m scripts.audit.registry_gate",
    "ruff check .",
    "mypy --strict packages",
    "pnpm vitest run",
    "python scripts/coverage_per_package.py",
)

_STEP_LABELS: Final[tuple[str, ...]] = (
    "Ruff lint",
    "Narrative-truth gate",
    "Per-package coverage floor",
    "License audit",
    "Size budget",
    "Contract tests",
)


@dataclass(frozen=True)
class StepDraft:
    """One workflow step's propagation shape (mirrors E1.5's ``StepShape``).

    ``discarding_construct`` is the *ground truth* of the generated step: the shape
    checker's job is to rediscover it from the rendered YAML.
    """

    step_name: str
    run: str
    continue_on_error: bool
    discarding_construct: str | None
    declared_blocking: bool

    @property
    def propagates_exit_status(self) -> bool:
        return self.discarding_construct is None

    @property
    def advisory_in_name(self) -> bool:
        return any(marker.lower() in self.step_name.lower() for marker in ADVISORY_MARKERS)

    def as_yaml_obj(self) -> dict[str, object]:
        step: dict[str, object] = {"name": self.step_name, "run": self.run}
        if self.continue_on_error:
            step["continue-on-error"] = True
        return step


@st.composite
def step_drafts(
    draw: st.DrawFn,
    *,
    declared_blocking: bool | None = None,
    constructs: Sequence[str | None] | None = None,
) -> StepDraft:
    """One step, either propagating or carrying exactly one discarding construct.

    Exactly one construct per step keeps the counterexample readable: a failure
    names the single construct that caused it instead of a soup of four.

    ``constructs`` narrows what may be injected, the way ``check_results``' ``status``
    and ``claim_results``' ``required`` narrow theirs: ``(None,)`` yields only
    propagating steps, ``DISCARDING_CONSTRUCTS`` only non-propagating ones, and a
    single-element tuple pins one construct so a test can quantify over the four
    explicitly. Left unset, the construct is drawn from ``None`` plus all four. This is
    a pin, not a filter, deliberately: a ``.filter`` over this composite accepts about
    one draw in eight and would trip Hypothesis' ``filter_too_much`` health check.
    """
    label = draw(st.sampled_from(_STEP_LABELS))
    command = draw(st.sampled_from(_STEP_COMMANDS))
    construct = draw(
        st.sampled_from(tuple(constructs))
        if constructs is not None
        else st.none() | st.sampled_from(DISCARDING_CONSTRUCTS)
    )
    marked_advisory = draw(st.booleans())
    marker = draw(st.sampled_from(ADVISORY_MARKERS))

    name = f"{label} ({marker})" if marked_advisory else label
    continue_on_error = construct == "continue-on-error: true"
    if construct is None or continue_on_error:
        run = command
    elif construct == "|| echo":
        run = f'{command} || echo "non-blocking"'
    else:
        run = f"{command} {construct}"

    blocking = draw(st.booleans()) if declared_blocking is None else declared_blocking
    return StepDraft(
        step_name=name,
        run=run,
        continue_on_error=continue_on_error,
        discarding_construct=construct,
        declared_blocking=blocking,
    )


@dataclass(frozen=True)
class JobDraft:
    """One workflow job: its selection condition, its ``needs:`` edges, its steps."""

    job_id: str
    needs: tuple[str, ...]
    if_condition: str | None
    steps: tuple[StepDraft, ...]

    def as_yaml_obj(self) -> dict[str, object]:
        job: dict[str, object] = {"runs-on": "ubuntu-latest"}
        if self.needs:
            job["needs"] = list(self.needs)
        if self.if_condition is not None:
            job["if"] = self.if_condition
        job["steps"] = [step.as_yaml_obj() for step in self.steps]
        return job


@dataclass(frozen=True)
class WorkflowDraft:
    """A whole generated workflow file, renderable to the YAML a gate parses."""

    path: str
    triggers: tuple[str, ...]
    jobs: tuple[JobDraft, ...]

    def as_yaml_obj(self) -> dict[str, object]:
        on: dict[str, object] = {}
        for trigger in self.triggers:
            if trigger == "push:main":
                on["push"] = {"branches": ["main"]}
            elif trigger == "pull_request":
                on["pull_request"] = {"branches": ["main"]}
            elif trigger == "tag:v*":
                push = on.get("push")
                if isinstance(push, dict):
                    push["tags"] = ["v*"]
                else:
                    on["push"] = {"tags": ["v*"]}
            elif trigger == "schedule":
                on["schedule"] = [{"cron": "0 3 * * *"}]
            else:
                on["workflow_dispatch"] = {}
        return {
            "name": self.path.rsplit("/", 1)[-1].removesuffix(".yml"),
            "on": on,
            "jobs": {job.job_id: job.as_yaml_obj() for job in self.jobs},
        }

    def to_yaml(self) -> str:
        """Render deterministic, ASCII-only YAML text (E-S13-07 read contract)."""
        return yaml.safe_dump(self.as_yaml_obj(), sort_keys=True, allow_unicode=False)

    def steps(self) -> tuple[tuple[str, StepDraft], ...]:
        """Every ``(job_id, step)`` pair, in file order."""
        return tuple((job.job_id, step) for job in self.jobs for step in job.steps)


@st.composite
def workflow_documents(
    draw: st.DrawFn,
    *,
    max_jobs: int = 3,
    max_steps: int = 3,
) -> WorkflowDraft:
    """A workflow whose jobs carry ``needs:`` edges and selection conditions.

    ``needs`` only ever points at an earlier job, so the dependency graph is
    acyclic by construction - a cycle would be a different (and separately
    specified) failure mode, not a shape question.
    """
    path = draw(
        st.sampled_from(
            (
                ".github/workflows/ci.yml",
                ".github/workflows/frontend.yml",
                ".github/workflows/cd-gcp.yml",
                ".github/workflows/mutation.yml",
            )
        )
    )
    triggers = draw(
        st.lists(st.sampled_from(_TRIGGERS), min_size=1, max_size=3, unique=True).map(tuple)
    )
    job_count = draw(st.integers(min_value=1, max_value=max_jobs))

    jobs: list[JobDraft] = []
    for index in range(job_count):
        earlier = tuple(job.job_id for job in jobs)
        needs = (
            draw(st.lists(st.sampled_from(earlier), max_size=len(earlier), unique=True).map(tuple))
            if earlier
            else ()
        )
        jobs.append(
            JobDraft(
                job_id=f"job-{index}",
                needs=needs,
                if_condition=draw(
                    st.none()
                    | st.sampled_from(
                        (
                            "github.event_name == 'pull_request'",
                            "github.ref == 'refs/heads/main'",
                            "startsWith(github.ref, 'refs/tags/v')",
                        )
                    )
                ),
                steps=draw(
                    st.lists(step_drafts(), min_size=1, max_size=max_steps).map(tuple)
                ),
            )
        )
    return WorkflowDraft(path=path, triggers=triggers, jobs=tuple(jobs))


# ---------------------------------------------------------------------------
# Document + source pin pairs (Property 5)
# ---------------------------------------------------------------------------

#: Pin kinds ``doc-number-pins.yaml`` declares (E1.3).
PIN_KINDS: Final[tuple[str, ...]] = ("threshold", "flag", "blocking-gate", "required-job")

#: Extractor families a pin resolves its mechanical source with.
EXTRACTOR_KINDS: Final[tuple[str, ...]] = ("yaml_path", "json_path", "regex")


@dataclass(frozen=True)
class PinCase:
    """A pin row plus both sides it compares (E1.3 / AD-3, design Property 5).

    ``document_text`` and ``source_text`` are complete file bodies including
    non-matching decoy lines, so the anchor's "matches exactly one line" contract
    is exercised rather than assumed.
    """

    pin: Mapping[str, object]
    document_text: str
    source_text: str
    document_value: str
    source_value: str
    agrees: bool


_DECOY_DOC_LINES: Final[tuple[str, ...]] = (
    "# SYNAPSE governance document",
    "A SKIP is not a PASS, and absence of proof is never a pass.",
    "Superseded: coverage target 55.0% line+branch (Sprint 8).",
)


def _render_source(extractor_kind: str, value: str) -> tuple[str, str]:
    """Return ``(extractor, source_text)`` for one mechanical source."""
    if extractor_kind == "yaml_path":
        body = yaml.safe_dump({"floors": {"pinned": {"value": value}}}, sort_keys=True)
        return "yaml_path:floors.pinned.value", body
    if extractor_kind == "json_path":
        body = json.dumps({"thresholds": {"pinned": value}}, sort_keys=True, indent=2)
        return "json_path:$.thresholds.pinned", body
    return (
        r"regex:--pinned-threshold (?P<value>[\d.]+)",
        f"run: gate.py --pinned-threshold {value} --strict\n",
    )


@st.composite
def pin_cases(draw: st.DrawFn) -> PinCase:
    """One (document value, mechanical source value) pin pair.

    ``scale`` reproduces the real ``percent_of_fraction`` case (the document states
    ``80``, the source stores ``0.80``): a pin that agrees only after scaling is
    generated as agreeing, so a checker that forgets the scale is caught rather
    than accommodated.
    """
    pin_id = draw(st.sampled_from(("coverage-target", "stryker-break", "kv-cache-floor")))
    kind = draw(st.sampled_from(PIN_KINDS))
    extractor_kind = draw(st.sampled_from(EXTRACTOR_KINDS))
    scale = draw(st.sampled_from(("identity", "percent_of_fraction")))
    agrees = draw(st.booleans())

    if scale == "percent_of_fraction":
        percent = draw(st.integers(min_value=0, max_value=100))
        document_value = str(percent)
        matched_source = f"{percent / 100:.2f}"
    else:
        percent = draw(st.integers(min_value=0, max_value=100))
        document_value = f"{percent}.0"
        matched_source = document_value

    if agrees:
        source_value = matched_source
    else:
        drift = draw(st.integers(min_value=1, max_value=25))
        source_value = (
            f"{min(percent + drift, 100) / 100:.2f}"
            if scale == "percent_of_fraction"
            else f"{min(percent + drift, 100)}.0"
        )
        agrees = source_value == matched_source

    extractor, source_text = _render_source(extractor_kind, source_value)
    document_line = f"- pinned value: {document_value} (mechanical)"
    decoys = draw(st.lists(st.sampled_from(_DECOY_DOC_LINES), max_size=3, unique=True))
    document_text = "\n".join([*decoys, document_line, ""])

    return PinCase(
        pin={
            "id": pin_id,
            "kind": kind,
            "required": draw(st.booleans()),
            "document": "CLAUDE.md",
            "anchor": r"- pinned value: (?P<value>[\d.]+) \(mechanical\)",
            "source": "infrastructure/quality/pinned.yaml",
            "extractor": extractor,
            "compare": "numeric",
            "scale": scale,
        },
        document_text=document_text,
        source_text=source_text,
        document_value=document_value,
        source_value=source_value,
        agrees=agrees,
    )


# ---------------------------------------------------------------------------
# Threshold sequences (Property 6)
# ---------------------------------------------------------------------------


def threshold_sequences(
    *,
    min_size: int = 1,
    max_size: int = 8,
    low: float = 0.0,
    high: float = 100.0,
) -> st.SearchStrategy[tuple[float, ...]]:
    """A sequence of successively committed values for one ratcheted threshold.

    Values are two-decimal floats in ``[low, high]`` and are deliberately *not*
    sorted: a ratchet is only interesting on a sequence that contains a regression,
    so the generator must be able to produce one.
    """
    return st.lists(
        st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False).map(
            lambda value: round(value, 2)
        ),
        min_size=min_size,
        max_size=max_size,
    ).map(tuple)


#: The thresholds ``ratchets.json`` records a highest-ever value for (E1.8).
_RATCHET_NAMES: Final[tuple[str, ...]] = (
    "coverage.packages/synapse_common.line",
    "coverage.orchestrator.line",
    "frontend.stryker.break",
    "mutation.survival.rewards",
    "mutation.survival.guardrails",
    "uplift.floor",
    "dead_modules.baseline",
    "actuating_agents.baseline",
)


def named_threshold_sequences(
    *,
    max_names: int = 4,
    max_size: int = 6,
) -> st.SearchStrategy[Mapping[str, tuple[float, ...]]]:
    """A mapping of ratchet name to its commit history, for the whole-file case."""
    return st.dictionaries(
        keys=st.sampled_from(_RATCHET_NAMES),
        values=threshold_sequences(max_size=max_size),
        min_size=1,
        max_size=max_names,
    )


# ---------------------------------------------------------------------------
# Coverage reports (Property 7)
# ---------------------------------------------------------------------------

_GATED_PACKAGES: Final[tuple[str, ...]] = (
    "packages/synapse_common",
    "orchestrator",
    "agents/demand_prophet",
    "agents/inventory_sentinel",
    "agents/pricing_oracle",
    "digital_twin",
    "uplift",
)


@dataclass(frozen=True)
class FloorEntry:
    """One row of ``infrastructure/quality/coverage-floors.yaml``.

    ``measured_at`` is the field task 4.1 writes: ``None`` means the floor was
    never measured (report ``SKIP - unmeasured``), a timestamp beside a ``0.0``
    floor means the floor is vacuous and must FAIL (R7.2).
    """

    line: float
    target: float
    measured_at: str | None
    source_run: str | None

    def as_yaml_obj(self) -> dict[str, object]:
        return {
            "line": self.line,
            "target": self.target,
            "measured_at": self.measured_at,
            "source_run": self.source_run,
        }


@dataclass(frozen=True)
class CoverageCase:
    """A measured coverage report paired with the floors table it is gated against.

    A package present in ``floors`` and absent from ``measured`` models the real
    "the runner produced no number for this package" case, which must never read
    as a pass.
    """

    floors: Mapping[str, FloorEntry]
    measured: Mapping[str, float]

    @property
    def below_floor(self) -> tuple[str, ...]:
        """Packages whose measured value is strictly below their floor."""
        return tuple(
            name
            for name, entry in sorted(self.floors.items())
            if name in self.measured and self.measured[name] < entry.line
        )

    @property
    def vacuous(self) -> tuple[str, ...]:
        """Gated packages with a zero floor that has nonetheless been measured."""
        return tuple(
            name
            for name, entry in sorted(self.floors.items())
            if entry.line == 0.0 and entry.measured_at is not None
        )

    @property
    def unmeasured(self) -> tuple[str, ...]:
        """Gated packages with a zero floor and no recorded measurement."""
        return tuple(
            name
            for name, entry in sorted(self.floors.items())
            if entry.line == 0.0 and entry.measured_at is None
        )

    def floors_yaml(self) -> str:
        """Render the floors table as ``coverage_per_package.py`` reads it."""
        return yaml.safe_dump(
            {
                "target": 84.0,
                "packages": {
                    name: entry.as_yaml_obj() for name, entry in sorted(self.floors.items())
                },
            },
            sort_keys=True,
        )


def _timestamps() -> st.SearchStrategy[str]:
    return st.datetimes(
        min_value=datetime(2026, 1, 1),
        max_value=datetime(2027, 1, 1),
    ).map(lambda moment: moment.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"))


@st.composite
def coverage_cases(draw: st.DrawFn, *, max_packages: int = 5) -> CoverageCase:
    """A (floors, measured) pair covering below-floor, vacuous, and unmeasured rows.

    Floors are drawn from ``{0.0} u [1.0, 95.0]`` so the vacuous-zero case is
    reachable on a meaningful fraction of examples instead of only when a float
    happens to land exactly on zero.
    """
    names = draw(
        st.lists(
            st.sampled_from(_GATED_PACKAGES),
            min_size=1,
            max_size=max_packages,
            unique=True,
        )
    )

    floors: dict[str, FloorEntry] = {}
    measured: dict[str, float] = {}
    for name in names:
        line = draw(
            st.one_of(
                st.just(0.0),
                st.floats(min_value=1.0, max_value=95.0, allow_nan=False).map(
                    lambda value: round(value, 1)
                ),
            )
        )
        has_measurement = draw(st.booleans())
        timestamp = draw(_timestamps()) if has_measurement else None
        floors[name] = FloorEntry(
            line=line,
            target=84.0,
            measured_at=timestamp,
            source_run=f"gh-run-{draw(st.integers(min_value=1, max_value=9999))}"
            if has_measurement
            else None,
        )
        if draw(st.booleans()):
            # Straddle the floor so both the pass and the fail side are reachable.
            measured[name] = round(
                draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False)), 2
            )

    return CoverageCase(floors=floors, measured=measured)
