# Feature: decision-quality-proof, Property 83: A named comparator is never pooled, and an
# oracle-role arm is never absorbed
"""The comparator is explicit: named means alone, pooled means declared baselines only.

Task 15.6 (R6.14), for task 15.5's change (AD-16). Subjects:
``uplift/harness.py::_resolve_baseline_arms``, ``comparator_label`` and the contrast-scoped
``incomplete`` of ``assemble_uplift_result``; ``uplift/cli.py::resolve_control_spec``,
``ControlSpec`` and ``build_arms``.

**Why (AD-16).** The pooled comparator used to absorb every non-consensus arm, so an Oracle_Arm
added to a run was silently pooled into the baseline, and one failed oracle replicate marked the
consensus contrast incomplete and drove C60 to ``EXIT_UNAVAILABLE`` -- the oracle could break a
verdict it is not the subject of. And ``cli.py::main`` never passed ``baseline_arm=``, so R6.1's
premise (two identical policies compared) failed before the run started.

**Clauses, each asserted unconditionally, over generated role maps.**

1. A named comparator resolves to exactly itself, whatever role it declared, and is recorded
   under its bare name.
2. A pool never contains an oracle-role arm, an excluded arm, or the subject; it is exactly the
   declared baselines, recorded as ``"pooled:"`` plus their sorted names. Every generated map
   carries an oracle or excluded arm, so the exclusion is exercised on every example.
3. An empty pool is refused rather than compared against nothing.
4. The subject named as its own comparator is refused.
5. An unregistered name is refused.
6. A failed oracle replicate leaves the contrast's ``incomplete`` False while ``run_incomplete``
   is True -- and the same failure on an arm INSIDE the contrast marks it incomplete, so the
   contrast predicate is live, not constant.
7. ``resolve_control_spec`` refuses both flags at once, a non-canonical arm set with neither
   flag, and an unregistered named arm; the canonical five with neither flag resolve to the pool
   and are recorded as one. A refused arm set is accepted the moment a comparator is stated, so
   the refusal is about the missing statement and not about the arms.

**Pure.** Harness results are built by hand from generated objective values: no twin, no
consensus network (``build_arms``'s consensus arm is replaced by a named stub), no subprocess.
Budget inherited from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal. Locus:
``ci.yml::uplift-verify`` fast step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

import uplift.cli as cli
from digital_twin.simulation.monte_carlo import ShockParams
from uplift.cli import CANONICAL_ARM_NAMES, ControlSpec, build_arms, resolve_control_spec
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    POOLED_COMPARATOR_PREFIX,
    HarnessResult,
    _resolve_baseline_arms,
    aggregate_arm,
    assemble_uplift_result,
    comparator_label,
    registered_roles,
)
from uplift.interfaces import (
    ARM_ROLES,
    ArmRole,
    KpiVector,
    Observation,
    PolicyAction,
    Scenario,
    ScenarioRun,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_CONTRACT = load_contract()
_FIDELITY = FidelityReport(kl_divergence=0.05, threshold=0.1)

#: Arm names a comparator label can state: no ``,`` and no ``:``, so none can collide with the
#: pooled label's syntax. An unregistered name below carries a ``-``, which no registered name
#: can contain.
_NAMES = st.text(alphabet="abcdefghij_", min_size=1, max_size=8)
_NON_BASELINE: Final[tuple[ArmRole, ...]] = ("consensus", "oracle", "excluded")
_NEVER_POOLED: Final[tuple[ArmRole, ...]] = ("oracle", "excluded")
_OBJECTIVES = st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False)
_SUBJECT: Final[str] = DEFAULT_CONSENSUS_ARM
_ORACLE: Final[str] = "oracle_structure_aware"
_EXCLUDED: Final[str] = "shadow_copy"


class _NamedStub:
    """A named ``DecisionPolicy`` that is never asked to decide."""

    def __init__(self, name: str) -> None:
        self.name = name

    def decide(self, obs: Observation) -> PolicyAction:  # noqa: ARG002 -- never invoked
        return PolicyAction()


# ---------------------------------------------------------------------------
# Generated registrations
# ---------------------------------------------------------------------------
@st.composite
def _registrations(draw: st.DrawFn) -> tuple[tuple[str, ...], dict[str, ArmRole], str]:
    """Arm names, a declared role for each, and the subject (any registered arm, any role)."""
    names = tuple(draw(st.lists(_NAMES, min_size=2, max_size=6, unique=True)))
    roles: dict[str, ArmRole] = {name: draw(st.sampled_from(ARM_ROLES)) for name in names}
    return names, roles, draw(st.sampled_from(names))


@st.composite
def _pool_registrations(draw: st.DrawFn) -> tuple[tuple[str, ...], dict[str, ArmRole], str]:
    """As above, with at least one baseline AND one oracle-or-excluded arm besides the subject.

    Built by construction rather than filtered, so every example both forms a pool and offers
    it an arm it must refuse.
    """
    names = tuple(draw(st.lists(_NAMES, min_size=3, max_size=7, unique=True)))
    subject, forced_baseline, forced_refusal, *rest = names
    roles: dict[str, ArmRole] = {
        subject: draw(st.sampled_from(ARM_ROLES)),
        forced_baseline: "baseline",
        forced_refusal: draw(st.sampled_from(_NEVER_POOLED)),
    }
    for name in rest:
        roles[name] = draw(st.sampled_from(ARM_ROLES))
    order = draw(st.permutations(names))
    return tuple(order), roles, subject


@st.composite
def _poolless_registrations(draw: st.DrawFn) -> tuple[tuple[str, ...], dict[str, ArmRole], str]:
    """Registrations in which no arm other than the subject declares ``baseline``."""
    names = tuple(draw(st.lists(_NAMES, min_size=2, max_size=6, unique=True)))
    subject = draw(st.sampled_from(names))
    roles: dict[str, ArmRole] = {}
    for name in names:
        roles[name] = draw(st.sampled_from(ARM_ROLES if name == subject else _NON_BASELINE))
    return names, roles, subject


def _registered(names: Sequence[str], roles: Mapping[str, ArmRole]) -> HarnessResult:
    """A harness result carrying only a registration: resolution reads names and roles."""
    return HarnessResult(
        arm_results={},
        runs_by_pair={},
        all_runs=[],
        results_path=None,
        scenarios=(),
        arm_names=tuple(names),
        arm_roles=roles,
    )


# ---------------------------------------------------------------------------
# Clause 1 -- a named comparator is exactly itself
# ---------------------------------------------------------------------------
@given(registration=_registrations(), data=st.data())
def test_a_named_comparator_resolves_to_exactly_itself_whatever_role_it_declared(
    registration: tuple[tuple[str, ...], dict[str, ArmRole], str], data: st.DataObject
) -> None:
    """Naming is the explicit contrast: never pooled, never widened, recorded bare."""
    names, roles, subject = registration
    named = data.draw(st.sampled_from([name for name in names if name != subject]))

    resolved = _resolve_baseline_arms(_registered(names, roles), subject, named)

    assert resolved == [named]
    assert comparator_label(named, resolved) == named
    assert not comparator_label(named, resolved).startswith(POOLED_COMPARATOR_PREFIX)


# ---------------------------------------------------------------------------
# Clause 2 -- a pool is the declared baselines, never an oracle, excluded arm or the subject
# ---------------------------------------------------------------------------
@given(registration=_pool_registrations())
def test_a_pool_absorbs_only_declared_baselines_and_never_the_subject(
    registration: tuple[tuple[str, ...], dict[str, ArmRole], str],
) -> None:
    """The pooled default means "every arm declared a baseline", which is what it claims."""
    names, roles, subject = registration
    refused = [name for name in names if name != subject and roles[name] in _NEVER_POOLED]
    assert refused, "every generated registration offers the pool an arm it must refuse"

    pooled = _resolve_baseline_arms(_registered(names, roles), subject, None)

    expected = [name for name in names if name != subject and roles[name] == "baseline"]
    assert pooled == expected
    assert pooled
    assert subject not in pooled
    assert all(roles[arm] == "baseline" for arm in pooled)
    assert not set(pooled) & set(refused)
    assert comparator_label(None, pooled) == POOLED_COMPARATOR_PREFIX + ",".join(sorted(expected))


# ---------------------------------------------------------------------------
# Clauses 3-5 -- the three resolution refusals
# ---------------------------------------------------------------------------
@given(registration=_poolless_registrations())
def test_an_empty_pool_is_refused_rather_than_compared_against_nothing(
    registration: tuple[tuple[str, ...], dict[str, ArmRole], str],
) -> None:
    """No baseline-role arm besides the subject: there is no pool, so there is no contrast."""
    names, roles, subject = registration
    with pytest.raises(ValueError, match="no baseline-role arm"):
        _resolve_baseline_arms(_registered(names, roles), subject, None)


@given(registration=_registrations())
def test_the_subject_named_as_its_own_comparator_is_refused(
    registration: tuple[tuple[str, ...], dict[str, ArmRole], str],
) -> None:
    """A contrast of an arm with itself is zero by construction and measures nothing."""
    names, roles, subject = registration
    with pytest.raises(ValueError, match="subject arm itself"):
        _resolve_baseline_arms(_registered(names, roles), subject, subject)


@given(registration=_registrations(), suffix=_NAMES)
def test_an_unregistered_comparator_name_is_refused(
    registration: tuple[tuple[str, ...], dict[str, ArmRole], str], suffix: str
) -> None:
    """A name no arm registered is refused, never matched loosely or ignored."""
    names, roles, subject = registration
    unregistered = f"unregistered-{suffix}"
    assert unregistered not in names
    with pytest.raises(ValueError, match="not a registered arm"):
        _resolve_baseline_arms(_registered(names, roles), subject, unregistered)


@given(registration=_registrations(), suffix=_NAMES, named=st.booleans())
def test_an_unregistered_subject_is_refused_rather_than_read_as_an_incomplete_contrast(
    registration: tuple[tuple[str, ...], dict[str, ArmRole], str], suffix: str, named: bool
) -> None:
    """A subject no arm registered is refused, whether its comparator is named or pooled.

    Before finding 97 it resolved, and assembly then reported an incomplete contrast -- the
    honest state for an arm that RAN and failed, misapplied to an arm that never ran.
    """
    names, roles, subject = registration
    unregistered = f"unregistered-{suffix}"
    assert unregistered not in names
    comparator = next(name for name in names if name != subject) if named else None
    with pytest.raises(ValueError, match="subject arm .* is not a registered arm"):
        _resolve_baseline_arms(_registered(names, roles), unregistered, comparator)


# ---------------------------------------------------------------------------
# Clause 6 -- incompleteness is scoped to the contrast
# ---------------------------------------------------------------------------
def _kpis(objective: float) -> KpiVector:
    return KpiVector(
        fill_rate=0.9,
        spoilage_rate=0.0,
        stockout_rate=0.1,
        avg_delivery_time_min=20.0,
        margin=1.0,
        co2_estimate=1.0,
        avg_on_hand_units=50.0,
        objective=objective,
    )


def _runs(arm: str, objectives: Sequence[float], failed_at: int | None) -> list[ScenarioRun]:
    """One run per replicate seed ``0..n-1``; replicate ``failed_at`` (if any) failed honestly."""
    return [
        ScenarioRun(
            arm=arm,
            seed=seed,
            kpis=None if seed == failed_at else _kpis(value),
            failed=seed == failed_at,
            error="replicate failed" if seed == failed_at else None,
        )
        for seed, value in enumerate(objectives)
    ]


@st.composite
def _contrasts(draw: st.DrawFn) -> tuple[dict[str, list[float]], tuple[str, ...], bool]:
    """Objective samples for a subject, one or two baselines, an oracle, maybe an excluded arm.

    Returns ``(objectives by arm, the baseline names, whether an excluded arm is registered)``.
    Every arm has the same replicate count, so every replicate seed is shared.
    """
    count = draw(st.integers(min_value=1, max_value=5))
    baselines = ("Par_Level_Reorder", "static_pricing")[: draw(st.integers(1, 2))]
    with_excluded = draw(st.booleans())
    arms = (_SUBJECT, *baselines, _ORACLE, *((_EXCLUDED,) if with_excluded else ()))
    samples = {arm: draw(st.lists(_OBJECTIVES, min_size=count, max_size=count)) for arm in arms}
    return samples, baselines, with_excluded


def _role_of(arm: str, baselines: Sequence[str]) -> ArmRole:
    """The role each arm of a :func:`_contrasts` case declares."""
    if arm == _SUBJECT:
        return "consensus"
    if arm in baselines:
        return "baseline"
    if arm == _ORACLE:
        return "oracle"
    return "excluded"


def _harness(
    samples: Mapping[str, Sequence[float]],
    baselines: Sequence[str],
    failures: Mapping[str, int],
) -> HarnessResult:
    """One scenario; each arm's runs at seeds ``0..n-1``, with the given failed replicates."""
    scenario = Scenario(name="demand-spike", seed=7, shock=ShockParams())
    runs_by_pair = {
        (scenario.name, arm): _runs(arm, values, failures.get(arm))
        for arm, values in samples.items()
    }
    return HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=(scenario,),
        arm_names=tuple(samples),
        arm_roles={arm: _role_of(arm, baselines) for arm in samples},
    )


