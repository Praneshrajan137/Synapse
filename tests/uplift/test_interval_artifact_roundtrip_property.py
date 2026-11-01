# Feature: decision-quality-proof, Property 82: An interval-carrying artifact round-trips
# canonically and leaves the aggregate digest unchanged
"""An interval inside the byte-pinned artifact round-trips, and moves nothing it must not.

Task 15.4 (R7.17), for task 15.1's schema change (AD-15). Subject: ``uplift/harness.py`` --
:class:`~uplift.harness.ArtifactInterval` and the schema-version-2 fields of
:class:`~uplift.harness.UpliftArtifact`.

**The digest clause is the load-bearing half.** AD-15 is affordable for exactly one reason:
``arm_aggregates_digest`` is SHA-256 over the arm aggregates ALONE, so an interval block leaves
it byte-identical and predecessor Property 15 (cross-process byte identity, R6.11) does not
move. That claim is asserted here, across interval values and across interval presence or
absence, against a digest recomputed with stdlib ``hashlib`` and ``json`` from the generated
aggregates -- never by calling the harness's own digest function, which would compare the
subject with itself.

**Clauses, each asserted unconditionally.**

1. The canonical round trip is byte-identical, and the canonical form is re-derived with a
   plain ``json.dumps(obj, sort_keys=True, separators=(',',':'))``.
2. ``arm_aggregates_digest`` is unchanged across interval values and across presence or
   absence -- while the canonical bytes DO change, so the block is carried, not dropped.
3. An unknown key inside ``interval`` is refused, by the mapping reader and the text reader.
4. ``schema_version`` 1 is refused -- and so is every other value that is not the integer 2,
   and a payload shaped like a real version-1 artifact.
5. ``point != headline_uplift`` is refused, at one ulp; with no interval, a headline other than
   the no-estimate sentinel is refused.
6. A stored verdict the rule does not produce is refused, as is an interval without a verdict
   or a verdict without an interval.
7. With the interval ``None``, ``unavailable_reasons`` names the absence and ``is_proof_grade``
   is ``False`` -- and the SAME artifact carrying an interval is proof-grade, so the absence is
   what refuses it.
8. The :class:`ArtifactInterval` field names equal :class:`~uplift.interval.Interval`'s, the
   conversion is lossless both ways, and every interval the estimator's record refuses is
   refused by the persisted form too.

**Pure.** Every artifact is constructed from generated data: no twin, no arm, no
``ConsensusProtocol``, no subprocess, no file. Budget inherited from ``HYPOTHESIS_PROFILE``;
no ``max_examples`` literal. Locus: ``ci.yml::uplift-verify`` fast step.
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

from uplift.contract import OBJECTIVE_KPI, interval_verdict
from uplift.harness import (
    ARTIFACT_SCHEMA_VERSION,
    NO_ESTIMATE_HEADLINE,
    UNATTRIBUTED,
    ArmAggregate,
    ArtifactFidelity,
    ArtifactInterval,
    UpliftArtifact,
    UpliftProvenance,
)
from uplift.interfaces import ARM_ROLES, HEADLINE_VERDICTS, ArmRole
from uplift.interval import METHOD, Interval, IntervalUnavailableError
from uplift.uplift_floor import MIN_POWERED_REPLICATES

# ---------------------------------------------------------------------------
# Generated vocabulary
# ---------------------------------------------------------------------------
_FINITE = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_ALPHAS = st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False)
_MARGINS = st.floats(min_value=1e-6, max_value=100.0, allow_nan=False, allow_infinity=False)
_UNIT = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_ARM_NAMES: Final[tuple[str, ...]] = (
    "Par_Level_Reorder",
    "consensus",
    "greedy_routing",
    "oracle_structure_aware",
)
_SCENARIO_NAMES: Final[tuple[str, ...]] = ("cold-start-city", "demand-spike", "supplier-default")
_KPI_NAMES: Final[tuple[str, ...]] = ("avg_on_hand_units", "fill_rate", "objective", "margin")
_COMPARATORS: Final[tuple[str, ...]] = (
    "Par_Level_Reorder",
    "pooled:Par_Level_Reorder,greedy_routing",
)
_ATTRIBUTED_REVISION: Final[str] = "0f1e2d3c4b5a"
_ATTRIBUTED_RUN_ID: Final[str] = "run-20261001-01"

#: The seven field names design E3.1 declares for the interval, restated rather than read off
#: either class, so the two classes cannot drift TOGETHER and still pass.
_DECLARED_INTERVAL_FIELDS: Final[frozenset[str]] = frozenset(
    {"method", "alpha", "resamples", "seed", "low", "high", "point"}
)


@dataclasses.dataclass(frozen=True)
class _Aggregate:
    """One ``(scenario, arm)`` aggregate, held apart from the model that records it."""

    scenario: str
    arm: str
    completed: int
    failed: int
    kpi_mean: tuple[tuple[str, float], ...]
    kpi_std: tuple[tuple[str, float], ...]


@dataclasses.dataclass(frozen=True)
class _Spec:
    """Every field of one artifact EXCEPT the interval, its headline and its verdict."""

    noise_tolerance_pp: float
    incomplete: bool
    run_incomplete: bool
    all_wins_warning: bool
    replicates_per_arm: int
    kl_divergence: float | None
    threshold: float
    within_fidelity_bound: bool | None
    roles: tuple[tuple[str, ArmRole], ...]
    revision: str
    run_id: str
    seeds: tuple[int, ...]
    comparator: str
    materiality_margin: float
    aggregates: tuple[_Aggregate, ...]


@st.composite
def _aggregates(draw: st.DrawFn) -> _Aggregate:
    names = draw(st.lists(st.sampled_from(_KPI_NAMES), min_size=1, max_size=3, unique=True))
    means = draw(st.lists(_FINITE, min_size=len(names), max_size=len(names)))
    stds = draw(st.lists(_FINITE, min_size=len(names), max_size=len(names)))
    return _Aggregate(
        scenario=draw(st.sampled_from(_SCENARIO_NAMES)),
        arm=draw(st.sampled_from(_ARM_NAMES)),
        completed=draw(st.integers(min_value=0, max_value=2000)),
        failed=draw(st.integers(min_value=0, max_value=50)),
        kpi_mean=tuple(zip(names, means, strict=True)),
        kpi_std=tuple(zip(reversed(names), stds, strict=True)),
    )


@st.composite
def _specs(draw: st.DrawFn) -> _Spec:
    """An artifact spanning every honesty profile the gate distinguishes."""
    replicates = draw(
        st.one_of(
            st.integers(min_value=0, max_value=MIN_POWERED_REPLICATES - 1),
            st.integers(min_value=MIN_POWERED_REPLICATES, max_value=3 * MIN_POWERED_REPLICATES),
        )
    )
    arms = draw(st.lists(st.sampled_from(_ARM_NAMES), max_size=4, unique=True))
    return _Spec(
        noise_tolerance_pp=draw(_UNIT),
        incomplete=draw(st.booleans()),
        run_incomplete=draw(st.booleans()),
        all_wins_warning=draw(st.booleans()),
        replicates_per_arm=replicates,
        kl_divergence=draw(st.none() | _UNIT),
        threshold=draw(_UNIT),
        within_fidelity_bound=draw(st.sampled_from([True, False, None])),
        roles=tuple((arm, draw(st.sampled_from(ARM_ROLES))) for arm in arms),
        revision=draw(st.sampled_from((_ATTRIBUTED_REVISION, UNATTRIBUTED))),
        run_id=draw(st.sampled_from((_ATTRIBUTED_RUN_ID, UNATTRIBUTED))),
        seeds=tuple(draw(st.lists(st.integers(min_value=0, max_value=2**32 - 1), max_size=4))),
        comparator=draw(st.sampled_from(_COMPARATORS)),
        materiality_margin=draw(_MARGINS),
        aggregates=tuple(
            draw(
                st.lists(
                    _aggregates(),
                    max_size=3,
                    unique_by=lambda aggregate: (aggregate.scenario, aggregate.arm),
                )
            )
        ),
    )


@st.composite
def _intervals(draw: st.DrawFn) -> Interval:
    """An admissible estimator record: three finite numbers, ordered ``low <= point <= high``."""
    low, point, high = sorted(draw(st.lists(_FINITE, min_size=3, max_size=3)))
    return Interval(
        method=METHOD,
        alpha=draw(_ALPHAS),
        resamples=draw(st.integers(min_value=1, max_value=10_000)),
        seed=draw(st.integers(min_value=0, max_value=2**31 - 1)),
        low=low,
        high=high,
        point=point,
    )


def _proof_grade(spec: _Spec) -> _Spec:
    """The same spec repaired into a completed, powered, in-bound, attributed contrast."""
    return dataclasses.replace(
        spec,
        incomplete=False,
        replicates_per_arm=MIN_POWERED_REPLICATES,
        kl_divergence=spec.threshold,
        within_fidelity_bound=True,
        revision=_ATTRIBUTED_REVISION,
        run_id=_ATTRIBUTED_RUN_ID,
    )


# ---------------------------------------------------------------------------
# Construction, and the independent oracles
# ---------------------------------------------------------------------------
def _artifact(spec: _Spec, interval: Interval | None) -> UpliftArtifact:
    """Build through the keyword surface; the headline and verdict follow from the interval."""
    return UpliftArtifact(
        schema_version=ARTIFACT_SCHEMA_VERSION,
        headline_uplift=NO_ESTIMATE_HEADLINE if interval is None else interval.point,
        primary_kpi=OBJECTIVE_KPI,
        noise_tolerance_pp=spec.noise_tolerance_pp,
        incomplete=spec.incomplete,
        all_wins_warning=spec.all_wins_warning,
        replicates_per_arm=spec.replicates_per_arm,
        fidelity=ArtifactFidelity(
            kl_divergence=spec.kl_divergence,
            threshold=spec.threshold,
            confidence="within_fidelity_bound",
            within_fidelity_bound=spec.within_fidelity_bound,
            fidelity_bound_statement="bounded by twin fidelity",
        ),
        provenance=UpliftProvenance(
            arms=tuple(arm for arm, _ in spec.roles),
            arm_roles=dict(spec.roles),
            replicates_per_arm=spec.replicates_per_arm,
            revision=spec.revision,
            run_id=spec.run_id,
            seeds=spec.seeds,
            written_at="2026-10-01T00:00:00Z",
        ),
        interval=None if interval is None else ArtifactInterval.from_interval(interval),
        headline_verdict=(
            None
            if interval is None
            else interval_verdict(interval.low, interval.high, margin=spec.materiality_margin)
        ),
        materiality_margin=spec.materiality_margin,
        comparator=spec.comparator,
        run_incomplete=spec.run_incomplete,
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


def _canonical(payload: object) -> str:
    """The repo-canonical JSON form, restated with stdlib only."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _expected_digest(spec: _Spec) -> str:
    """SHA-256 over the aggregates alone, recomputed from the spec rather than the model."""
    ordered = sorted(spec.aggregates, key=lambda aggregate: (aggregate.scenario, aggregate.arm))
    body = [
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
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _payload(artifact: UpliftArtifact) -> dict[str, Any]:
    """An independent, mutable copy of the artifact's wire mapping."""
    return copy.deepcopy(artifact.to_payload())


def _assert_refused(payload: dict[str, Any]) -> None:
    """Both readers the C60 gate can reach refuse ``payload`` rather than coerce it."""
    with pytest.raises(ValidationError):
        UpliftArtifact.model_validate(payload)
    with pytest.raises(ValidationError):
        UpliftArtifact.from_canonical_json(json.dumps(payload))


# ---------------------------------------------------------------------------
# Clause 1 -- the canonical round trip is byte-identical
# ---------------------------------------------------------------------------
@given(spec=_specs(), interval=st.none() | _intervals())
def test_an_interval_carrying_artifact_round_trips_to_identical_canonical_bytes(
    spec: _Spec, interval: Interval | None
) -> None:
    """Serialise, parse, re-serialise: the same value and the same bytes, interval included."""
    artifact = _artifact(spec, interval)
    text = artifact.to_canonical_json()
    parsed = UpliftArtifact.from_canonical_json(text)

    assert parsed == artifact
    assert parsed.to_canonical_json() == text
    assert text == _canonical(json.loads(text))
    assert parsed.interval == artifact.interval
    assert parsed.headline_verdict == artifact.headline_verdict
    assert parsed.headline_uplift == artifact.headline_uplift
    assert parsed.schema_version == ARTIFACT_SCHEMA_VERSION
    assert parsed.provenance.arm_roles == artifact.provenance.arm_roles
    assert parsed.as_powered_proof() == artifact.as_powered_proof()
    if interval is not None:
        assert parsed.interval is not None
        assert parsed.interval.to_interval() == interval


# ---------------------------------------------------------------------------
# Clause 2 -- the aggregate digest does not move (AD-15's affordability claim)
# ---------------------------------------------------------------------------
@given(spec=_specs(), first=_intervals(), second=_intervals())
def test_the_aggregate_digest_is_unmoved_by_the_interval_value_or_its_presence(
    spec: _Spec, first: Interval, second: Interval
) -> None:
    """Two intervals and no interval: three different artifacts, one digest, the stdlib one."""
    with_first = _artifact(spec, first)
    with_second = _artifact(spec, second)
    without = _artifact(spec, None)

    expected = _expected_digest(spec)
    assert with_first.arm_aggregates_digest == expected
    assert with_second.arm_aggregates_digest == expected
    assert without.arm_aggregates_digest == expected

    # The block is genuinely carried: the bytes differ while the digest does not.
    carried = json.loads(with_first.to_canonical_json())
    absent = json.loads(without.to_canonical_json())
    assert carried["interval"] == ArtifactInterval.from_interval(first).model_dump(mode="json")
    assert absent["interval"] is None
    assert with_first.to_canonical_json() != without.to_canonical_json()


# ---------------------------------------------------------------------------
# Clause 3 -- an unknown key inside the interval block is refused
# ---------------------------------------------------------------------------
@given(
    spec=_specs(),
    interval=_intervals(),
    key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=12).filter(
        lambda candidate: candidate not in _DECLARED_INTERVAL_FIELDS
    ),
    value=st.one_of(_FINITE, st.booleans(), st.text(max_size=5)),
)
def test_an_unknown_key_inside_the_interval_block_is_refused(
    spec: _Spec, interval: Interval, key: str, value: object
) -> None:
    """``extra="forbid"`` reaches inside the block: a stray field is a refusal, not a drop."""
    payload = _payload(_artifact(spec, interval))
    # Non-vacuity: the uncorrupted payload is accepted by both readers.
    assert UpliftArtifact.model_validate(payload) == _artifact(spec, interval)
    assert UpliftArtifact.from_canonical_json(json.dumps(payload)) == _artifact(spec, interval)

    corrupted = copy.deepcopy(payload)
    corrupted["interval"][key] = value
    _assert_refused(corrupted)
    with pytest.raises(ValidationError):
        ArtifactInterval.model_validate(corrupted["interval"])


