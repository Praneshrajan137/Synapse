"""Property-based test for the C46 published-checkpoint gate decision.

Feature: core-purpose-uplift, Property 16: The C43 published-checkpoint gate decision is
correct over sidecar/registry inputs

    *For any* combination of published sidecar ``smoke`` flag, ``last_coverage_p90``,
    recorded registry sha, published version string, and published held-out block shape
    (with the registry populated and the remote reachable), the **registered**
    published-checkpoint check reports ``PASS`` if and only if the artifact is non-smoke
    AND recorded coverage ``>= 0.85`` AND the recorded sha appears in the published
    version AND both recomputes were performed and held; otherwise it reports a
    non-passing outcome -- ``FAIL`` for a smoke artifact, uncalibrated coverage, sha
    drift, or a recomputed coverage below the floor, and ``UNAVAILABLE`` for an
    unmarked artifact or a number that could not be recomputed at all.

    Requirement 5.3: a pass requires non-smoke + ``last_coverage_p90 >= 0.85`` + recorded
    sha matching the published version.
    Requirement 5.4: a smoke artifact is a failure.
    Requirement 5.5: coverage below the 0.85 floor is a failure.
    Requirement 5.6: a recorded sha absent from the published version is a drift failure.

Why this file's subject moved, and the discrepancy that is recorded rather than resolved
----------------------------------------------------------------------------------------

This file used to drive :func:`~scripts.audit.published_checkpoint_truth.evaluate`, and
``.kiro/specs/core-purpose-uplift/design.md`` (Property 16, ``:320-322``) still names
``evaluate()`` and still calls the check ``C43``. Both readings are now stale, and
**neither the tag above nor the older spec has been edited to hide that**:

* The check is **C46**, not C43. C43 is "All 8 agents expose POST /a2a for consensus".
  ``verify_claims.py``'s C46 docstring records a SKIP branch that once mis-stamped itself
  ``C43``, so an unavailable published-checkpoint probe landed on another check's row.
  The tag line is left verbatim so it still resolves against the design heading it was
  generated from; the identifier is corrected here, in the title and in the prose.
* The **registered surface** is now :func:`~scripts.audit.published_checkpoint_truth.assess`,
  re-pointed by ``decision-quality-proof`` task 18.3 (AD-19, R9.14). ``evaluate`` is
  retained but is no longer a gate, so pinning it would pin a surface nothing consumes --
  and worse, would pin the defect that motivated the move: ``evaluate`` acts on
  ``Outcome.FAIL`` alone, so an ``UNAVAILABLE`` recompute falls through to ``ok``.

R5.3-R5.6 remain validated because the re-point is strictly **stricter**: every input this
file previously required to be ``fail`` is still non-passing, and inputs that previously
reached ``ok`` without a recompute are now ``UNAVAILABLE``. A criterion cannot be weakened
by moving it onto a surface that refuses more; it can only be weakened by moving it onto
one that refuses less, which is the direction task 18.3 reversed.

What this file asserts, and what it deliberately leaves to its neighbours
-------------------------------------------------------------------------

Here: the **registered decision** over the R5.3-R5.6 input space, extended by the one
dimension the re-point makes decisive -- the shape of the published ``heldout`` block.
Not here: the three-way classification's own totality and detail obligations, the CRPS
allowance arithmetic, and the local-substitution refusal, all of which
``test_checkpoint_claim_classification_property.py`` (purpose-achievement-audit
Property 17) already drives against ``assess``; and the outcome-to-gate-status
projection, which ``test_smoke_artifact_distinction_property.py`` (Property 72) owns.

The expected verdict is recomputed here from the raw sidecar/registry fields and from the
block shape's declared consequence, so the test states the rule independently rather than
echoing ``assess``'s branch order. Because the registry is populated and the remote
answers, ``SKIP`` is never an acceptable verdict: every example must be a decided
``PASS``, ``FAIL`` or ``UNAVAILABLE``.

The property is network-free and repo-safe: the registry payload, the policy, the fetcher
and the tree root are all injected, so the committed ``published_checkpoints.json`` is
never read, no socket is opened and $0 is spent. Every threshold, marker and filename is
read from ``infrastructure/quality/checkpoint-truth.yaml`` through the parsed policy
(AD-13); there is no threshold literal in this file.

**Validates: Requirements 5.3, 5.4, 5.5, 5.6**
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.audit.published_checkpoint_truth import (
    COVERAGE_FLOOR,
    HELDOUT_LOWER_KEY,
    HELDOUT_UPPER_KEY,
    SERVING_NAME,
    CheckpointTruthReport,  # noqa: TC002 - runtime import: typeguard may resolve
    Clause,
    Outcome,
    assess,
    policy,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

_REPO = "example-owner/synapse-demand-prophet"

POLICY: Final = policy()
FLOOR: Final = POLICY.floors.coverage_p90
TOLERANCE: Final = POLICY.tolerances.final_crps
LEVELS: Final[tuple[float, ...]] = TOLERANCE.quantile_levels
SMOKE_PREFIXES: Final[tuple[str, ...]] = POLICY.classification.smoke.version_prefixes
REAL_PREFIXES: Final[tuple[str, ...]] = POLICY.classification.real.version_prefixes
SIDECAR_NAME: Final[str] = POLICY.source.sidecar_filename.format(name=SERVING_NAME)

#: A registry coverage that is always valid, so the *record* is never the reason a
#: verdict moves: this property varies what the artifact publishes, not what the
#: operator recorded. ``validate_entry`` rejects a record below the floor outright.
RECORD_COVERAGE: Final[float] = 1.0

#: The bias applied to the raw quantile columns, and the conformal radius that widens
#: them. Chosen so the RAW band excludes every actual and the ADJUSTED band includes it,
#: which is what makes a substitution of one for the other visible as a failure.
_BIAS: Final[float] = 2.0
_RADIUS: Final[float] = 2.0


# ---------------------------------------------------------------------------
# The rule, restated from the raw fields
# ---------------------------------------------------------------------------


def _matching_prefix(version: str, prefixes: Sequence[str]) -> bool:
    """Whether ``version`` carries any declared prefix (longest first is irrelevant here)."""
    return any(version.startswith(prefix) for prefix in prefixes)


def _pinball(errors: Sequence[float], level: float) -> float:
    """Mean pinball loss at one level -- the training objective's definition."""
    total = 0.0
    for error in errors:
        total += level * error if error >= 0.0 else (level - 1.0) * error
    return total / len(errors)