@given(case=_contrasts(), named=st.booleans(), data=st.data())
def test_a_failed_oracle_replicate_never_marks_the_consensus_contrast_incomplete(
    case: tuple[dict[str, list[float]], tuple[str, ...], bool], named: bool, data: st.DataObject
) -> None:
    """The oracle (and an excluded arm) fail; the run is incomplete, the contrast is not."""
    samples, baselines, with_excluded = case
    count = len(samples[_SUBJECT])
    failures = {_ORACLE: data.draw(st.integers(min_value=0, max_value=count - 1))}
    if with_excluded:
        failures[_EXCLUDED] = data.draw(st.integers(min_value=0, max_value=count - 1))
    comparator = baselines[0] if named else None

    result = assemble_uplift_result(
        _harness(samples, baselines, failures),
        _CONTRACT,
        fidelity=_FIDELITY,
        consensus_arm=_SUBJECT,
        baseline_arm=comparator,
    )

    assert result.run_incomplete is True
    assert result.incomplete is False
    # The contrast completed, so it was measured: an interval and a verdict exist.
    assert result.interval is not None
    assert result.headline_verdict is not None
    expected_label = (
        baselines[0] if named else POOLED_COMPARATOR_PREFIX + ",".join(sorted(baselines))
    )
    assert result.comparator == expected_label
    assert _ORACLE not in result.comparator
    assert _EXCLUDED not in result.comparator