# ---------------------------------------------------------------------------
# Clause 4 -- schema_version 1, and every other non-2 value, is refused
# ---------------------------------------------------------------------------
@given(
    spec=_specs(),
    interval=st.none() | _intervals(),
    version=st.one_of(
        st.just(1),
        st.integers().filter(lambda candidate: candidate != ARTIFACT_SCHEMA_VERSION),
        st.sampled_from([True, False, 2.0, "2", None]),
    ),
)
def test_a_schema_version_other_than_two_is_refused(
    spec: _Spec, interval: Interval | None, version: object
) -> None:
    """Only the integer 2 is read; a version-1 headline is in another unit and is not migrated."""
    payload = _payload(_artifact(spec, interval))
    assert payload["schema_version"] == ARTIFACT_SCHEMA_VERSION
    payload["schema_version"] = version
    _assert_refused(payload)


@given(spec=_specs())
def test_a_payload_shaped_like_a_version_one_artifact_is_refused(spec: _Spec) -> None:
    """A real v1 artifact: ``schema_version`` 1, a fill-rate KPI, none of the v2 keys."""
    payload = _payload(_artifact(spec, None))
    for key in ("interval", "headline_verdict", "materiality_margin", "comparator"):
        del payload[key]
    del payload["run_incomplete"]
    payload["schema_version"] = 1
    payload["primary_kpi"] = "fill_rate"
    _assert_refused(payload)


