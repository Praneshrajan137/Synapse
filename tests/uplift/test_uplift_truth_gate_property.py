"""Property-based tests for the ``uplift_truth`` verdict mapping.

Feature: decision-integrity-uplift-proof
Property 21: Uplift_truth gate exit codes follow the floor mapping.

    *For any* measurement and committed floor, the gate exits ``0`` when the measurement
    proves an uplift at or above the floor; exits the regression code (``1``), emitting
    the measured value and the floor, when a real measurement is strictly below the
    floor; and exits a distinct non-zero code (never a pass) when no uplift is proven.

**Restated for the purpose-achievement-audit R2 remediation.** The original statement of
this property was "exits 0 when the measured uplift is >= the floor", read from a bare
``headline_uplift`` field. That is the tautology Requirement 2 of the
``purpose-achievement-audit`` spec found: with ``UPLIFT_FLOOR = 0.0`` it reported PASS on
an artifact declaring ``incomplete: true`` and fidelity ``unknown``. R2.4 supersedes it:
the verdict now derives from :func:`uplift.uplift_floor.is_proven_uplift`, so a pass
additionally requires a powered, complete, within-fidelity-bound run with a strictly
positive headline. The floor mapping itself -- pass at/above, regression below -- is
unchanged, and that is what this property still pins.

The expected code is recomputed here from the proof's fields rather than by calling
``is_proven_uplift``, so this is an independent statement of the rule and not a
restatement of the implementation. Pure: no artifact, no twin, no socket, $0.

**Validates: Requirements 6.3, 6.4, 6.5** (and, as restated, R2.4)
"""
from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from scripts.audit.uplift_truth import (
    EXIT_PASS,
    EXIT_REGRESSION,
    EXIT_UNAVAILABLE,
    verdict,
    verdict_reason,
)
from uplift.uplift_floor import MIN_POWERED_REPLICATES, PoweredProof

_EXIT_CODES = (EXIT_PASS, EXIT_REGRESSION, EXIT_UNAVAILABLE)

# Finite values on a range where the ``headline >= floor`` comparison stays meaningful.
_finite = st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)

# Replicate counts that straddle the INV-TW-002 power floor in both directions.
_replicates = st.one_of(
    st.integers(min_value=0, max_value=MIN_POWERED_REPLICATES - 1),
    st.integers(min_value=MIN_POWERED_REPLICATES, max_value=MIN_POWERED_REPLICATES * 3),
    st.just(MIN_POWERED_REPLICATES),
)


@st.composite
def _proofs(draw) -> PoweredProof:
    """A proof spanning powered/under-powered, complete/incomplete, and all three
    fidelity states, with headlines that land above, below, and exactly on a floor."""
    return PoweredProof(
        headline_uplift=draw(_finite),
        replicates=draw(_replicates),
        incomplete=draw(st.booleans()),
        within_fidelity_bound=draw(st.sampled_from([True, False, None])),
    )


_proof_or_none = st.one_of(st.none(), _proofs())


def _expected_exit(proof: PoweredProof | None, floor: float) -> int:
    """Restate the mapping directly from the proof's fields (R2.4)."""
    if proof is None:
        return EXIT_UNAVAILABLE
    if proof.replicates < MIN_POWERED_REPLICATES:
        return EXIT_UNAVAILABLE
    if proof.incomplete:
        return EXIT_UNAVAILABLE
    if proof.within_fidelity_bound is not True:
        return EXIT_UNAVAILABLE
    if not math.isfinite(proof.headline_uplift):
        return EXIT_UNAVAILABLE
    if proof.headline_uplift < floor:
        return EXIT_REGRESSION
    if proof.headline_uplift > 0.0:
        return EXIT_PASS
    return EXIT_UNAVAILABLE


# ---------------------------------------------------------------------------
# Property 21: the three-way mapping, and its totality
# ---------------------------------------------------------------------------
@given(proof=_proof_or_none, floor=_finite)
def test_exit_codes_follow_floor_mapping(proof: PoweredProof | None, floor: float) -> None:
    """Pass at/above the floor when proven, regression below, unavailable otherwise."""
    code = verdict(proof, floor=floor)

    assert len(set(_EXIT_CODES)) == 3
    assert code in _EXIT_CODES
    assert code == _expected_exit(proof, floor)

    if code == EXIT_UNAVAILABLE:
        # R6.5 / I-7: a distinct non-zero code. Absence of proof is never a pass.
        assert code != EXIT_PASS
        assert code != EXIT_REGRESSION
        assert code != 0


@given(proof=_proof_or_none, floor=_finite)
def test_regression_reason_names_measured_and_floor(
    proof: PoweredProof | None, floor: float
) -> None:
    """R6.4: the regression report emits the measured value, the floor, and 'REGRESSION'."""
    code = verdict(proof, floor=floor)
    reason = verdict_reason(proof, code, floor=floor)

    assert reason  # every outcome is explained, never silently non-zero
    if code == EXIT_REGRESSION:
        assert proof is not None
        assert "REGRESSION" in reason.upper()
        assert str(proof.headline_uplift) in reason
        assert str(floor) in reason


# ---------------------------------------------------------------------------
# Property 21 (boundary): measured == floor passes only when it is a real gain
# ---------------------------------------------------------------------------
@given(floor=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False))
def test_boundary_measured_equals_positive_floor_is_pass(floor: float) -> None:
    """A proven measurement exactly on a positive floor passes (R6.3 uses '>=')."""
    proof = PoweredProof(
        headline_uplift=floor,
        replicates=MIN_POWERED_REPLICATES,
        incomplete=False,
        within_fidelity_bound=True,
    )
    assert verdict(proof, floor=floor) == EXIT_PASS


# ---------------------------------------------------------------------------
# The audit's central example: the artifact the gate used to pass (R2.1, R2.4)
# ---------------------------------------------------------------------------
def test_zero_headline_on_zero_floor_is_not_a_pass() -> None:
    """A complete, powered, in-bound run measuring 0.0 against a floor of 0.0 is not
    proven: "at least zero" is no longer spelled "proven" (R2.4)."""
    proof = PoweredProof(
        headline_uplift=0.0,
        replicates=MIN_POWERED_REPLICATES,
        incomplete=False,
        within_fidelity_bound=True,
    )
    assert verdict(proof, floor=0.0) == EXIT_UNAVAILABLE


def test_incomplete_run_is_never_a_pass() -> None:
    """The exact shape of the previously committed artifact: incomplete, unpowered,
    fidelity unknown, headline 0.0. It used to exit 0; it must not."""
    proof = PoweredProof(
        headline_uplift=0.0,
        replicates=0,
        incomplete=True,
        within_fidelity_bound=None,
    )
    assert verdict(proof, floor=0.0) == EXIT_UNAVAILABLE


def test_large_gain_out_of_fidelity_bound_is_never_a_pass() -> None:
    """R2.4: an out-of-bound result is non-zero irrespective of headline magnitude."""
    for within in (False, None):
        proof = PoweredProof(
            headline_uplift=99.0,
            replicates=MIN_POWERED_REPLICATES,
            incomplete=False,
            within_fidelity_bound=within,
        )
        assert verdict(proof, floor=0.0) == EXIT_UNAVAILABLE