@given(case=_contrasts(), on_subject=st.booleans(), data=st.data())
def test_the_same_failure_on_an_arm_inside_the_contrast_does_mark_it_incomplete(
    case: tuple[dict[str, list[float]], tuple[str, ...], bool],
    on_subject: bool,
    data: st.DataObject,
) -> None:
    """Non-vacuity for clause 6: the contrast predicate fires on its own arms."""
    samples, baselines, _ = case
    count = len(samples[_SUBJECT])
    failed_arm = _SUBJECT if on_subject else baselines[-1]
    failures = {failed_arm: data.draw(st.integers(min_value=0, max_value=count - 1))}

    result = assemble_uplift_result(
        _harness(samples, baselines, failures),
        _CONTRACT,
        fidelity=_FIDELITY,
        consensus_arm=_SUBJECT,
        baseline_arm=None,
    )

    assert result.incomplete is True
    assert result.run_incomplete is True


# ---------------------------------------------------------------------------
# Clause 7 -- the CLI's comparator: three refusals and the canonical default
# ---------------------------------------------------------------------------
@st.composite
def _non_canonical_arm_sets(draw: st.DrawFn) -> tuple[str, ...]:
    """An arm set that is not exactly the canonical five: one more, one fewer, or reordered."""
    shape = draw(st.sampled_from(("extra", "missing", "reordered")))
    canonical = list(CANONICAL_ARM_NAMES)
    if shape == "extra":
        position = draw(st.integers(min_value=0, max_value=len(canonical)))
        canonical.insert(position, draw(st.sampled_from((_ORACLE, _EXCLUDED, "Par_Level_Copy"))))
        return tuple(canonical)
    if shape == "missing":
        del canonical[draw(st.integers(min_value=0, max_value=len(canonical) - 1))]
        return tuple(canonical)
    reordered = tuple(
        draw(st.permutations(canonical).filter(lambda order: list(order) != canonical))
    )
    return reordered