@given(spec=_specs(), interval=st.none() | _intervals())
def test_an_artifact_that_does_not_state_its_schema_version_is_refused(
    spec: _Spec, interval: Interval | None
) -> None:
    """The version is required, never defaulted: an unversioned payload is not read as v2."""
    payload = _payload(_artifact(spec, interval))
    del payload["schema_version"]
    _assert_refused(payload)


# ---------------------------------------------------------------------------
# Clause 5 -- the headline IS the interval's point, and nothing else
# ---------------------------------------------------------------------------
@given(spec=_specs(), interval=_intervals(), other=_FINITE)
def test_a_headline_that_is_not_the_interval_point_is_refused(
    spec: _Spec, interval: Interval, other: float
) -> None:
    """One ulp off is refused, as is any other finite number: the point is stored once."""
    payload = _payload(_artifact(spec, interval))

    one_ulp = copy.deepcopy(payload)
    one_ulp["headline_uplift"] = math.nextafter(interval.point, math.inf)
    _assert_refused(one_ulp)

    elsewhere = copy.deepcopy(payload)
    elsewhere["headline_uplift"] = (
        other if other != interval.point else math.nextafter(interval.point, -math.inf)
    )
    _assert_refused(elsewhere)


@given(spec=_specs(), other=_FINITE.filter(lambda value: value != NO_ESTIMATE_HEADLINE))
def test_with_no_interval_only_the_sentinel_headline_is_admitted(spec: _Spec, other: float) -> None:
    """A headline nobody intervalled is not a measurement, so it can only be the sentinel."""
    payload = _payload(_artifact(spec, None))
    assert payload["headline_uplift"] == NO_ESTIMATE_HEADLINE
    payload["headline_uplift"] = other
    _assert_refused(payload)


