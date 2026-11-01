"""Property-based test that the uplift artifact round-trips losslessly and canonically.

Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
losslessly and canonically

    *For any* completed run summary, serialising it to the result artifact and parsing it
    back yields an equivalent :class:`~uplift.uplift_floor.PoweredProof` and provenance
    record, the serialised bytes are canonical (``sort_keys=True``, compact separators),
    and re-serialising the parsed value reproduces the same bytes.

Requirement 2.3: a completed powered run writes an artifact carrying ``incomplete: false``,
a finite numeric ``headline_uplift``, a numeric ``kl_divergence``, a boolean
``within_fidelity_bound``, the replicates-per-arm count, and a provenance record naming the
run identifier, the source revision, the seed set, and the arm identifiers.

Why the property is shaped this way
-----------------------------------
The C60 gate no longer reads a bare headline number; it reads an
:class:`~uplift.harness.UpliftArtifact` through :meth:`UpliftArtifact.read`
(``scripts/audit/uplift_truth.py::_read_artifact``). That makes the artifact's
serialisation the *evidence boundary* of the one question the project exists to answer, so
three separate things have to hold at once, and each is a distinct way the boundary could
leak:

* **Lossless.** Every recorded field survives the trip, the key set on the wire is exactly
  the model's declared field set (nothing dropped), and ``extra="forbid"`` means nothing can
  be silently *added* either -- an unknown key is a rejection, not a discarded field. A
  restated ``arm_aggregates_digest`` is rejected too, so bytes cannot claim aggregates they
  do not carry.

* **Canonical.** Byte identity is asserted across **two independent constructions** of one
  logical artifact -- keyword construction, and validation of a payload whose every mapping
  was built in *reversed* key-insertion order -- not across two calls on one object. A
  serialiser that leaked dict order would give two byte-different files for one measurement,
  which breaks R2.5's "two runs of the same seed set are byte-comparable" for a reason that
  has nothing to do with the measurement. Calling ``to_canonical_json`` twice on one object
  would prove nothing about that. The canonical form is then re-derived with a plain
  ``json.dumps(obj, sort_keys=True, separators=(',',':'))`` -- stdlib, no ``default=`` hook
  -- so this file is an independent statement of the convention rather than a call back into
  ``uplift.harness.canonical_json``. The ``arm_aggregates_digest`` is likewise recomputed
  here with ``hashlib`` over independently built aggregate mappings.

* **Rejecting, not coercing.** ``incomplete: true`` is a *first-class honest state* (I-7):
  the model must accept it, must round-trip it as exactly ``True``, and must surface it as
  not-proof-grade. What is forbidden is silent coercion to ``false``. A non-finite
  ``headline_uplift``, a non-numeric or absent ``kl_divergence``, a non-boolean or absent
  ``incomplete``, and an absent provenance record are all rejected outright by the model the
  gate reads through -- so an inadmissible artifact cannot reach the verdict path wearing an
  admissible shape.

The v2 artifact (decision-quality-proof task 15.1, Metric_Contract v2)
---------------------------------------------------------------------
The artifact gained six required fields -- ``schema_version``, the ``interval`` block the
headline is the point of, the ``headline_verdict`` that interval licenses, the
``materiality_margin`` it was judged against, the ``comparator``, and the whole-run
``run_incomplete`` -- and the provenance record gained ``arm_roles``. The three claims above
extend to them unchanged. *Lossless*: generated intervals are placed to license each of the
four verdicts, including the two boundaries the rule's strictness exists for (a low bound ON
the margin, a bound AT zero), plus the no-estimate state, and the interval block's wire keys
are exactly ``uplift.interval.Interval``'s seven fields. *Canonical*: the interval and role
maps are key-reversed like every other mapping. *Rejecting*: a version-1 payload, an unknown
key inside the interval block, a stored verdict the committed rule does not derive, a
headline that is not the interval's point, and an interval that is inverted or does not
bracket its point are each refused -- the corpus becomes more discriminating, not less (task
15.1's coupling note). The margin is read from the committed contract, never written as a
literal. The aggregate digest is still recomputed over the aggregates alone, so every
assertion of it also pins AD-15: the interval block never moves it.

Deliberately **not** restated here
----------------------------------
* ``tests/uplift/test_headline_artifact_roundtrip_property.py`` (feature
  ``core-purpose-uplift``, Property 7) already owns "an assembled non-incomplete
  ``UpliftResult`` persists a finite ``headline_uplift`` and ``incomplete: false``", read
  back through ``UpliftArtifact.read``. It asserts nothing about canonical bytes, byte
  idempotence, provenance recovery, ``PoweredProof`` recovery, or rejection. Those are this
  file's subject; the headline-is-finite claim is not re-derived from an assembled result
  here.
* ``tests/uplift/test_uplift_truth_gate_property.py`` and
  ``tests/uplift/test_c60_three_way_exit_property.py`` own the *verdict* mapping over an
  artifact (pass / regression / unavailable). This file stops at the artifact: it asserts
  that an incomplete run is not proof-grade and not proven, never which exit code that
  produces.
* ``tests/uplift/test_uplift_floor_data_gate.py`` owns the example-class facts about
  ``PoweredProof.from_payload`` / ``from_artifact`` -- a non-numeric, boolean, or non-finite
  headline yields no proof, an absent or malformed file yields no proof, and an omitted
  ``incomplete`` reads as ``True``. What this file adds is the *universal* claim over
  artifacts actually written by :meth:`UpliftArtifact.write`: ``from_artifact`` recovers the
  recorded headline, replicate count, completeness flag, and fidelity verdict exactly.
* ``tests/uplift/test_arm_aggregate_property.py`` owns the per-arm mean/std statistics. The
  aggregates here are generated values; their arithmetic is not re-asserted.

Honest scope boundary. ``PoweredProof.from_artifact`` reads raw JSON and consults only
``headline_uplift``, a replicate key, ``incomplete`` and ``fidelity.within_fidelity_bound``,
so it is *not* claimed here to reject a non-numeric ``kl_divergence`` -- it never looks at
one. The rejection asserted below is the artifact model's, which is what the gate's read
path (``uplift_truth._read_artifact``) and ``Admission.proof`` go through.

**The harness is never run (I-0).** Every artifact under test is constructed directly from
generated data: no twin, no arm, no ``ConsensusProtocol``, no subprocess, no socket, and no
``MIN_SCENARIOS``-scale replicate run -- a 1000-replicate-per-arm run belongs to the
scheduled ``.github/workflows/uplift.yml`` (task 10.5), never to this machine. The only I/O
is writing an artifact under a pytest temporary directory; the repo's
``artifacts/uplift/result.json`` is neither read nor written. Nothing here is slow-marked
because nothing here is slow.

``max_examples`` is never set -- the budget comes from the root ``conftest.py`` profiles
(``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000). No floor or tolerance
is introduced: every assertion is exact equality, and the power bar is read from
:data:`uplift.uplift_floor.MIN_POWERED_REPLICATES` and the floor from
:data:`uplift.uplift_floor.UPLIFT_FLOOR` rather than written as a literal.

**Validates: Requirements 2.3**
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
from typing import Any, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from uplift.contract import interval_verdict, load_contract
from uplift.harness import (
    ARTIFACT_SCHEMA_VERSION,
    KPI_FIELDS,
    NO_ESTIMATE_HEADLINE,
    POOLED_COMPARATOR_PREFIX,
    UNATTRIBUTED,
    ArmAggregate,
    ArtifactFidelity,
    ArtifactInterval,
    UpliftArtifact,
    UpliftProvenance,
)
from uplift.interfaces import ARM_ROLES, HEADLINE_VERDICTS, ArmRole, HeadlineVerdict
from uplift.interval import INTERVAL_SEED, METHOD, Interval
from uplift.uplift_floor import MIN_POWERED_REPLICATES, UPLIFT_FLOOR, PoweredProof, is_proven_uplift

# ---------------------------------------------------------------------------
# Generated vocabulary. Fixed ASCII alphabets (no newlines) so the canonical text is a
# single line and the "no indentation, no trailing newline" claim is assertable.
# ---------------------------------------------------------------------------
#: Every ``KpiVector`` field, so the aggregates carry the v2 fields (``avg_on_hand_units``,
#: ``objective``) as well as the six v1 ones.
_KPI_NAMES: Final[tuple[str, ...]] = tuple(sorted(KPI_FIELDS))
_ARM_NAMES: Final[tuple[str, ...]] = ("baseline-0", "baseline-1", "consensus", "par-level")
_SCENARIO_NAMES: Final[tuple[str, ...]] = ("cold-start-city", "festival-surge", "scenario-0")
_CONFIDENCES: Final[tuple[str, ...]] = ("high", "low", "medium", "unknown")

#: Revisions and run identifiers, including the honest :data:`UNATTRIBUTED` sentinel so the
#: unattributed artifact shape is generated as well as the attributed one.
_REVISIONS: Final[tuple[str, ...]] = ("0f1e2d3c4b5a", "9a8b7c6d5e4f", UNATTRIBUTED)
_RUN_IDS: Final[tuple[str, ...]] = ("run-20260101-01", "17351234567", UNATTRIBUTED)
_WRITTEN_AT: Final[tuple[str, ...]] = ("2026-01-01T00:00:00Z", "2026-02-03T04:05:06Z")
_STATEMENTS: Final[tuple[str, ...]] = (
    "bounded by twin fidelity",
    "KL divergence within the C34 re-sync threshold",
)

#: The committed Metric_Contract v2. The margin and the objective KPI are read through it --
#: never written here as literals.
_CONTRACT: Final = load_contract()
_MARGIN: Final[float] = _CONTRACT.materiality_margin
_OBJECTIVE: Final[str] = _CONTRACT.objective_kpi

#: Recorded comparators: two named arms and a pooled label (AD-16).
_COMPARATORS: Final[tuple[str, ...]] = (
    "baseline-0",
    "par-level",
    f"{POOLED_COMPARATOR_PREFIX}baseline-0,baseline-1,par-level",
)

_finite = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

#: Replicate counts straddling the INV-TW-002 power bar in both directions.
_replicates = st.one_of(
    st.integers(min_value=0, max_value=MIN_POWERED_REPLICATES - 1),
    st.integers(min_value=MIN_POWERED_REPLICATES, max_value=MIN_POWERED_REPLICATES * 3),
)

#: Interval bounds stay inside ``_finite``'s range.
_BOUND: Final[float] = 1e6
_positive = st.floats(min_value=0.0, max_value=_BOUND, exclude_min=True)
#: A strictly positive offset that moves any ``_BOUND``-range value to a different float.
_shifts = st.floats(min_value=1e-3, max_value=1e3, allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Specs: the logical value, held apart from any one construction of it, so the same
# artifact can be built two different ways and compared byte for byte.
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class _AggregateSpec:
    """One ``(scenario, arm)`` aggregate. KPI maps are ordered pairs, not dicts, so the
    insertion order a construction uses is part of the spec rather than an accident."""

    scenario: str
    arm: str
    completed: int
    failed: int
    kpi_mean: tuple[tuple[str, float], ...]
    kpi_std: tuple[tuple[str, float], ...]


@dataclasses.dataclass(frozen=True)
class _IntervalSpec:
    """One ``1 - alpha`` interval, held apart from either construction of it."""

    alpha: float
    resamples: int
    seed: int
    low: float
    high: float
    point: float

    def computed(self) -> Interval:
        """The computation form, which refuses a non-finite bound, ``low > high`` and a point
        outside the bounds -- so a spec that builds is an admissible interval."""
        return Interval(
            method=METHOD,
            alpha=self.alpha,
            resamples=self.resamples,
            seed=self.seed,
            low=self.low,
            high=self.high,
            point=self.point,
        )

    def payload(self) -> dict[str, Any]:
        """The plain mapping form, built here rather than read back off either model."""
        return {
            "alpha": self.alpha,
            "high": self.high,
            "low": self.low,
            "method": METHOD,
            "point": self.point,
            "resamples": self.resamples,
            "seed": self.seed,
        }


#: An interval and the verdict it was PLACED to license, or ``None`` for no estimate.
_Placement = tuple[HeadlineVerdict, _IntervalSpec] | None


@dataclasses.dataclass(frozen=True)
class _ArtifactSpec:
    """Every field of one logical :class:`~uplift.harness.UpliftArtifact`."""

    headline_uplift: float
    primary_kpi: str
    noise_tolerance_pp: float
    incomplete: bool
    all_wins_warning: bool
    replicates_per_arm: int
    kl_divergence: float | None
    threshold: float
    confidence: str
    within_fidelity_bound: bool | None
    fidelity_bound_statement: str
    arms: tuple[str, ...]
    #: Ordered pairs, like the KPI maps, so insertion order is part of the spec.
    arm_roles: tuple[tuple[str, ArmRole], ...]
    revision: str
    run_id: str
    seeds: tuple[int, ...]
    written_at: str
    aggregates: tuple[_AggregateSpec, ...]
    interval: _IntervalSpec | None
    headline_verdict: HeadlineVerdict | None
    materiality_margin: float
    comparator: str
    run_incomplete: bool


@st.composite
def _aggregate_specs(draw: st.DrawFn) -> _AggregateSpec:
    names = draw(st.lists(st.sampled_from(_KPI_NAMES), min_size=1, max_size=3, unique=True))
    means = draw(st.lists(_finite, min_size=len(names), max_size=len(names)))
    stds = draw(st.lists(_finite, min_size=len(names), max_size=len(names)))
    return _AggregateSpec(
        scenario=draw(st.sampled_from(_SCENARIO_NAMES)),
        arm=draw(st.sampled_from(_ARM_NAMES)),
        completed=draw(st.integers(min_value=0, max_value=2000)),
        failed=draw(st.integers(min_value=0, max_value=50)),
        kpi_mean=tuple(zip(names, means, strict=True)),
        # Reversed name order, so the two KPI maps of one aggregate disagree about
        # insertion order and only `sort_keys=True` can make them serialise stably.
        kpi_std=tuple(zip(reversed(names), stds, strict=True)),
    )


@st.composite
def _interval_specs(draw: st.DrawFn) -> tuple[HeadlineVerdict, _IntervalSpec]:
    """An interval PLACED to license a drawn verdict against the committed margin.

    Each placement is built from the rule's strict bounds, so the drawn verdict is an
    independent statement of what the artifact re-derives -- and the artifact refuses a
    stored verdict the rule does not produce, so every construction of a placed spec checks
    the two against each other. Both boundaries the strictness exists for are generated: a
    low bound exactly ON the margin is a sub-margin gain, never a win, and a bound exactly at
    zero is inconclusive.
    """
    verdict = draw(st.sampled_from(HEADLINE_VERDICTS))
    if verdict == "win":
        low = draw(st.floats(min_value=_MARGIN, max_value=_BOUND, exclude_min=True))
        high = draw(st.floats(min_value=low, max_value=_BOUND))
    elif verdict == "sub_margin_gain":
        low = draw(st.just(_MARGIN) | st.floats(min_value=0.0, max_value=_MARGIN, exclude_min=True))
        high = draw(st.floats(min_value=low, max_value=_BOUND))
    elif verdict == "inconclusive":
        low = draw(st.just(0.0) | st.floats(min_value=-_BOUND, max_value=0.0))
        high = draw(st.just(0.0) | st.floats(min_value=0.0, max_value=_BOUND))
    else:  # baseline_wins: the HIGH bound is strictly below zero
        high = -draw(_positive)
        low = draw(st.floats(min_value=-_BOUND, max_value=high))
    point = (
        low
        if low == high
        else draw(st.sampled_from((low, high)) | st.floats(min_value=low, max_value=high))
    )
    return verdict, _IntervalSpec(
        alpha=draw(st.floats(min_value=0.0, max_value=1.0, exclude_min=True, exclude_max=True)),
        resamples=draw(st.integers(min_value=1, max_value=10_000)),
        seed=draw(st.integers(min_value=0, max_value=2**32 - 1)),
        low=low,
        high=high,
        point=point,
    )


def _placed(spec: _ArtifactSpec, placement: _Placement) -> _ArtifactSpec:
    """``spec`` pinned to ``placement``: the headline is the interval's point and the verdict
    the one it was placed to license -- or, with no interval, the no-estimate state (no
    verdict, and the sentinel headline)."""
    if placement is None:
        return dataclasses.replace(
            spec, interval=None, headline_verdict=None, headline_uplift=NO_ESTIMATE_HEADLINE
        )
    verdict, interval = placement
    return dataclasses.replace(
        spec, interval=interval, headline_verdict=verdict, headline_uplift=interval.point
    )


def _fixed_placement(
    verdict: HeadlineVerdict, low: float, high: float, point: float
) -> tuple[HeadlineVerdict, _IntervalSpec]:
    return verdict, _IntervalSpec(
        alpha=_CONTRACT.alpha,
        resamples=_CONTRACT.resamples,
        seed=INTERVAL_SEED,
        low=low,
        high=high,
        point=point,
    )


#: One placement per verdict, as offsets from the committed margin. Two sit on a boundary the
#: strict rule exists for: a low bound ON the margin, and a low bound AT zero.
_FIXED_PLACEMENTS: Final[tuple[tuple[HeadlineVerdict, _IntervalSpec], ...]] = (
    _fixed_placement("win", 2.0 * _MARGIN, 3.0 * _MARGIN, 2.5 * _MARGIN),
    _fixed_placement("sub_margin_gain", _MARGIN, 2.0 * _MARGIN, 1.5 * _MARGIN),
    _fixed_placement("inconclusive", 0.0, _MARGIN, 0.5 * _MARGIN),
    _fixed_placement("baseline_wins", -2.0 * _MARGIN, -_MARGIN, -1.5 * _MARGIN),
)


#: The default placement mix: the no-estimate state or an interval placed to license a verdict.
#: A module-level strategy rather than a call in the default, so it is built once.
_PLACEMENTS: Final[st.SearchStrategy[_Placement]] = st.none() | _interval_specs()


@st.composite
def _artifact_specs(
    draw: st.DrawFn,
    placements: st.SearchStrategy[_Placement] = _PLACEMENTS,
) -> _ArtifactSpec:
    """An artifact spanning every honesty profile: complete/incomplete, powered/under-
    powered, fidelity available/unavailable/out-of-bound, attributed/unattributed -- and,
    under v2, every headline verdict and the no-estimate state, every arm role, a named or a
    pooled comparator, and the whole-run flag drawn independently of ``incomplete``."""
    replicates = draw(_replicates)
    arms = tuple(draw(st.lists(st.sampled_from(_ARM_NAMES), max_size=4)))
    unplaced = _ArtifactSpec(
        headline_uplift=NO_ESTIMATE_HEADLINE,
        primary_kpi=_OBJECTIVE,
        noise_tolerance_pp=draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False)),
        incomplete=draw(st.booleans()),
        all_wins_warning=draw(st.booleans()),
        replicates_per_arm=replicates,
        kl_divergence=draw(st.none() | _unit),
        threshold=draw(_unit),
        confidence=draw(st.sampled_from(_CONFIDENCES)),
        within_fidelity_bound=draw(st.sampled_from([True, False, None])),
        fidelity_bound_statement=draw(st.sampled_from(_STATEMENTS)),
        arms=arms,
        arm_roles=tuple((arm, draw(st.sampled_from(ARM_ROLES))) for arm in sorted(set(arms))),
        revision=draw(st.sampled_from(_REVISIONS)),
        run_id=draw(st.sampled_from(_RUN_IDS)),
        seeds=tuple(draw(st.lists(st.integers(min_value=0, max_value=2**32 - 1), max_size=5))),
        written_at=draw(st.sampled_from(_WRITTEN_AT)),
        aggregates=tuple(draw(st.lists(_aggregate_specs(), max_size=3))),
        interval=None,
        headline_verdict=None,
        materiality_margin=_MARGIN,
        comparator=draw(st.sampled_from(_COMPARATORS)),
        run_incomplete=draw(st.booleans()),
    )
    return _placed(unplaced, draw(placements))


def _proof_grade(spec: _ArtifactSpec) -> _ArtifactSpec:
    """The same spec repaired into a completed, powered, in-bound, attributed run.

    The non-vacuity companion to the rejection assertions: if nothing were ever accepted,
    "an incomplete run is not proof-grade" would be true for the wrong reason. Under v2 the
    repaired headline is the point of a point-mass interval at the contract's ``alpha``, and
    its verdict is the one the committed rule derives from those bounds.
    """
    headline = max(abs(spec.headline_uplift), UPLIFT_FLOOR) + 1.0
    interval = _IntervalSpec(
        alpha=_CONTRACT.alpha,
        resamples=_CONTRACT.resamples,
        seed=INTERVAL_SEED,
        low=headline,
        high=headline,
        point=headline,
    )
    repaired = _placed(spec, (interval_verdict(headline, headline, margin=_MARGIN), interval))
    return dataclasses.replace(
        repaired,
        incomplete=False,
        replicates_per_arm=MIN_POWERED_REPLICATES,
        kl_divergence=spec.threshold,
        within_fidelity_bound=True,
        revision=_REVISIONS[0],
        run_id=_RUN_IDS[0],
    )


# ---------------------------------------------------------------------------
# Two independent constructions of one logical artifact
# ---------------------------------------------------------------------------
def _build(spec: _ArtifactSpec) -> UpliftArtifact:
    """Construct through the model's keyword surface, letting the digest be derived.

    The interval takes the harness's path: computation form first, then
    :meth:`ArtifactInterval.from_interval`.
    """
    return UpliftArtifact(
        schema_version=ARTIFACT_SCHEMA_VERSION,
        headline_uplift=spec.headline_uplift,
        primary_kpi=spec.primary_kpi,
        noise_tolerance_pp=spec.noise_tolerance_pp,
        incomplete=spec.incomplete,
        all_wins_warning=spec.all_wins_warning,
        replicates_per_arm=spec.replicates_per_arm,
        interval=(
            None
            if spec.interval is None
            else ArtifactInterval.from_interval(spec.interval.computed())
        ),
        headline_verdict=spec.headline_verdict,
        materiality_margin=spec.materiality_margin,
        comparator=spec.comparator,
        run_incomplete=spec.run_incomplete,
        fidelity=ArtifactFidelity(
            kl_divergence=spec.kl_divergence,
            threshold=spec.threshold,
            confidence=spec.confidence,
            within_fidelity_bound=spec.within_fidelity_bound,
            fidelity_bound_statement=spec.fidelity_bound_statement,
        ),
        provenance=UpliftProvenance(
            arms=spec.arms,
            arm_roles=dict(spec.arm_roles),
            replicates_per_arm=spec.replicates_per_arm,
            revision=spec.revision,
            run_id=spec.run_id,
            seeds=spec.seeds,
            written_at=spec.written_at,
        ),
        arm_aggregates=tuple(
            ArmAggregate(
                scenario=aggregate.scenario,
                arm=aggregate.arm,
                completed=aggregate.completed,
                failed=aggregate.failed,
                kpi_mean=dict(aggregate.kpi_mean),
                kpi_std=dict(aggregate.kpi_std),
            )
            for aggregate in spec.aggregates
        ),
    )


def _reversed_keys(mapping: dict[str, Any]) -> dict[str, Any]:
    """The same mapping with its key insertion order reversed."""
    return dict(reversed(list(mapping.items())))


def _aggregate_payload(spec: _AggregateSpec, *, reverse: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "arm": spec.arm,
        "completed": spec.completed,
        "failed": spec.failed,
        "kpi_mean": dict(reversed(spec.kpi_mean) if reverse else spec.kpi_mean),
        "kpi_std": dict(reversed(spec.kpi_std) if reverse else spec.kpi_std),
        "scenario": spec.scenario,
    }
    return _reversed_keys(payload) if reverse else payload


def _payload(spec: _ArtifactSpec, *, reverse: bool = False) -> dict[str, Any]:
    """The plain mapping form of ``spec``, optionally with every mapping key-reversed.

    ``arm_aggregates_digest`` is deliberately absent so the model derives it, exactly as
    it does for the keyword construction -- the two paths must agree on the derivation.
    List order is never reversed: the aggregate *sequence* is recorded data, while a
    mapping's key order is not.
    """
    fidelity: dict[str, Any] = {
        "confidence": spec.confidence,
        "fidelity_bound_statement": spec.fidelity_bound_statement,
        "kl_divergence": spec.kl_divergence,
        "threshold": spec.threshold,
        "within_fidelity_bound": spec.within_fidelity_bound,
    }
    provenance: dict[str, Any] = {
        "arm_roles": dict(reversed(spec.arm_roles) if reverse else spec.arm_roles),
        "arms": list(spec.arms),
        "replicates_per_arm": spec.replicates_per_arm,
        "revision": spec.revision,
        "run_id": spec.run_id,
        "seeds": list(spec.seeds),
        "written_at": spec.written_at,
    }
    interval = None if spec.interval is None else spec.interval.payload()
    payload: dict[str, Any] = {
        "all_wins_warning": spec.all_wins_warning,
        "arm_aggregates": [
            _aggregate_payload(aggregate, reverse=reverse) for aggregate in spec.aggregates
        ],
        "comparator": spec.comparator,
        "fidelity": _reversed_keys(fidelity) if reverse else fidelity,
        "headline_uplift": spec.headline_uplift,
        "headline_verdict": spec.headline_verdict,
        "incomplete": spec.incomplete,
        "interval": _reversed_keys(interval) if reverse and interval is not None else interval,
        "materiality_margin": spec.materiality_margin,
        "noise_tolerance_pp": spec.noise_tolerance_pp,
        "primary_kpi": spec.primary_kpi,
        "provenance": _reversed_keys(provenance) if reverse else provenance,
        "replicates_per_arm": spec.replicates_per_arm,
        "run_incomplete": spec.run_incomplete,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
    }
    return _reversed_keys(payload) if reverse else payload


# ---------------------------------------------------------------------------
# Independent oracles: the canonical convention and the aggregate digest, restated with
# stdlib only, never by calling `uplift.harness.canonical_json` / `arm_aggregates_digest`.
# ---------------------------------------------------------------------------
def _canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _expected_digest(spec: _ArtifactSpec) -> str:
    ordered = sorted(spec.aggregates, key=lambda aggregate: (aggregate.scenario, aggregate.arm))
    return hashlib.sha256(
        _canonical(
            [
                {
                    "arm": aggregate.arm,
                    "completed": aggregate.completed,
                    "failed": aggregate.failed,
                    "kpi_mean": dict(aggregate.kpi_mean),
                    "kpi_std": dict(aggregate.kpi_std),
                    "scenario": aggregate.scenario,
                }
                for aggregate in ordered
            ]
        ).encode("utf-8")
    ).hexdigest()


def _keys_are_sorted(value: Any) -> bool:
    """Whether every mapping in ``value``, at every depth, has keys in sorted order."""
    if isinstance(value, dict):
        keys = list(value)
        return keys == sorted(keys) and all(_keys_are_sorted(item) for item in value.values())
    if isinstance(value, list):
        return all(_keys_are_sorted(item) for item in value)
    return True


# ---------------------------------------------------------------------------
# Rejection corpus: every way an artifact can fail to say what it means. `_DELETE` removes
# the key entirely (an absent field is not the same as a null one).
# ---------------------------------------------------------------------------
_DELETE: Final = object()

#: ``(label, path, value)``. Only values pydantic cannot lawfully coerce are listed -- a
#: string ``"0.1"`` for a float, or ``"yes"`` for a bool, ARE coercions the model performs
#: by design, so asserting they are rejected would be asserting a falsehood.
_REJECTED: Final[tuple[tuple[str, tuple[str, ...], object], ...]] = (
    ("a NaN headline_uplift", ("headline_uplift",), float("nan")),
    ("an infinite headline_uplift", ("headline_uplift",), float("inf")),
    ("a negatively infinite headline_uplift", ("headline_uplift",), float("-inf")),
    ("a non-numeric headline_uplift", ("headline_uplift",), "three"),
    ("a null headline_uplift", ("headline_uplift",), None),
    ("an absent headline_uplift", ("headline_uplift",), _DELETE),
    ("a non-numeric kl_divergence", ("fidelity", "kl_divergence"), "unknown"),
    ("a listed kl_divergence", ("fidelity", "kl_divergence"), [0.1]),
    ("a mapped kl_divergence", ("fidelity", "kl_divergence"), {"value": 0.1}),
    ("a NaN kl_divergence", ("fidelity", "kl_divergence"), float("nan")),
    ("an infinite kl_divergence", ("fidelity", "kl_divergence"), float("inf")),
    ("an absent kl_divergence", ("fidelity", "kl_divergence"), _DELETE),
    ("a non-boolean incomplete", ("incomplete",), "maybe"),
    ("an out-of-range integral incomplete", ("incomplete",), 2),
    ("a null incomplete", ("incomplete",), None),
    ("an absent incomplete", ("incomplete",), _DELETE),
    ("a non-boolean within_fidelity_bound", ("fidelity", "within_fidelity_bound"), 2),
    ("an absent within_fidelity_bound", ("fidelity", "within_fidelity_bound"), _DELETE),
    ("an absent provenance record", ("provenance",), _DELETE),
    ("an absent seed set", ("provenance", "seeds"), _DELETE),
    ("an absent arm identifier set", ("provenance", "arms"), _DELETE),
    ("an absent run identifier", ("provenance", "run_id"), _DELETE),
    ("an absent source revision", ("provenance", "revision"), _DELETE),
    ("an empty source revision", ("provenance", "revision"), ""),
    ("an unknown top-level field", ("synapse_headline",), 1.0),
    ("an unknown fidelity field", ("fidelity", "kl"), 0.1),
    ("an unknown provenance field", ("provenance", "operator"), "an operator"),
    ("a restated arm_aggregates_digest", ("arm_aggregates_digest",), "0" * 64),
    # -- Metric_Contract v2 (task 15.1): valid against any spec, interval or none ----------
    ("a version-1 payload", ("schema_version",), 1),
    ("a future schema_version", ("schema_version",), ARTIFACT_SCHEMA_VERSION + 1),
    ("a non-numeric schema_version", ("schema_version",), "two"),
    ("a null schema_version", ("schema_version",), None),
    ("an absent schema_version", ("schema_version",), _DELETE),
    ("the version-1 headline KPI", ("primary_kpi",), "fill_rate"),
    ("an absent interval block", ("interval",), _DELETE),
    ("an absent headline_verdict", ("headline_verdict",), _DELETE),
    ("an undeclared headline_verdict", ("headline_verdict",), "material"),
    ("an absent materiality_margin", ("materiality_margin",), _DELETE),
    ("a zero materiality_margin", ("materiality_margin",), 0.0),
    ("a negated materiality_margin", ("materiality_margin",), -_MARGIN),
    ("a NaN materiality_margin", ("materiality_margin",), float("nan")),
    ("an infinite materiality_margin", ("materiality_margin",), float("inf")),
    ("an absent comparator", ("comparator",), _DELETE),
    ("an empty comparator", ("comparator",), ""),
    ("an absent run_incomplete", ("run_incomplete",), _DELETE),
    ("a non-boolean run_incomplete", ("run_incomplete",), "maybe"),
    ("an absent arm_roles record", ("provenance", "arm_roles"), _DELETE),
    ("a role for an unregistered arm", ("provenance", "arm_roles", "ghost-arm"), "baseline"),
)

#: Corruptions inside the interval block, so only meaningful against a spec that has one.
_REJECTED_INSIDE_INTERVAL: Final[tuple[tuple[str, tuple[str, ...], object], ...]] = (
    ("an unknown interval field", ("interval", "width"), 1.0),
    ("an absent interval point", ("interval", "point"), _DELETE),
    ("an absent interval method", ("interval", "method"), _DELETE),
    ("an absent interval seed", ("interval", "seed"), _DELETE),
    ("a NaN interval low bound", ("interval", "low"), float("nan")),
    ("an infinite interval high bound", ("interval", "high"), float("inf")),
    ("a non-numeric interval resample count", ("interval", "resamples"), "many"),
    ("a null interval alpha", ("interval", "alpha"), None),
)


def _corrupt(payload: dict[str, Any], path: tuple[str, ...], value: object) -> dict[str, Any]:
    corrupted = copy.deepcopy(payload)
    target: Any = corrupted
    for key in path[:-1]:
        target = target[key]
    if value is _DELETE:
        target.pop(path[-1], None)
    else:
        target[path[-1]] = value
    return corrupted


def _assert_rejected(label: str, corrupted: dict[str, Any]) -> None:
    """Both artifact readers must refuse ``corrupted`` rather than coerce it.

    ``model_validate`` is the mapping path and ``from_canonical_json`` is the text path
    :meth:`UpliftArtifact.read` -- and therefore ``uplift_truth._read_artifact`` -- takes.
    """
    try:
        UpliftArtifact.model_validate(corrupted)
    except ValidationError:
        pass
    else:
        pytest.fail(f"{label} was accepted by UpliftArtifact.model_validate")

    try:
        UpliftArtifact.from_canonical_json(json.dumps(corrupted))
    except ValidationError:
        pass
    else:
        pytest.fail(f"{label} was accepted by UpliftArtifact.from_canonical_json")


# ---------------------------------------------------------------------------
# Property 14 -- lossless
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs())
def test_every_recorded_field_survives_the_canonical_round_trip(spec: _ArtifactSpec) -> None:
    """Serialise, parse, and every field -- and every derived predicate -- is recovered."""
    artifact = _build(spec)
    text = artifact.to_canonical_json()
    parsed = UpliftArtifact.from_canonical_json(text)

    assert parsed == artifact
    # Byte-level idempotence: re-serialising the parsed value reproduces the same bytes.
    assert parsed.to_canonical_json() == text

    assert parsed.headline_uplift == artifact.headline_uplift
    assert math.isfinite(parsed.headline_uplift)
    assert parsed.primary_kpi == artifact.primary_kpi == _OBJECTIVE
    assert parsed.noise_tolerance_pp == artifact.noise_tolerance_pp
    assert parsed.incomplete is artifact.incomplete
    assert parsed.all_wins_warning is artifact.all_wins_warning
    assert parsed.replicates_per_arm == artifact.replicates_per_arm

    assert parsed.fidelity == artifact.fidelity
    assert parsed.fidelity.kl_divergence == artifact.fidelity.kl_divergence
    assert parsed.fidelity.threshold == artifact.fidelity.threshold
    assert parsed.fidelity.confidence == artifact.fidelity.confidence
    assert parsed.fidelity.within_fidelity_bound is artifact.fidelity.within_fidelity_bound
    assert parsed.fidelity.fidelity_bound_statement == artifact.fidelity.fidelity_bound_statement

    # R2.3's provenance record: run identifier, source revision, seed set, arm identifiers.
    assert parsed.provenance == artifact.provenance
    assert parsed.provenance.run_id == artifact.provenance.run_id
    assert parsed.provenance.revision == artifact.provenance.revision
    assert parsed.provenance.seeds == artifact.provenance.seeds
    assert parsed.provenance.arms == artifact.provenance.arms
    assert parsed.provenance.replicates_per_arm == artifact.provenance.replicates_per_arm
    assert parsed.provenance.written_at == artifact.provenance.written_at
    assert parsed.provenance.to_canonical_json() == artifact.provenance.to_canonical_json()
    assert parsed.provenance.is_attributed is artifact.provenance.is_attributed
    assert parsed.provenance.arm_roles == artifact.provenance.arm_roles == dict(spec.arm_roles)

    assert parsed.arm_aggregates == artifact.arm_aggregates
    assert parsed.arm_aggregates_digest == artifact.arm_aggregates_digest
    assert parsed.arm_aggregates_digest == _expected_digest(spec)

    # v2: the six new fields, the interval's seven recorded fields, and the headline pin.
    assert parsed.schema_version == artifact.schema_version == ARTIFACT_SCHEMA_VERSION
    assert parsed.interval == artifact.interval
    expected_interval = None if spec.interval is None else spec.interval.computed().as_dict()
    assert (None if parsed.interval is None else parsed.interval.model_dump()) == (
        expected_interval
    )
    assert parsed.headline_uplift == (
        NO_ESTIMATE_HEADLINE if parsed.interval is None else parsed.interval.point
    )
    assert parsed.headline_verdict == artifact.headline_verdict == spec.headline_verdict
    assert parsed.materiality_margin == artifact.materiality_margin == _MARGIN
    assert parsed.comparator == artifact.comparator == spec.comparator
    assert parsed.run_incomplete is artifact.run_incomplete is spec.run_incomplete

    # The derived predicates the gate reads are recovered, not recomputed differently.
    assert parsed.unavailable_reasons == artifact.unavailable_reasons
    assert parsed.is_proof_grade is artifact.is_proof_grade
    assert parsed.as_powered_proof() == artifact.as_powered_proof()


# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs())
def test_the_wire_key_set_is_exactly_the_declared_field_set(spec: _ArtifactSpec) -> None:
    """No declared field is omitted from the artifact and no undeclared field is admitted."""
    text = _build(spec).to_canonical_json()
    on_the_wire = json.loads(text)

    assert isinstance(on_the_wire, dict)
    assert tuple(sorted(on_the_wire)) == tuple(sorted(UpliftArtifact.model_fields))
    assert tuple(sorted(on_the_wire["fidelity"])) == tuple(sorted(ArtifactFidelity.model_fields))
    assert tuple(sorted(on_the_wire["provenance"])) == tuple(sorted(UpliftProvenance.model_fields))
    for aggregate in on_the_wire["arm_aggregates"]:
        assert tuple(sorted(aggregate)) == tuple(sorted(ArmAggregate.model_fields))

    # v2: the interval block declares exactly the computation form's seven fields, so no
    # recorded interval field can be dropped on the way to the artifact, and the role map
    # is keyed by exactly the registered arms.
    assert tuple(sorted(ArtifactInterval.model_fields)) == tuple(
        sorted(field.name for field in dataclasses.fields(Interval))
    )
    expected_interval_keys = (
        () if spec.interval is None else tuple(sorted(ArtifactInterval.model_fields))
    )
    assert tuple(sorted(on_the_wire["interval"] or {})) == expected_interval_keys
    assert tuple(sorted(on_the_wire["provenance"]["arm_roles"])) == tuple(sorted(set(spec.arms)))


# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs())
def test_each_headline_verdict_and_the_no_estimate_state_round_trip_byte_for_byte(
    spec: _ArtifactSpec,
) -> None:
    """Every verdict v2 can record, and the honest no-estimate state, survives the trip.

    The placements are fixed, so every example exercises all five states rather than
    whichever the generator drew -- and the fixture is asserted to hold all four verdicts.
    """
    assert {verdict for verdict, _interval in _FIXED_PLACEMENTS} == set(HEADLINE_VERDICTS)
    for placement in (*_FIXED_PLACEMENTS, None):
        artifact = _build(_placed(spec, placement))
        text = artifact.to_canonical_json()
        parsed = UpliftArtifact.from_canonical_json(text)

        assert parsed == artifact
        assert parsed.to_canonical_json() == text
        assert (parsed.interval is None) is (placement is None)
        assert parsed.headline_verdict == (None if placement is None else placement[0])
        assert parsed.headline_uplift == (
            NO_ESTIMATE_HEADLINE if placement is None else placement[1].point
        )


# ---------------------------------------------------------------------------
# Property 14 -- canonical
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs())
def test_the_serialised_bytes_are_sorted_and_compact_at_every_depth(spec: _ArtifactSpec) -> None:
    """The artifact's bytes are the repo-canonical form, re-derived here with stdlib only."""
    text = _build(spec).to_canonical_json()

    assert text == _canonical(json.loads(text))
    assert _keys_are_sorted(json.loads(text))
    # Compact separators: no space after a comma or a colon anywhere.
    assert ", " not in text
    assert '": ' not in text
    # A single line: no indentation and no trailing newline (a diff of two artifacts is a
    # diff of their measurements, never of their formatting).
    assert "\n" not in text
    assert text == text.strip()


# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs())
def test_two_constructions_of_one_logical_artifact_are_byte_identical(
    spec: _ArtifactSpec,
) -> None:
    """Keyword construction and key-reversed payload validation produce the same bytes.

    This is the guarantee R2.5 rests on, stated at the artifact level: two constructions of
    one logical measurement cannot differ byte-wise for a reason that is not a measurement.
    """
    keyword_built = _build(spec)
    payload_built = UpliftArtifact.model_validate(_payload(spec, reverse=True))
    plain_built = UpliftArtifact.model_validate(_payload(spec))

    assert keyword_built == payload_built == plain_built
    text = keyword_built.to_canonical_json()
    assert payload_built.to_canonical_json() == text
    assert plain_built.to_canonical_json() == text
    # The derived aggregate digest is order-independent too, and equals the stdlib recompute.
    assert payload_built.arm_aggregates_digest == _expected_digest(spec)


# ---------------------------------------------------------------------------
# Property 14 -- the persisted file and the proof the gate reads off it
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs())
def test_from_artifact_recovers_exactly_the_recorded_fields(
    spec: _ArtifactSpec, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A written artifact re-reads as itself, and ``PoweredProof`` recovers its fields."""
    artifact = _build(spec)
    path = artifact.write(tmp_path_factory.mktemp("uplift-artifact") / "result.json")

    # The file bytes are exactly the canonical form -- nothing added on the way to disk.
    assert path.read_bytes() == artifact.to_canonical_json().encode("utf-8")
    assert UpliftArtifact.read(path) == artifact

    proof = PoweredProof.from_artifact(path)
    assert proof is not None
    assert proof.headline_uplift == artifact.headline_uplift
    assert proof.replicates == artifact.replicates_per_arm
    assert proof.incomplete is artifact.incomplete
    assert proof.within_fidelity_bound is artifact.fidelity.within_fidelity_bound
    # The file-backed reader and the in-memory reader are one implementation.
    assert proof == artifact.as_powered_proof()
    # Power is read from the recorded count, restated independently of `is_powered`.
    assert proof.is_powered == (artifact.replicates_per_arm >= MIN_POWERED_REPLICATES)


# ---------------------------------------------------------------------------
# Property 14 -- rejected, not coerced
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs(), corruption=st.sampled_from(_REJECTED))
def test_an_unsayable_artifact_is_rejected_rather_than_coerced(
    spec: _ArtifactSpec, corruption: tuple[str, tuple[str, ...], object]
) -> None:
    """Every listed malformation is refused by the model the C60 gate reads through."""
    label, path, value = corruption
    payload = _payload(spec)

    # Non-vacuity: the uncorrupted payload is accepted, so the rejections below are
    # discriminating rather than a model that refuses everything.
    assert UpliftArtifact.model_validate(payload) == _build(spec)

    _assert_rejected(label, _corrupt(payload, path, value))


# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(
    spec=_artifact_specs(placements=_interval_specs()),
    corruption=st.sampled_from(_REJECTED_INSIDE_INTERVAL),
    shift=_shifts,
)
def test_an_unsayable_interval_block_is_rejected_rather_than_coerced(
    spec: _ArtifactSpec, corruption: tuple[str, tuple[str, ...], object], shift: float
) -> None:
    """An unknown key, a missing or non-finite field, an inverted interval, and one that
    does not bracket its own point are each refused inside the interval block (task 15.1)."""
    label, path, value = corruption
    interval = spec.interval
    assert interval is not None
    payload = _payload(spec)
    assert UpliftArtifact.model_validate(payload) == _build(spec)

    _assert_rejected(label, _corrupt(payload, path, value))

    beyond = interval.high + shift
    assert beyond > interval.high
    _assert_rejected("an inverted interval", _corrupt(payload, ("interval", "low"), beyond))
    # The headline moves with the point, so the missed bracket is the only defect left.
    unbracketed = _corrupt(
        _corrupt(payload, ("interval", "point"), beyond), ("headline_uplift",), beyond
    )
    _assert_rejected("an interval that does not bracket its point", unbracketed)


# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs(placements=_interval_specs()), shift=_shifts)
def test_a_verdict_or_headline_the_interval_does_not_license_is_refused(
    spec: _ArtifactSpec, shift: float
) -> None:
    """The verdict is re-derived and the headline pinned, so neither can be restated.

    Every verdict other than the one the committed rule derives from the stored bounds --
    ``None`` included -- is refused; so is a headline that is not the interval's point, and
    so is a verdict left standing after its interval is removed.
    """
    payload = _payload(spec)
    assert UpliftArtifact.model_validate(payload) == _build(spec)

    wrong = [verdict for verdict in (*HEADLINE_VERDICTS, None) if verdict != spec.headline_verdict]
    assert len(wrong) == len(HEADLINE_VERDICTS)
    for verdict in wrong:
        _assert_rejected(
            f"a stored {verdict!r} verdict", _corrupt(payload, ("headline_verdict",), verdict)
        )

    moved = spec.headline_uplift + shift
    assert moved != spec.headline_uplift
    _assert_rejected(
        "a headline off the interval point", _corrupt(payload, ("headline_uplift",), moved)
    )

    orphaned = _corrupt(
        _corrupt(payload, ("interval",), None), ("headline_uplift",), NO_ESTIMATE_HEADLINE
    )
    _assert_rejected("a verdict with no interval behind it", orphaned)


# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs())
def test_incomplete_true_round_trips_as_true_and_is_never_proof_grade(
    spec: _ArtifactSpec,
) -> None:
    """``incomplete: true`` is preserved exactly and rejected as proof, never coerced.

    I-7: an artifact must be able to state that its run did not complete. What must never
    happen is the flag arriving as ``false`` on the other side of the round trip, or an
    incomplete run reading as a proven measurement.
    """
    incomplete = _build(dataclasses.replace(spec, incomplete=True))
    parsed = UpliftArtifact.from_canonical_json(incomplete.to_canonical_json())

    assert parsed.incomplete is True
    assert json.loads(parsed.to_canonical_json())["incomplete"] is True
    assert parsed.is_proof_grade is False
    assert any("incomplete" in reason for reason in parsed.unavailable_reasons)

    proof = parsed.as_powered_proof()
    assert proof is not None
    assert proof.incomplete is True
    assert is_proven_uplift(proof, UPLIFT_FLOOR) is False

    # The discriminating converse: repaired into a completed, powered, in-bound, attributed
    # run with a positive headline, the same spec IS proof-grade and IS proven.
    repaired = _build(_proof_grade(spec))
    assert repaired.incomplete is False
    assert repaired.unavailable_reasons == ()
    assert repaired.is_proof_grade is True
    assert is_proven_uplift(repaired.as_powered_proof(), UPLIFT_FLOOR) is True

    # ... and the whole-run flag is not an unavailable reason: admissibility reads the
    # contrast predicate ``incomplete`` (task 15.5), so an arm outside the contrast that
    # failed a replicate cannot make the consensus contrast inadmissible.
    whole_run = _build(dataclasses.replace(_proof_grade(spec), run_incomplete=True))
    assert whole_run.unavailable_reasons == ()
    assert whole_run.is_proof_grade is True


# Feature: purpose-achievement-audit, Property 14: The uplift artifact round-trips
# losslessly and canonically
@given(spec=_artifact_specs())
def test_an_artifact_with_no_interval_says_so_and_is_never_proof_grade(
    spec: _ArtifactSpec,
) -> None:
    """I-7: "no interval was estimated" is an honest, first-class state -- never proof.

    The repaired, otherwise proof-grade run is stripped of its interval: it is accepted, it
    round-trips exactly, the absence is its one and only unavailable reason, and it is not
    proof-grade. The same run WITH its interval is proof-grade, so the absence alone is
    what refuses it.
    """
    estimated = _proof_grade(spec)
    unestimated = _build(_placed(estimated, None))
    parsed = UpliftArtifact.from_canonical_json(unestimated.to_canonical_json())

    assert parsed == unestimated
    assert parsed.interval is None
    assert parsed.headline_verdict is None
    assert parsed.headline_uplift == NO_ESTIMATE_HEADLINE
    assert parsed.is_proof_grade is False
    assert len(parsed.unavailable_reasons) == 1
    assert "no interval was estimated" in parsed.unavailable_reasons[0]
    assert _build(estimated).is_proof_grade is True