_ARM_SETS = st.one_of(st.just(CANONICAL_ARM_NAMES), _non_canonical_arm_sets())


@given(arm_names=_ARM_SETS, data=st.data())
def test_both_comparator_flags_at_once_are_refused(
    arm_names: tuple[str, ...], data: st.DataObject
) -> None:
    """A contrast is against one named arm or against the pool, never both."""
    named = data.draw(st.sampled_from(arm_names))
    with pytest.raises(ValueError, match="mutually exclusive"):
        resolve_control_spec(baseline_arm=named, pooled_baseline=True, arm_names=arm_names)


@given(arm_names=_non_canonical_arm_sets(), data=st.data())
def test_a_non_canonical_arm_set_with_no_stated_comparator_is_refused_not_pooled(
    arm_names: tuple[str, ...], data: st.DataObject
) -> None:
    """No default for an unrecognised arm set -- and stating a comparator is all it takes."""
    assert arm_names != CANONICAL_ARM_NAMES
    with pytest.raises(ValueError, match="not exactly the canonical five"):
        resolve_control_spec(baseline_arm=None, pooled_baseline=False, arm_names=arm_names)

    # The refusal is about the missing statement, not the arms: either statement is accepted.
    assert resolve_control_spec(
        baseline_arm=None, pooled_baseline=True, arm_names=arm_names
    ) == ControlSpec(baseline_arm=None, pooled=True)
    named = data.draw(st.sampled_from(arm_names))
    assert resolve_control_spec(
        baseline_arm=named, pooled_baseline=False, arm_names=arm_names
    ) == ControlSpec(baseline_arm=named, pooled=False)