# ---------------------------------------------------------------------------
# Clause 6 -- a stored verdict is re-derived, never believed
# ---------------------------------------------------------------------------
@given(spec=_specs(), interval=_intervals())
def test_a_stored_verdict_the_rule_does_not_derive_is_refused(
    spec: _Spec, interval: Interval
) -> None:
    """Every verdict but the derived one is refused; so is an interval with no verdict at all."""
    artifact = _artifact(spec, interval)
    derived = artifact.headline_verdict
    assert derived in HEADLINE_VERDICTS
    payload = _payload(artifact)

    wrong = [verdict for verdict in HEADLINE_VERDICTS if verdict != derived]
    assert len(wrong) == len(HEADLINE_VERDICTS) - 1
    for verdict in wrong:
        corrupted = copy.deepcopy(payload)
        corrupted["headline_verdict"] = verdict
        _assert_refused(corrupted)

    no_verdict = copy.deepcopy(payload)
    no_verdict["headline_verdict"] = None
    _assert_refused(no_verdict)


@given(spec=_specs(), verdict=st.sampled_from(HEADLINE_VERDICTS))
def test_a_verdict_with_no_interval_is_refused(spec: _Spec, verdict: str) -> None:
    """No interval licenses no verdict: the pair is recorded together or not at all."""
    payload = _payload(_artifact(spec, None))
    payload["headline_verdict"] = verdict
    _assert_refused(payload)