def reference_crps(
    predictions: Sequence[Sequence[float]], actuals: Sequence[float]
) -> float:
    """The value a correct recompute must land on for one horizon.

    Restated here rather than imported: a reference computed by the subject cannot
    falsify the subject.
    """
    per_level = [
        _pinball(
            [actual - row[index] for row, actual in zip(predictions, actuals, strict=True)],
            level,
        )
        for index, level in enumerate(LEVELS)
    ]
    return sum(per_level) / len(per_level)


def heldout_rows(count: int) -> tuple[list[list[float]], list[float]]:
    """``count`` held-out rows whose RAW quantile band excludes every actual.

    Deliberately biased high by :data:`_BIAS`. A gate that read the ``predictions``
    columns instead of the published ``lower_90``/``upper_90`` bounds would recompute
    **zero** coverage over these rows and fail the positive controls below -- so the
    80%-versus-90% conflation this task warns about is detectable here rather than
    invisible. The conformal-adjusted bounds widen the same band by :data:`_RADIUS`,
    which is what brings every actual inside it.
    """
    actuals = [float(index) for index in range(count)]
    centre = (len(LEVELS) - 1) / 2.0
    predictions = [
        [actual + _BIAS + (index - centre) for index in range(len(LEVELS))]
        for actual in actuals
    ]
    return predictions, actuals


def adjusted_bounds(
    predictions: Sequence[Sequence[float]],
) -> tuple[list[float], list[float]]:
    """The CQR widening ``ConformalCalibrator.predict_intervals`` applies, restated.

    ``max(q_lo - Q, 0)`` and ``q_hi + Q`` for a single symmetric radius, including the
    clamp at zero, so the fixture is the shape a real publication carries.
    """
    lower = [max(row[0] - _RADIUS, 0.0) for row in predictions]
    upper = [row[-1] + _RADIUS for row in predictions]
    return lower, upper


ROWS: Final[int] = TOLERANCE.min_samples
PREDICTIONS, ACTUALS = heldout_rows(ROWS)
REFERENCE_CRPS: Final[float] = reference_crps(PREDICTIONS, ACTUALS)


def _block(
    predictions: Sequence[Sequence[float]],
    actuals: Sequence[float],
    *,
    bounds: bool,
) -> dict[str, Any]:
    """The flat single-horizon block, with or without the conformal-adjusted bounds."""
    block: dict[str, Any] = {
        "quantile_levels": list(LEVELS),
        "predictions": [list(row) for row in predictions],
        "actuals": list(actuals),
    }
    if bounds:
        lower, upper = adjusted_bounds(predictions)
        block[HELDOUT_LOWER_KEY] = lower
        block[HELDOUT_UPPER_KEY] = upper
    return block


