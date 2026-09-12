"""Property-based test that a recorded number is recomputed or reported unavailable.

Feature: decision-quality-proof, Property 71: A recorded number is recomputed or reported
unavailable, never `ok`

    *For any* published sidecar and *any* recorded value, the registered check reports
    unavailable -- never `ok` and never a pass -- whenever the recorded CRPS or the
    recorded 90% coverage cannot be recomputed from the sidecar, including when the
    held-out block is absent, is shorter than the committed minimum row count, or omits
    the conformal-adjusted bounds the coverage recompute reads; reports non-passing
    naming both the recorded and the recomputed value whenever their absolute difference
    exceeds the committed allowance; reports non-passing naming the measured value and
    the floor whenever recomputed coverage falls below the committed floor; and reports
    passing only when both values were recomputed and both hold.

The load-bearing clause is the negative one
-------------------------------------------

``published_checkpoint_truth.evaluate`` acted on ``Outcome.FAIL`` alone -- ``if
crps.outcome is Outcome.FAIL: return fail`` then ``return ok`` -- so an ``UNAVAILABLE``
recompute **fell through to** ``ok``. It also never called ``validate_entry``, so an entry
recording no ``final_crps`` produced ``recorded=None`` -> ``UNAVAILABLE`` -> a published
PASS. And ``UNAVAILABLE`` was the outcome for a sidecar carrying no ``heldout`` block,
which was every artifact ``agents/demand_prophet/training/train.py`` produced. The hole
was not hypothetical; it was the live state of the registry's C46 row.

So the clause asserted here, unconditionally rather than per branch, is: **no observation
reaches a passing status through an UNAVAILABLE outcome.** It is asserted twice, at both
levels the fall-through crossed -- the gate's own aggregate outcome, and the published
gate status the aggregate projects into through ``verify_claims.GATE_STATUS``.

Three couplings this file makes mechanical rather than documented
----------------------------------------------------------------

1. **The mirrored minimum.** ``train.py::HELDOUT_MIN_ROWS`` mirrors
   ``checkpoint-truth.yaml::tolerances.final_crps.min_samples``. A mirror nothing compares
   is a second source of truth, so the equality is asserted. It is read by **AST**, not by
   import: importing ``train.py`` drags in torch, which is not a cost the fast verify step
   should pay, and a grep for the name would not tell us the value it is bound to.
2. **The published keys and the read keys.** ``train.py::HeldoutHorizon`` declares the
   fields a published block carries; ``published_checkpoint_truth`` declares the keys the
   coverage recompute reads. If those two sets drift, the recompute becomes permanently
   unavailable against artifacts that look complete -- exactly the failure this task
   removes -- so the containment is asserted, in the direction that matters.
3. **The status vocabulary.** Every ``Outcome`` this gate can emit must be translatable by
   ``GATE_STATUS``; an untranslatable member raises ``KeyError``, which ``_run_check``
   coerces to FAIL, moving the published counts for a reason unrelated to the subject.

Why a property and not examples. The claim is not "one sidecar was mishandled"; it is that
the space of (published block, recorded value) pairs contains states with no recomputable
answer, and that silence must never read as a pass. Totality over that space is the claim,
so it is quantified over the space -- and the two refusal paths that matter most are *also*
proven by construction below, because "no generated example reached the refusal" is not
evidence that the refusal works.

I-0 and $0: nothing is trained, fetched or built. The policy, registry, fetcher and tree
root are all injected, so the committed ``published_checkpoints.json`` is never read and no
socket is opened. Every threshold is read from the committed policy (AD-13); there is no
threshold literal below. Budget inherited from the root ``conftest.py`` profile.

**Validates: Requirements 8.9, 8.10, 9.8, 9.13, 9.14**
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Final

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.audit import verify_claims
from scripts.audit.published_checkpoint_truth import (
    HELDOUT_LOWER_KEY,
    HELDOUT_UPPER_KEY,
    SERVING_NAME,
    CheckpointTruthReport,  # noqa: TC002 - runtime import: typeguard may resolve
    Clause,
    Outcome,
    assess,
    policy,
    recompute_coverage_p90,
    recompute_final_crps,
)

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
TRAIN_PY: Final[Path] = ROOT / "agents" / "demand_prophet" / "training" / "train.py"

POLICY: Final = policy()
FLOOR: Final = POLICY.floors.coverage_p90
TOLERANCE: Final = POLICY.tolerances.final_crps
LEVELS: Final[tuple[float, ...]] = TOLERANCE.quantile_levels
BLOCK_KEY: Final[str] = TOLERANCE.sidecar_block
MIN_ROWS: Final[int] = TOLERANCE.min_samples
REAL_PREFIX: Final[str] = POLICY.classification.real.version_prefixes[0]
SIDECAR_NAME: Final[str] = POLICY.source.sidecar_filename.format(name=SERVING_NAME)

_REPO: Final[str] = "example-owner/synapse-demand-prophet"
_SHA: Final[str] = "a1b2c3d"
#: The names ``train.py`` must declare on a published horizon for both recomputes to
#: have an input. Read from the gate where the gate owns them.
PUBLISHED_HORIZON_KEYS: Final[frozenset[str]] = frozenset(
    {"predictions", "actuals", HELDOUT_LOWER_KEY, HELDOUT_UPPER_KEY}
)

#: Only PASS is a pass. A SKIP is not a PASS and neither is UNAVAILABLE (I-7).
NON_PASSING: Final[frozenset[Outcome]] = frozenset(Outcome) - {Outcome.PASS}
#: Whatever PASS is spelled as in the published registry, derived not restated.
PASSING_STATUS: Final[str] = verify_claims.GATE_STATUS["ok"]

#: The bias on the raw quantile columns and the conformal radius that widens them.
#: Chosen so the RAW band excludes every actual while the ADJUSTED band includes it.
_BIAS: Final[float] = 2.0
_RADIUS: Final[float] = 2.0


# ---------------------------------------------------------------------------
# The reference computations, restated from the definitions the policy names
# ---------------------------------------------------------------------------


def _pinball(errors: list[float], level: float) -> float:
    total = 0.0
    for error in errors:
        total += level * error if error >= 0.0 else (level - 1.0) * error
    return total / len(errors)


def reference_crps(predictions: list[list[float]], actuals: list[float]) -> float:
    """Mean pinball loss over the levels, for one horizon -- the training objective."""
    per_level = [
        _pinball(
            [actual - row[index] for row, actual in zip(predictions, actuals, strict=True)],
            level,
        )
        for index, level in enumerate(LEVELS)
    ]
    return sum(per_level) / len(per_level)


def heldout_rows(count: int) -> tuple[list[list[float]], list[float]]:
    """``count`` rows whose RAW quantile band excludes every actual (biased high).

    The bias is deliberate: it makes the difference between the raw quantile columns and
    the conformal-adjusted bounds *observable*. A recompute that scored actuals against
    ``predictions`` would land on zero coverage over these rows and fail the positive
    control, so the 80%-versus-90% conflation cannot pass unnoticed.
    """
    actuals = [float(index) for index in range(count)]
    centre = (len(LEVELS) - 1) / 2.0
    predictions = [
        [actual + _BIAS + (index - centre) for index in range(len(LEVELS))]
        for actual in actuals
    ]
    return predictions, actuals


def adjusted_bounds(
    predictions: list[list[float]],
) -> tuple[list[float], list[float]]:
    """``max(q_lo - Q, 0)`` and ``q_hi + Q`` -- the CQR widening, clamp included."""
    return (
        [max(row[0] - _RADIUS, 0.0) for row in predictions],
        [row[-1] + _RADIUS for row in predictions],
    )


# ---------------------------------------------------------------------------
# The generated space: every way a published block can fail to support a recompute
# ---------------------------------------------------------------------------


@st.composite
def block_cases(draw: st.DrawFn) -> dict[str, Any]:
    """Draw one published-block case as a mapping of its independent mutation axes."""
    return {
        "rows": draw(st.integers(min_value=0, max_value=MIN_ROWS + 3)),
        "keep_lower": draw(st.booleans()),
        "keep_upper": draw(st.booleans()),
        "trim_bounds": draw(st.booleans()),
        "taint_actual": draw(st.booleans()),
        "covered": draw(st.booleans()),
        "nested": draw(st.booleans()),
    }


def build_block(case: dict[str, Any]) -> dict[str, Any]:
    """Realise one case as the JSON block a published sidecar would carry."""
    rows = int(case["rows"])
    predictions, actuals = heldout_rows(rows)
    if case["covered"]:
        # The conformal-adjusted band, which brings every actual inside it.
        lower, upper = adjusted_bounds(predictions)
    else:
        # A band sitting entirely above every actual: recomputable, covering none.
        lower = [actual + 8.0 for actual in actuals]
        upper = [actual + 9.0 for actual in actuals]
    if case["trim_bounds"] and upper:
        upper = upper[:-1]
    payload: dict[str, Any] = {
        "predictions": [list(row) for row in predictions],
        "actuals": list(actuals),
    }
    if case["taint_actual"] and payload["actuals"]:
        payload["actuals"][0] = "not-a-number"
    if case["keep_lower"]:
        payload[HELDOUT_LOWER_KEY] = lower
    if case["keep_upper"]:
        payload[HELDOUT_UPPER_KEY] = upper
    if case["nested"]:
        return {"quantile_levels": list(LEVELS), "horizons": {"1h": payload}}
    payload["quantile_levels"] = list(LEVELS)
    return payload


def expected_coverage_outcome(case: dict[str, Any]) -> Outcome:
    """The coverage recompute's outcome, derived from the case's axes alone."""
    if not (case["keep_lower"] and case["keep_upper"]):
        return Outcome.UNAVAILABLE  # the adjusted bounds are not published
    if int(case["rows"]) == 0:
        return Outcome.UNAVAILABLE  # no held-out rows
    if case["taint_actual"]:
        return Outcome.UNAVAILABLE  # an actual that is not a number
    if case["trim_bounds"]:
        return Outcome.UNAVAILABLE  # bound and actual lists disagree in length
    if int(case["rows"]) < MIN_ROWS:
        return Outcome.UNAVAILABLE  # below the committed minimum
    return Outcome.PASS if case["covered"] else Outcome.FAIL


def expected_crps_outcome(case: dict[str, Any]) -> Outcome:
    """The CRPS recompute's outcome for the same case, with ``recorded`` set exactly.

    The bound axes do not appear: the CRPS recompute reads ``predictions``/``actuals``
    and is deliberately unaffected by whether the adjusted bounds were published. That
    asymmetry is the point -- it is why a sidecar can recompute one number and not the
    other, and why the coverage clause needed its own refusal path.
    """
    if int(case["rows"]) == 0 or case["taint_actual"] or int(case["rows"]) < MIN_ROWS:
        return Outcome.UNAVAILABLE
    return Outcome.PASS


def recorded_crps_for(case: dict[str, Any]) -> float:
    """A recorded ``final_crps`` that matches the block exactly, when there is one."""
    rows = int(case["rows"])
    if rows == 0 or case["taint_actual"]:
        return 0.0
    predictions, actuals = heldout_rows(rows)
    return reference_crps(predictions, actuals)


def build_sidecar(case: dict[str, Any], *, coverage: float) -> dict[str, Any]:
    """A real, non-smoke, sha-pinned sidecar whose only variable is the block."""
    return {
        "version": f"{REAL_PREFIX}{_SHA}",
        "arch": {},
        POLICY.classification.smoke.sidecar_flag: False,
        "calibrator": {"last_coverage_p90": coverage},
        BLOCK_KEY: build_block(case),
    }


def landed_entry(*, final_crps: float) -> dict[str, Any]:
    """A validated record of the shape the runbook's step-5 output produces."""
    return {
        "repo": _REPO,
        "sha": _SHA,
        "coverage_p90": 1.0,
        "final_crps": final_crps,
        "trained_at": "2026-06-01T12:00:00Z",
        "rows": 1_125_000,
    }