# ---------------------------------------------------------------------------
# Clause 7 -- an absent interval is named, and is never proof-grade
# ---------------------------------------------------------------------------
@given(spec=_specs(), interval=_intervals())
def test_an_absent_interval_is_named_and_is_never_proof_grade(
    spec: _Spec, interval: Interval
) -> None:
    """Everything else proof-grade, the interval absent: exactly one reason, and it is that."""
    repaired = _proof_grade(spec)

    with_interval = _artifact(repaired, interval)
    assert with_interval.unavailable_reasons == ()
    assert with_interval.is_proof_grade is True

    without = _artifact(repaired, None)
    reasons = without.unavailable_reasons
    assert len(reasons) == 1
    assert reasons[0].startswith("no interval was estimated:")
    assert without.is_proof_grade is False


# ---------------------------------------------------------------------------
# Clause 8 -- the persisted interval is the estimator's record, field for field
# ---------------------------------------------------------------------------
def test_the_artifact_interval_declares_exactly_the_estimators_seven_fields() -> None:
    """Pinned by name against the computation form AND against the declared seven."""
    estimator_fields = {field.name for field in dataclasses.fields(Interval)}
    assert set(ArtifactInterval.model_fields) == estimator_fields
    assert estimator_fields == _DECLARED_INTERVAL_FIELDS