def _uncovered_block() -> dict[str, Any]:
    """Bounds that sit entirely above every actual: recomputable, and coverage 0."""
    block = _block(PREDICTIONS, ACTUALS, bounds=False)
    block[HELDOUT_LOWER_KEY] = [actual + 8.0 for actual in ACTUALS]
    block[HELDOUT_UPPER_KEY] = [actual + 9.0 for actual in ACTUALS]
    return block


_SHORT: Final[int] = max(TOLERANCE.min_samples - 1, 1)
_SHORT_PREDICTIONS, _SHORT_ACTUALS = heldout_rows(_SHORT)

#: Each shape's declared consequence on the two recompute clauses. Written as data so
#: the property quantifies over shapes whose outcome is known **by construction**
#: rather than hoping a generator stumbles onto the refusal path.
_MISSING: Final = object()
BLOCK_SHAPES: Final[dict[str, tuple[Any, frozenset[Outcome]]]] = {
    # Fully published: both recomputes run and hold. The positive control.
    "covered": (_block(PREDICTIONS, ACTUALS, bounds=True), frozenset()),
    # The live state before R9.13: predictions and actuals but no adjusted bounds, so
    # `final_crps` recomputes while coverage cannot. This is the case `evaluate`
    # reported as `ok`.
    "no-bounds": (_block(PREDICTIONS, ACTUALS, bounds=False), frozenset({Outcome.UNAVAILABLE})),
    # No block at all: neither recompute has an input.
    "absent": (_MISSING, frozenset({Outcome.UNAVAILABLE})),
    # Shorter than the committed minimum: an estimate that noisy is not evidence.
    "short": (
        _block(_SHORT_PREDICTIONS, _SHORT_ACTUALS, bounds=True),
        frozenset({Outcome.UNAVAILABLE}),
    ),
    # Recomputable and genuinely uncalibrated: the recompute is the verdict, and it
    # FAILs on the floor rather than deferring to the recorded number.
    "uncovered": (_uncovered_block(), frozenset({Outcome.FAIL})),
}


def expected_outcome(smoke: Any, coverage: Any, sha: str, version: str, shape: str) -> Outcome:
    """The outcome the registered surface owes, derived from the inputs alone.

    Aggregation is ``FAIL > UNAVAILABLE > SKIP > PASS``: a failure outranks a gap, and a
    gap is never a pass (I-7).
    """
    outcomes: set[Outcome] = set(BLOCK_SHAPES[shape][1])
    if smoke is True or _matching_prefix(version, SMOKE_PREFIXES):
        outcomes.add(Outcome.FAIL)  # R5.4
    elif not _matching_prefix(version, REAL_PREFIXES):
        outcomes.add(Outcome.UNAVAILABLE)  # an unmarked artifact is not promoted
    calibrated = isinstance(coverage, (int, float)) and float(coverage) >= COVERAGE_FLOOR
    if not calibrated:
        outcomes.add(Outcome.FAIL)  # R5.5
    if sha.strip() not in version:
        outcomes.add(Outcome.FAIL)  # R5.6
    for outcome in (Outcome.FAIL, Outcome.UNAVAILABLE, Outcome.SKIP):
        if outcome in outcomes:
            return outcome
    return Outcome.PASS


# ---------------------------------------------------------------------------
# Strategies
#
# The generators stay inside the space a published sidecar/registry pair can actually
# occupy -- a boolean-or-absent ``smoke`` flag, a probability-or-absent coverage, a hex
# sha, a ``<kind>_<sha>`` version string and one of the five block shapes -- while
# weighting the exact decision boundaries (the floor, an empty sha, a sha that
# is//isn't a substring of the version) so they are hit densely instead of by luck.
# ---------------------------------------------------------------------------

_smoke = st.sampled_from([True, False, _MISSING])

_coverage = st.one_of(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.sampled_from(
        [
            None,
            _MISSING,
            0.0,
            COVERAGE_FLOOR - 1e-9,
            COVERAGE_FLOOR,
            COVERAGE_FLOOR + 1e-9,
            0.91,
            1.0,
        ]
    ),
)

_hex7 = st.text(alphabet="0123456789abcdef", min_size=7, max_size=7)
#: An empty or blank sha is deliberately absent: ``validate_entry`` rejects it, so the
#: record would be ``invalid`` and the *registry* clause would decide the verdict rather
#: than the sha-pin clause under test. The legacy probe tolerated an unrecorded sha
#: because it never validated the record; a landed record always carries one. Whitespace
#: around a real sha is kept, because that is a shape an operator's copy-paste produces.
_sha = st.one_of(
    _hex7,
    st.sampled_from(["  a1b2c3d  ", "a1b2c3d", "deadbee", "0000000"]),
)