@given(arm_names=_ARM_SETS, suffix=_NAMES)
def test_a_named_comparator_the_run_did_not_register_is_refused(
    arm_names: tuple[str, ...], suffix: str
) -> None:
    """Refused before any replicate runs, rather than after a run it could not judge."""
    with pytest.raises(ValueError, match="not a registered arm"):
        resolve_control_spec(
            baseline_arm=f"unregistered-{suffix}", pooled_baseline=False, arm_names=arm_names
        )


def test_the_canonical_five_with_no_flag_resolve_to_the_pool_and_are_recorded_as_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_arms`` registers exactly the canonical five; with no flag they pool, by name."""
    monkeypatch.setattr(cli, "_build_consensus_arm", lambda: _NamedStub(DEFAULT_CONSENSUS_ARM))
    arms = build_arms(seed=0)
    names = tuple(spec.name for spec in arms)
    assert names == CANONICAL_ARM_NAMES
    assert [spec.role for spec in arms] == ["consensus"] + ["baseline"] * 4

    control = resolve_control_spec(baseline_arm=None, pooled_baseline=False, arm_names=names)
    assert control == ControlSpec(baseline_arm=None, pooled=True)

    resolved = _resolve_baseline_arms(
        _registered(names, registered_roles(arms)), DEFAULT_CONSENSUS_ARM, control.baseline_arm
    )
    assert resolved == list(CANONICAL_ARM_NAMES[1:])
    assert comparator_label(control.baseline_arm, resolved) == (
        POOLED_COMPARATOR_PREFIX + ",".join(sorted(CANONICAL_ARM_NAMES[1:]))
    )


@pytest.mark.parametrize(
    ("baseline_arm", "pooled"), [("Par_Level_Reorder", True), (None, False), ("  ", False)]
)
def test_a_control_spec_that_is_not_exactly_one_form_is_refused(
    baseline_arm: str | None, pooled: bool
) -> None:
    """A ControlSpec names one arm or asks for the pool; a blank name is no name."""
    with pytest.raises(ValueError, match="exactly one of the two|non-empty name"):
        ControlSpec(baseline_arm=baseline_arm, pooled=pooled)


def test_the_cli_refuses_both_comparator_flags_before_doing_anything() -> None:
    """The flags are a mutually exclusive group, so the parser itself refuses the pair."""
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args(
            ["--smoke", "--pooled-baseline", "--baseline-arm", "Par_Level_Reorder"]
        )
    parsed = cli._build_parser().parse_args(["--smoke", "--baseline-arm", "Par_Level_Reorder"])
    assert parsed.baseline_arm == "Par_Level_Reorder"
    assert parsed.pooled_baseline is False