def report_for(
    sidecar: dict[str, Any], entry: dict[str, Any], directory: Path
) -> CheckpointTruthReport:
    """Drive the registered surface with everything injected -- no socket, no repo read."""
    path = directory / SIDECAR_NAME
    path.write_text(json.dumps(sidecar, sort_keys=True), encoding="utf-8")

    def _fetch(repo_id: str, filename: str) -> str:
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


@pytest.fixture(scope="module")
def hub(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A module-scoped scratch dir standing in for the HF Hub cache (no network)."""
    return tmp_path_factory.mktemp("recompute_or_unavailable")


# ---------------------------------------------------------------------------
# Property 71 -- the two recomputes, directly
# ---------------------------------------------------------------------------
# Feature: decision-quality-proof, Property 71: A recorded number is recomputed or reported
# unavailable, never ok # noqa: E501
@settings(deadline=None)
@given(case=block_cases())
def test_a_recompute_that_cannot_be_performed_reports_unavailable_and_measures_nothing(
    case: dict[str, Any],
) -> None:
    """Each recompute decides, or refuses -- and a refusal reports no measurement.

    Reporting ``measured=None`` alongside ``UNAVAILABLE`` is the half that stops a
    refusal from being read as a number: a gate that returned a partial figure with an
    unavailable verdict invites a reader to use the figure anyway.

    **Validates: Requirements 8.9, 8.10, 9.13, 9.14**
    """
    sidecar = build_sidecar(case, coverage=1.0)

    coverage = recompute_coverage_p90(sidecar, FLOOR, block=BLOCK_KEY, min_rows=MIN_ROWS)
    assert coverage.outcome is expected_coverage_outcome(case), coverage.detail
    assert coverage.basis == "recompute"
    assert coverage.floor == FLOOR.value
    assert coverage.min_rows == MIN_ROWS
    # Both numbers on every branch (R8.10), including the branch that measured nothing.
    assert str(FLOOR.value) in coverage.detail
    assert (coverage.measured is None) is (coverage.outcome is Outcome.UNAVAILABLE)
    assert (coverage.outcome is Outcome.PASS) is coverage.holds
    if coverage.outcome is not Outcome.UNAVAILABLE:
        assert coverage.rows >= MIN_ROWS
        assert coverage.measured is not None
        assert coverage.horizons != ()
        assert len(coverage.per_horizon_coverage) == len(coverage.horizons)

    crps = recompute_final_crps(sidecar, TOLERANCE, recorded=recorded_crps_for(case))
    assert crps.outcome is expected_crps_outcome(case), crps.detail
    assert (crps.recomputed is None) is (crps.outcome is Outcome.UNAVAILABLE)

    # An absent recorded value is equally unrecomputable, and an absent artifact more so.
    assert recompute_final_crps(sidecar, TOLERANCE, recorded=None).outcome is (
        Outcome.UNAVAILABLE
    )
    absent = recompute_coverage_p90(None, FLOOR, block=BLOCK_KEY, min_rows=MIN_ROWS)
    assert absent.outcome is Outcome.UNAVAILABLE
    assert absent.measured is None


# ---------------------------------------------------------------------------
# Property 71 -- the negative clause, through the registered surface
# ---------------------------------------------------------------------------
@settings(deadline=None)
@given(case=block_cases(), coverage=st.floats(min_value=0.0, max_value=1.0))
def test_no_observation_reaches_a_passing_status_through_an_unavailable_outcome(
    case: dict[str, Any], coverage: float, hub: Path
) -> None:
    """The clause the fall-through violated, asserted unconditionally at both levels.

    Not "on the branches where a block is absent" -- on every generated observation. An
    UNAVAILABLE finding and a passing verdict must never coexist, and the projection into
    the published gate status must not launder one into the other either.

    **Validates: Requirements 9.8, 9.14**
    """
    sidecar = build_sidecar(case, coverage=coverage)
    report = report_for(sidecar, landed_entry(final_crps=recorded_crps_for(case)), hub)

    unavailable = tuple(f for f in report.findings if f.outcome is Outcome.UNAVAILABLE)
    status = verify_claims.GATE_STATUS[report.outcome.value]

    # (1) The gate's own aggregate never passes over an unavailable clause.
    assert not (unavailable and report.outcome is Outcome.PASS)
    # (2) Nor does the status the published registry row carries.
    assert not (unavailable and status == PASSING_STATUS)
    # (3) And the aggregate agrees with the clause vocabulary rather than outranking it:
    #     an unavailable clause with no failing clause IS an unavailable report.
    failing = tuple(f for f in report.findings if f.outcome is Outcome.FAIL)
    if unavailable and not failing:
        assert report.outcome is Outcome.UNAVAILABLE
        assert report.outcome in NON_PASSING
        assert report.exit_code != 0

    # The expected clause outcomes, derived from the case rather than from the report.
    expected_coverage = expected_coverage_outcome(case)
    recompute_findings = tuple(
        f for f in report.findings if f.clause is Clause.COVERAGE_RECOMPUTE
    )
    assert [f.outcome for f in recompute_findings] == (
        [] if expected_coverage is Outcome.PASS else [expected_coverage]
    )
    assert report.coverage_recompute is not None
    assert report.coverage_recompute.outcome is expected_coverage


# ---------------------------------------------------------------------------
# The refusal paths, proven by construction rather than by generation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "missing",
    [HELDOUT_LOWER_KEY, HELDOUT_UPPER_KEY],
)
def test_a_block_missing_either_adjusted_bound_is_unavailable_and_names_the_key(
    missing: str,
) -> None:
    """One bound is not half an interval, and the raw quantile columns are not the other.

    The refusal is specific: with levels ``[0.1, 0.5, 0.9]`` the published
    ``predictions`` columns span a nominal 80% band, so scoring actuals against them
    would report a different interval's coverage against INV-DP-002's 90% floor. The
    gate must refuse rather than substitute, and must name what it wanted.

    **Validates: Requirements 9.13, 9.14**
    """
    predictions, actuals = heldout_rows(MIN_ROWS)
    lower, upper = adjusted_bounds(predictions)
    block: dict[str, Any] = {
        "quantile_levels": list(LEVELS),
        "predictions": predictions,
        "actuals": actuals,
        HELDOUT_LOWER_KEY: lower,
        HELDOUT_UPPER_KEY: upper,
    }
    del block[missing]

    recompute = recompute_coverage_p90(
        {BLOCK_KEY: block}, FLOOR, block=BLOCK_KEY, min_rows=MIN_ROWS
    )
    assert recompute.outcome is Outcome.UNAVAILABLE
    assert recompute.measured is None
    assert missing in recompute.detail
    # And it says why the raw columns are not a substitute, so nobody adds a fallback.
    assert "never substituted" in recompute.detail


def test_a_fully_recomputable_publication_passes_so_always_unavailable_is_not_enough(
    hub: Path,
) -> None:
    """The positive control. A gate that refused everything would satisfy the clauses above.

    It also pins the two recomputes as *independent* evidence: the recomputed coverage is
    computed here from the published bounds, and the recomputed CRPS from the published
    quantile columns, and the report must carry both.

    **Validates: Requirements 8.9, 9.13**
    """
    predictions, actuals = heldout_rows(MIN_ROWS)
    case = {
        "rows": MIN_ROWS,
        "keep_lower": True,
        "keep_upper": True,
        "trim_bounds": False,
        "taint_actual": False,
        "covered": True,
        "nested": False,
    }
    sidecar = build_sidecar(case, coverage=1.0)
    entry = landed_entry(final_crps=reference_crps(predictions, actuals))
    report = report_for(sidecar, entry, hub)

    assert report.outcome is Outcome.PASS, report.detail
    assert report.findings == ()
    assert report.exit_code == 0
    assert verify_claims.GATE_STATUS[report.outcome.value] == PASSING_STATUS
    assert report.coverage_recompute is not None
    assert report.coverage_recompute.measured == pytest.approx(1.0)
    assert report.coverage_recompute.rows == MIN_ROWS
    # Scored against the ADJUSTED band, provably: the raw quantile columns of this same
    # block exclude every actual, so a recompute reading them would land on 0.0.
    assert all(row[0] > actual for row, actual in zip(predictions, actuals, strict=True))
    assert report.crps is not None
    assert report.crps.recomputed == pytest.approx(reference_crps(predictions, actuals))
    # The read is retained as a cross-check beside the recompute, not replaced by it.
    assert report.coverage is not None
    assert report.coverage.basis == "read"
    assert report.coverage_recompute.cross_check == report.coverage.measured


# ---------------------------------------------------------------------------
# The three couplings, asserted rather than documented
# ---------------------------------------------------------------------------


def _train_module() -> ast.Module:
    """``train.py`` parsed, never imported: importing it would pull in torch."""
    assert TRAIN_PY.is_file(), f"{TRAIN_PY} is missing; the coupling cannot be checked"
    return ast.parse(TRAIN_PY.read_text(encoding="utf-8"))


def _annotated_int(module: ast.Module, name: str) -> int | None:
    for node in module.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and isinstance(node.value, ast.Constant)
        ):
            value = node.value.value
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            return None
    return None


def _class_fields(module: ast.Module, name: str) -> frozenset[str]:
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return frozenset(
                field.target.id
                for field in node.body
                if isinstance(field, ast.AnnAssign) and isinstance(field.target, ast.Name)
            )
    return frozenset()


def test_the_training_mirror_and_the_committed_minimum_declare_the_same_row_count() -> None:
    """A mirror nothing compares is a second source of truth (AD-13).

    ``train.py`` publishes at least this many held-out rows and the gate refuses fewer
    than this many. If the two drifted, a compliant training run would produce artifacts
    the gate reports UNAVAILABLE, and the failure would look like a publication problem
    rather than a declaration problem.

    **Validates: Requirements 9.13**
    """
    declared = _annotated_int(_train_module(), "HELDOUT_MIN_ROWS")

    assert declared is not None, "train.py declares no integer HELDOUT_MIN_ROWS constant"
    assert declared == MIN_ROWS, (
        f"train.py mirrors HELDOUT_MIN_ROWS={declared} while checkpoint-truth.yaml"
        f"::tolerances.final_crps.min_samples is {MIN_ROWS}"
    )


def test_the_published_horizon_declares_every_key_the_recomputes_read() -> None:
    """The shape written and the shape read are one shape, or the recompute is dead.

    Containment is asserted in the direction that matters: a horizon may carry *more*
    than the recomputes read, but a key a recompute needs and the publisher never writes
    makes the gate permanently unavailable against artifacts that look complete.

    **Validates: Requirements 9.13**
    """
    fields = _class_fields(_train_module(), "HeldoutHorizon")

    assert fields, "train.py declares no HeldoutHorizon fields"
    missing = PUBLISHED_HORIZON_KEYS - fields
    assert not missing, (
        f"train.py::HeldoutHorizon publishes no {sorted(missing)}, which the coverage and "
        "CRPS recomputes read; every artifact it writes would be UNAVAILABLE"
    )


def test_every_outcome_this_gate_emits_is_translatable_by_the_registry_status_table() -> None:
    """The coupling a new ``Outcome`` member owes, made mechanical instead of remembered.

    ``GATE_STATUS`` is the shared table the registry rows use to translate a gate's own
    verdict string into ``PASS``/``FAIL``/``SKIP``. A member this gate can emit but that
    table cannot translate raises ``KeyError``, which ``_run_check`` coerces to FAIL --
    moving the published counts for a reason unrelated to the subject, which is exactly
    what a fourth outcome did to C71 on its first push.

    **Validates: Requirements 9.14**
    """
    untranslatable = {outcome.value for outcome in Outcome} - set(verify_claims.GATE_STATUS)

    assert not untranslatable, (
        f"published_checkpoint_truth can report {sorted(untranslatable)}, which "
        "verify_claims.GATE_STATUS cannot translate"
    )
    # And the two states that are not passes are not spelled as one (I-7).
    assert verify_claims.GATE_STATUS[Outcome.UNAVAILABLE.value] != PASSING_STATUS
    assert verify_claims.GATE_STATUS[Outcome.SKIP.value] != PASSING_STATUS
    assert verify_claims.GATE_STATUS[Outcome.PASS.value] == PASSING_STATUS


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
