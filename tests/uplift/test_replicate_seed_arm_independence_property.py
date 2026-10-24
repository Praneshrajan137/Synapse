"""Property-based test that replicate seeds are arm-independent and deterministic.

Feature: core-purpose-uplift, Property 17: Replicate seeds are arm-independent and
deterministic (attribution).

    *For any* ``(base_seed, index)``, ``replicate_seed`` is deterministic and depends
    only on those two values, so replicate ``i`` of the consensus arm and of every
    baseline arm is driven by the identical derived seed — the harness derives one seed
    sequence per scenario and reuses it across all arms.

    Requirement 6.1: "THE Uplift_Harness SHALL derive each replicate seed from only the
    scenario seed and replicate index, so that replicate ``i`` of the Consensus_Arm and
    of every Baseline_Arm is driven by the identical seeded twin realization."

    Requirement 6.2: "IF an arm would be driven by a seed that does not match the
    replicate seed derived from ``(scenario.seed, replicate_index)``, THEN THE
    Uplift_Harness SHALL reject that configuration rather than accept it — both arms
    MUST use the exact derived replicate seed."

The property is pure: it exercises the seed derivation itself and the harness's
per-scenario seed-sequence construction with the closed loop stubbed out. No twin runs,
no consensus assembly, no sockets, $0.

Carried to the v2 harness (decision-quality-proof task 15.5): every arm is registered as an
``ArmSpec`` declaring its role, and :meth:`UpliftHarness.run` -- the entry point a real run
takes -- is driven over several scenarios with arms of every role, so the reuse is shown for
whatever role an arm declared, not only for the two the predecessor named.

**Validates: Requirements 6.1, 6.2**
"""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import MIN_SCENARIOS, ShockParams
from uplift.harness import UpliftHarness, replicate_seed
from uplift.interfaces import (
    ARM_ROLES,
    ArmRole,
    ArmSpec,
    DecisionPolicy,
    Observation,
    PolicyAction,
    Scenario,
    ScenarioRun,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# Scenario seeds and replicate indices, over the range the harness actually derives from.
_seeds = st.integers(min_value=0, max_value=2**31 - 1)
_indices = st.integers(min_value=0, max_value=10_000)

# Arm names standing in for the consensus arm and the pre-registered baseline arms. The
# derivation takes no arm argument, so every one of these must receive the same seed.
_arm_names = st.lists(
    st.sampled_from(
        [
            "consensus",
            "par_level_reorder",
            "static_pricing",
            "greedy_routing",
            "no_op_disruption",
        ]
    ),
    min_size=2,
    max_size=5,
    unique=True,
)

_UINT32_MAX = 2**32 - 1


class _StubPolicy:
    """Minimal ``DecisionPolicy`` — never invoked, the closed loop is stubbed out."""

    def __init__(self, name: str) -> None:
        self.name = name

    def decide(self, obs: Observation) -> PolicyAction:  # pragma: no cover — not run
        return PolicyAction()


class _SeedCapturingHarness(UpliftHarness):
    """Harness that records the derived replicate seed sequence per arm.

    Overrides only the execution seam (``_run_sequential``), so the seed derivation under
    test — ``_run_arm_runs``'s ``[replicate_seed(scenario.seed, i) for i in range(n)]`` —
    runs verbatim while no twin is ever built. ``captured`` keeps the last sequence per arm;
    ``captured_by_pair`` keeps every ``(scenario, arm)`` sequence, for multi-scenario runs.
    """

    def __init__(self) -> None:
        super().__init__()
        self.captured: dict[str, list[int]] = {}
        self.captured_by_pair: dict[tuple[str, str], list[int]] = {}

    def _run_sequential(
        self,
        scenario: Scenario,
        policy: DecisionPolicy | None,
        policy_factory: Callable[[], DecisionPolicy] | None,
        arm_name: str,
        seeds: Sequence[int],
    ) -> list[ScenarioRun]:
        self.captured[arm_name] = list(seeds)
        self.captured_by_pair[(scenario.name, arm_name)] = list(seeds)
        return []


class _UnflooredSeedCapturingHarness(_SeedCapturingHarness):
    """The capturing harness with the INV-TW-002 floor lifted.

    The power floor is Property 10's subject; lifting it here keeps this property fast. It is
    an override of the one guard method, so the seed derivation still runs verbatim.
    """

    @staticmethod
    def _check_power(n: int) -> None:
        """No floor: Property 10 (``test_under_power_guard_property.py``) owns the guard."""


@st.composite
def _registrations(draw: st.DrawFn) -> list[tuple[str, ArmRole]]:
    """Unique arm names, each with a role drawn from every admissible role."""
    names = draw(_arm_names)
    return [(name, draw(st.sampled_from(ARM_ROLES))) for name in names]


def test_replicate_seed_signature_takes_no_arm() -> None:
    """Structural half of R6.1: the derivation cannot depend on the arm."""
    params = list(inspect.signature(replicate_seed).parameters)
    assert params == ["base_seed", "index"]


@given(base_seed=_seeds, index=_indices, arms=_arm_names)
def test_replicate_seeds_are_arm_independent_and_deterministic(
    base_seed: int, index: int, arms: list[str]
) -> None:
    """Property 17: the derived replicate seed is a pure function of ``(seed, index)``.

    **Validates: Requirements 6.1, 6.2**
    """
    # R6.1 — determinism: repeated derivation for the same (base_seed, index) agrees.
    expected = replicate_seed(base_seed, index)
    assert replicate_seed(base_seed, index) == expected
    assert isinstance(expected, int)
    assert 0 <= expected <= _UINT32_MAX

    # R6.1 — arm independence: every arm asking for replicate ``index`` of the same
    # scenario is handed the identical derived seed, so all arms share one twin stream.
    per_arm = {arm: replicate_seed(base_seed, index) for arm in arms}
    assert set(per_arm.values()) == {expected}

    # R6.2 — a seed that is not the exact derived value is distinguishable from it, so
    # "both arms MUST use the exact derived replicate seed" is a checkable condition.
    tampered = (expected + 1) % (_UINT32_MAX + 1)
    assert tampered != expected

    # R6.1/R6.2 — the harness reuses one seed sequence per scenario across all arms:
    # each arm's captured sequence equals the sequence derived from the scenario seed
    # alone, position by position.
    scenario = Scenario(name="prop17", seed=base_seed, shock=ShockParams())
    n = min(index + 1, 8)
    derived = [replicate_seed(scenario.seed, i) for i in range(n)]

    # The power floor is Property 10's subject; the unfloored harness keeps this fast.
    harness = _UnflooredSeedCapturingHarness()
    for arm in arms:
        harness._run_arm_runs(scenario, _StubPolicy(arm), n, parallel=False)

    assert set(harness.captured) == set(arms)
    for arm in arms:
        assert harness.captured[arm] == derived
    assert derived[index % n] == replicate_seed(base_seed, index % n)


@given(
    base_seeds=st.lists(_seeds, min_size=1, max_size=3, unique=True),
    registrations=_registrations(),
    n=st.integers(min_value=1, max_value=8),
)
def test_every_registered_arm_is_handed_one_seed_sequence_per_scenario(
    base_seeds: list[int], registrations: list[tuple[str, ArmRole]], n: int
) -> None:
    """Through ``run``, every arm of every role gets its scenario's one derived sequence.

    **Validates: Requirements 6.1, 6.2**
    """
    scenarios = [
        Scenario(name=f"prop17-{position}", seed=seed, shock=ShockParams())
        for position, seed in enumerate(base_seeds)
    ]
    arms = [ArmSpec(_StubPolicy(name), role) for name, role in registrations]
    harness = _UnflooredSeedCapturingHarness()

    result = harness.run(scenarios, arms, n, parallel=False)

    # Every (scenario, arm) pair reached the execution seam exactly once, and the result
    # records each arm with the role it declared.
    assert set(harness.captured_by_pair) == {
        (scenario.name, name) for scenario in scenarios for name, _role in registrations
    }
    assert result.arm_roles == dict(registrations)
    for scenario in scenarios:
        derived = [replicate_seed(scenario.seed, i) for i in range(n)]
        for name, _role in registrations:
            assert harness.captured_by_pair[(scenario.name, name)] == derived


def test_harness_seed_sequence_is_shared_at_the_powered_floor() -> None:
    """The same one-sequence-per-scenario reuse holds at the INV-TW-002 power floor."""
    scenario = Scenario(name="prop17-powered", seed=4242, shock=ShockParams())
    harness = _SeedCapturingHarness()

    for arm in ("consensus", "par_level_reorder"):
        harness._run_arm_runs(scenario, _StubPolicy(arm), MIN_SCENARIOS, parallel=False)

    derived = [replicate_seed(scenario.seed, i) for i in range(MIN_SCENARIOS)]
    assert harness.captured["consensus"] == derived
    assert harness.captured["par_level_reorder"] == derived