@st.composite
def _gate_inputs(draw: st.DrawFn) -> tuple[Any, Any, str, str, str]:
    """Draw ``(smoke, coverage, recorded_sha, published_version, block_shape)``.

    The version is often derived from the drawn sha (matching record) and often from an
    unrelated sha (drift), so both sides of the sha cross-check are exercised.
    """
    smoke = draw(_smoke)
    coverage = draw(_coverage)
    sha = draw(_sha)
    stripped = sha.strip()
    other = draw(_hex7)
    version = draw(
        st.one_of(
            st.just(f"{REAL_PREFIXES[0]}{stripped}"),
            st.just(f"{SMOKE_PREFIXES[0]}{stripped}"),
            st.just(f"{REAL_PREFIXES[0]}{other}"),
            st.just(stripped),
            st.sampled_from(["", REAL_PREFIXES[0], "version-1"]),
        )
    )
    shape = draw(st.sampled_from(sorted(BLOCK_SHAPES)))
    return smoke, coverage, sha, version, shape


def build_sidecar(smoke: Any, coverage: Any, version: str, shape: str) -> dict[str, Any]:
    """A published serving sidecar carrying only the fields the caller asked for."""
    sidecar: dict[str, Any] = {"version": version, "arch": {}}
    if smoke is not _MISSING:
        sidecar[POLICY.classification.smoke.sidecar_flag] = smoke
    if coverage is not _MISSING:
        sidecar["calibrator"] = {"last_coverage_p90": coverage}
    block = BLOCK_SHAPES[shape][0]
    if block is not _MISSING:
        sidecar[TOLERANCE.sidecar_block] = block
    return sidecar


def landed_entry(sha: str) -> dict[str, Any]:
    """A record of the shape the runbook's step-5 output produces, always valid."""
    return {
        "repo": _REPO,
        "sha": sha,
        "coverage_p90": RECORD_COVERAGE,
        "final_crps": REFERENCE_CRPS,
        "trained_at": "2026-06-01T12:00:00Z",
        "rows": 1_125_000,
    }


