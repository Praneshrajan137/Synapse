"""Property-based test for reproduction stability within the declared tolerance.

Feature: decision-integrity-uplift-proof
Property 23: Reproduction is stable within the declared tolerance.

    *For any* two runs of the reproduction command with the same configured seeds, the
    absolute run-to-run difference of the headline uplift number does not exceed the
    declared noise tolerance (<= 1.0 percentage point).

The reproduction is deterministic *by construction*: ``replicate_seed`` derives every
replicate's twin seed from ``(scenario.seed, index)`` alone, the SimPy twin is seeded,
and the baseline policies are deterministic. So two runs with the *same configured
seeds* produce the identical headline uplift number (a run-to-run difference of exactly
``0.0``), which trivially satisfies the ``<= NOISE_TOLERANCE_PP`` (1.0 pp) tolerance the
reproduction is judged against.

This test drives the real SimPy twin exactly as ``make prove-uplift`` does — it reuses
the CLI's reduced-cost reproduction path (:func:`uplift.cli._run_reduced`) plus
:func:`assemble_uplift_result` / :func:`build_uplift_report` to obtain
``report.headline_uplift`` — but with a reduced-cost seeded configuration: a small
number of replicates over a short horizon, and a modest number of Hypothesis examples,
because each example drives the twin many times (2 runs x scenarios x arms x replicates)
and is therefore slow.

The consensus arm is unavailable in-process (no injected protocol/transport), so its
runs fail honestly and it contributes no samples; the deterministic baseline arms still
complete and yield a deterministic headline. Determinism of that headline *across the
two runs of the same config* is exactly what Property 23 requires.

Validates: Requirements 7.3
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from uplift.cli import NOISE_TOLERANCE_PP, build_arms
from uplift.cli import _run_reduced  # reduced-cost smoke path used by prove-uplift
from uplift.contract import load_contract
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    LoopConfig,
    assemble_uplift_result,
    build_uplift_report,
)
from uplift.scenarios import DEMAND_SPIKE, SUPPLIER_DEFAULT

# Reduced-cost seeded configuration (design "Cost management" note for Property 23):
#   - a small subset of the adversarial suite (two representative seeded scenarios),
#   - a very small replicate count, and
#   - a short closed-loop horizon (a single one-hour step),
# so each Hypothesis example drives the real twin only a handful of times.
_REDUCED_SCENARIOS = (DEMAND_SPIKE, SUPPLIER_DEFAULT)
_REDUCED_REPLICATES = 2
_REDUCED_LOOP = LoopConfig(duration_hours=1.0, step_hours=1.0)

# The pre-registered metric contract is fixed input to the reproduction; load it once.
_CONTRACT = load_contract()


def _headline_for_config(seed: int) -> float:
    """Run the reduced-cost reproduction once for ``seed`` and return the headline number.

    Mirrors what ``make prove-uplift`` does: build the arm suite at the configured
    construction ``seed``, run the reduced-cost closed-loop matrix over the seeded
    scenarios, assemble the result under the pre-registered contract, and read the
    headline uplift off the fidelity-co-located report.
    """
    arms = build_arms(seed=seed)
    harness_result = _run_reduced(
        _REDUCED_SCENARIOS,
        arms,
        _REDUCED_REPLICATES,
        _REDUCED_LOOP,
        emission_factor=0.5,
    )
    result = assemble_uplift_result(
        harness_result, _CONTRACT, consensus_arm=DEFAULT_CONSENSUS_ARM
    )
    report = build_uplift_report(result)
    return float(report.headline_uplift)


# Feature: decision-integrity-uplift-proof, Property 23: Reproduction is stable within
# the declared tolerance.
@settings(
    max_examples=4,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(seed=st.integers(min_value=0, max_value=32))
def test_reproduction_is_stable_within_declared_tolerance(seed: int) -> None:
    """Two runs of the reproduction with the same configured seeds agree within tolerance.

    Each Hypothesis example runs the reduced-cost reproduction *twice* with the identical
    configured seed and asserts the absolute run-to-run difference of the headline uplift
    number is within the version-controlled noise tolerance (<= 1.0 pp). Because the
    harness is deterministic given a seed, the difference is exactly ``0.0`` in practice,
    which is comfortably inside the tolerance (Property 23, Requirement 7.3).
    """
    headline_first = _headline_for_config(seed)
    headline_second = _headline_for_config(seed)

    run_to_run_diff = abs(headline_first - headline_second)

    assert run_to_run_diff <= NOISE_TOLERANCE_PP, (
        f"run-to-run headline diff {run_to_run_diff} pp exceeds declared noise "
        f"tolerance {NOISE_TOLERANCE_PP} pp for seed {seed}"
    )