@given(interval=_intervals())
def test_an_estimated_interval_converts_and_converts_back_unchanged(interval: Interval) -> None:
    """``from_interval`` copies; ``to_interval`` restores; nothing is recomputed either way."""
    persisted = ArtifactInterval.from_interval(interval)
    assert persisted.model_dump() == interval.as_dict()
    assert persisted.to_interval() == interval


@given(bounds=st.lists(_FINITE, min_size=2, max_size=2, unique=True), beyond=_UNIT)
def test_every_interval_the_estimator_record_refuses_is_refused_when_persisted(
    bounds: list[float], beyond: float
) -> None:
    """Refusal parity, proven by construction: a point outside, and inverted bounds."""
    low, high = sorted(bounds)
    outside = high + 1.0 + beyond
    inadmissible = (
        {"low": low, "high": high, "point": outside},
        {"low": high, "high": low, "point": low},
    )
    for bound_fields in inadmissible:
        fields: dict[str, Any] = {
            "method": METHOD,
            "alpha": 0.05,
            "resamples": 10,
            "seed": 0,
            **bound_fields,
        }
        with pytest.raises(IntervalUnavailableError):
            Interval(**fields)
        with pytest.raises(ValidationError):
            ArtifactInterval.model_validate(fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"low": -math.inf},
        {"high": math.inf},
        {"point": math.nan},
        {"resamples": 0},
    ],
)
def test_a_non_finite_bound_or_an_empty_resample_count_is_refused_in_both_forms(
    overrides: dict[str, Any],
) -> None:
    """The remaining estimator refusals, each mirrored by the persisted form."""
    fields: dict[str, Any] = {
        "method": METHOD,
        "alpha": 0.05,
        "resamples": 10,
        "seed": 0,
        "low": 0.0,
        "high": 1.0,
        "point": 0.5,
        **overrides,
    }
    with pytest.raises(IntervalUnavailableError):
        Interval(**fields)
    with pytest.raises(ValidationError):
        ArtifactInterval.model_validate(fields)


@pytest.mark.parametrize("alpha", [math.nan, math.inf, -math.inf])
def test_a_non_finite_alpha_is_refused_because_it_cannot_round_trip(alpha: float) -> None:
    """The one refusal beyond the estimator's: a non-finite number has no canonical JSON form."""
    with pytest.raises(ValidationError):
        ArtifactInterval(
            method=METHOD, alpha=alpha, resamples=10, seed=0, low=0.0, high=1.0, point=0.5
        )