@pytest.fixture(scope="module")
def sidecar_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A module-scoped scratch dir standing in for the HF Hub cache (no network)."""
    return tmp_path_factory.mktemp("c46_published_sidecar")


def _report(
    sidecar: dict[str, Any], entry: dict[str, Any], directory: Path
) -> CheckpointTruthReport:
    """Drive the registered surface with an injected registry, fetcher and tree root."""
    path = directory / SIDECAR_NAME
    path.write_text(json.dumps(sidecar, sort_keys=True), encoding="utf-8")

    def _fetch(repo_id: str, filename: str) -> str:
        # The gate must ask the recorded repo for the serving-name sidecar, nothing else.
        assert repo_id == _REPO
        assert filename == SIDECAR_NAME
        return str(path)

    return assess(
        checkpoint_policy=POLICY,
        registry={SERVING_NAME: entry},
        fetch_sidecar=_fetch,
        root=directory,
        env={},
    )


# ---------------------------------------------------------------------------
# Property 16
# ---------------------------------------------------------------------------
# Feature: core-purpose-uplift, Property 16: The C43 published-checkpoint gate decision is correct over sidecar/registry inputs  # noqa: E501
@settings(deadline=None)
@given(gate_inputs=_gate_inputs())
def test_the_registered_gate_decision_is_correct_over_sidecar_and_registry_inputs(
    gate_inputs: tuple[Any, Any, str, str, str], sidecar_dir: Path
) -> None:
    """Property 16: ``PASS`` iff non-smoke AND calibrated AND sha-pinned AND recomputed.

    **Validates: Requirements 5.3, 5.4, 5.5, 5.6**
    """
    smoke, coverage, sha, version, shape = gate_inputs
    sidecar = build_sidecar(smoke, coverage, version, shape)
    report = _report(sidecar, landed_entry(sha), sidecar_dir)

    expected = expected_outcome(smoke, coverage, sha, version, shape)
    assert report.outcome is expected, (smoke, coverage, sha, version, shape, report.detail)
    # A populated registry plus a reachable remote is always a decided verdict, and a
    # decided verdict is never a SKIP.
    assert report.outcome is not Outcome.SKIP
    assert (report.exit_code == 0) is (expected is Outcome.PASS)

    # The negative clause, asserted unconditionally rather than per branch: an
    # UNAVAILABLE anywhere in the findings can never coexist with a passing report.
    unavailable = [f for f in report.findings if f.outcome is Outcome.UNAVAILABLE]
    assert not (unavailable and report.outcome is Outcome.PASS)

    if expected is Outcome.PASS:
        assert report.findings == ()
        assert SERVING_NAME in report.detail and _REPO in report.detail
        assert report.coverage_recompute is not None
        assert report.coverage_recompute.outcome is Outcome.PASS
    if smoke is True or _matching_prefix(version, SMOKE_PREFIXES):
        # R5.4: a smoke artifact fails on the classification clause and says so.
        smoke_findings = [f for f in report.findings if f.clause is Clause.CLASSIFICATION]
        assert [f.outcome for f in smoke_findings] == [Outcome.FAIL]
        assert "SMOKE" in smoke_findings[0].detail
    if not (isinstance(coverage, (int, float)) and float(coverage) >= COVERAGE_FLOOR):
        # R5.5's reporting obligation: both numbers, on the read that saw them.
        assert report.coverage is not None
        assert str(COVERAGE_FLOOR) in report.coverage.detail


# Feature: core-purpose-uplift, Property 16: The C43 published-checkpoint gate decision is correct over sidecar/registry inputs  # noqa: E501
def test_a_sidecar_publishing_no_adjusted_bounds_is_refused_rather_than_passed(
    tmp_path: Path,
) -> None:
    """The exact live state, by construction: clean on every clause but the recompute.

    This is what makes the re-point load-bearing instead of cosmetic. The sidecar here
    is a real, non-smoke, sha-pinned artifact whose recorded coverage clears the floor
    and whose ``final_crps`` recomputes exactly -- and it publishes no conformal-adjusted
    bounds, which is every artifact ``train.py`` produced before R9.13. The registered
    surface must refuse it. Proven by construction rather than left to a generator: a
    property that only ever saw recomputable blocks would assert nothing about the
    refusal path (I-7).

    **Validates: Requirements 5.3**
    """
    sha = "a1b2c3d"
    sidecar = build_sidecar(False, RECORD_COVERAGE, f"{REAL_PREFIXES[0]}{sha}", "no-bounds")
    report = _report(sidecar, landed_entry(sha), tmp_path)

    assert report.outcome is Outcome.UNAVAILABLE
    assert report.outcome is not Outcome.PASS
    assert report.exit_code == 2
    # The CRPS half really did recompute, so the refusal is the coverage half's alone.
    assert report.crps is not None and report.crps.outcome is Outcome.PASS
    assert report.coverage is not None and report.coverage.holds is True
    assert report.coverage_recompute is not None
    assert report.coverage_recompute.outcome is Outcome.UNAVAILABLE
    assert report.coverage_recompute.measured is None
    # And it names the missing keys, so the repair is the runbook step, not a debate.
    recompute_findings = [f for f in report.findings if f.clause is Clause.COVERAGE_RECOMPUTE]
    assert [f.outcome for f in recompute_findings] == [Outcome.UNAVAILABLE]
    assert HELDOUT_LOWER_KEY in recompute_findings[0].detail
    assert HELDOUT_UPPER_KEY in recompute_findings[0].detail


# Feature: core-purpose-uplift, Property 16: The C43 published-checkpoint gate decision is correct over sidecar/registry inputs  # noqa: E501
def test_a_fully_published_artifact_reaches_pass(tmp_path: Path) -> None:
    """The positive control: "always non-passing" must not satisfy this file.

    Without this, every assertion above could be met by a gate that refuses
    unconditionally -- which would be a different way of establishing nothing.

    **Validates: Requirements 5.3**
    """
    sha = "a1b2c3d"
    sidecar = build_sidecar(False, RECORD_COVERAGE, f"{REAL_PREFIXES[0]}{sha}", "covered")
    report = _report(sidecar, landed_entry(sha), tmp_path)

    assert report.outcome is Outcome.PASS, report.detail
    assert report.exit_code == 0
    assert report.findings == ()
    assert report.coverage_recompute is not None
    assert report.coverage_recompute.rows == ROWS
    assert report.coverage_recompute.min_rows == TOLERANCE.min_samples
    # The verdict is the recompute's, and it reports both the value and the floor.
    assert report.coverage_recompute.measured == pytest.approx(1.0)
    assert str(FLOOR.value) in report.coverage_recompute.detail
    # And it is genuinely the ADJUSTED band that was scored: the raw quantile columns of
    # this same block exclude every actual, so a gate reading them would land on 0.0.
    raw_lower = [row[0] for row in PREDICTIONS]
    assert all(low > actual for low, actual in zip(raw_lower, ACTUALS, strict=True))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
