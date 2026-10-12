"""Property-based test that identical arms measure no uplift (the negative control).

Feature: purpose-achievement-audit, Property 16: Identical arms measure no uplift

    *For any* seeded scenario and *any* pre-registered baseline policy, when the
    Consensus_Arm is replaced by a *copy* of that Baseline_Arm so the two arms are
    identical, the harness records identical KPI aggregates for both arms, reports a
    headline uplift inside the committed noise tolerance of zero, credits no
    ``(scenario, KPI)`` pair to SYNAPSE, and yields a measurement that -- even granted
    full power and full twin fidelity -- does not read as a proven gain.

**Validates: Requirements 2.6**

Why a negative control is the load-bearing test here
----------------------------------------------------
The audit's Requirement 2 found a gate reporting PASS on an artifact that declared
``incomplete: true``: a measurement apparatus that had never been shown to be capable of
reporting *no* uplift. An instrument that cannot read zero cannot be trusted when it
reads a gain. R2.6 is the experiment that closes that: make the two arms identical and
the apparatus must say so.

Because the two arms are the same policy driven from the same replicate seeds, the
expected reading is not merely "small" -- it is exactly zero, and the per-replicate runs
are identical object for object. Both are asserted: the exact identity because it is the
truth, and the tolerance band because it is the form R2.6 states and the form a powered
run (where sampling noise is real) will be judged in.

The noise tolerance is read from committed configuration
--------------------------------------------------------
``infrastructure/quality/ratchets.json`` -> ``uplift-noise-tolerance``, recorded as a
``direction: down`` ceiling so ``bound`` is the tightest tolerance ever committed and
*widening* it is the regression -- widening being exactly how a real null-uplift failure
would be made to pass. The row's ``shipped`` block binds that bound to the live constant
``uplift/cli.py::NOISE_TOLERANCE_PP``, and ``scripts/audit/ratchet_truth.py`` enforces
the agreement (R7.8). Nothing in this file writes a tolerance literal;
:func:`test_the_noise_tolerance_is_read_from_committed_configuration` asserts the two
sources agree, so a tolerance quietly widened in either place is visible here.

Deliberately **not** restated here
----------------------------------
* ``tests/uplift/test_seed_reproducibility_property.py`` (``core-purpose-uplift``,
  Property 11) and ``tests/uplift/test_reproduction_stability_property.py`` (Property 23)
  both compare *two runs of the same configuration* against the noise tolerance. That is
  reproducibility. This file compares *two identical arms within one run*, which is a
  different claim: reproducibility says the instrument repeats itself, the negative
  control says the instrument reads zero when there is nothing to read.
* ``tests/uplift/test_arm_symmetry_no_leakage_property.py`` (Property 18) asserts the
  harness presents both arms the same cadence, costs, twin construction and observation
  fields, using recording stubs. It stops at the *inputs*. This file starts from real
  KPI outputs and goes to the headline, the contract classification, and the proof
  predicate.
* ``tests/uplift/test_uplift_truth_gate_property.py`` and
  ``tests/uplift/test_uplift_admissibility_property.py`` own the gate's verdict and
  admissibility mapping over a *constructed* artifact. This file supplies the one thing
  they cannot: a headline number produced by a real run of two identical arms, fed to
  :func:`uplift.uplift_floor.is_proven_uplift`.
* ``tests/uplift/test_arm_aggregate_property.py`` owns the mean/std arithmetic; the two
  arms' aggregates are compared to each other here, never to a formula.
* ``tests/uplift/test_decision_rule_property.py`` owns ``classify``'s totality; what is
  asserted here is only that identical arms land on ``TIE_INCONCLUSIVE``, never
  ``SYNAPSE_WINS``.

Scope this property does **not** cover, stated plainly
-----------------------------------------------------
* **The replicate count is small and generated, never ``MIN_SCENARIOS``.** R2.6 states
  the experiment at ``MIN_POWERED_REPLICATES`` (1000) per arm and asks for a headline
  whose 95% interval contains zero. **What the small count costs the claim:** no
  interval is estimated here at all. With identical arms and shared replicate seeds the
  two sample sets are *equal*, so the point estimate is exactly zero and there is no
  sampling noise for an interval to bound -- which makes this a strictly stronger
  statement about *this* configuration and a strictly weaker one about a powered run,
  where the consensus arm is a genuinely different policy and the interval is the whole
  question. Nothing here establishes that a powered 1000-replicate run of the real
  Consensus_Arm reproduces the baseline within the tolerance; that measurement is owned
  by ``.github/workflows/uplift.yml`` (task 10.5) and is forbidden on a dev box (I-0).
* **The real Consensus_Arm is not exercised.** R2.6's experiment is "replace the
  Consensus_Arm with a copy of the Baseline_Arm", so the substituted arm is by
  construction a baseline; the eight-agent ``ConsensusProtocol`` is deliberately absent.
  The arm carries ``DEFAULT_CONSENSUS_ARM`` as its name, which is how result assembly
  identifies the consensus side, so the substitution reaches every code path the real
  arm would.
* **The proof half is stipulated, not run.** The artifact this run honestly produces is
  under-powered, so ``is_proven_uplift`` would reject it for the power reason alone --
  a vacuous pass. To isolate R2.6's "SHALL NOT report a proven gain" clause, the
  *measured* headline is placed in a proof whose power, completeness and fidelity fields
  are stipulated ideal, and the predicate must still refuse it. The converse is asserted
  in the same breath (the same stipulated proof carrying a positive headline IS proven),
  so the refusal is attributable to the null measurement rather than to the stipulation.
  The honestly-produced artifact's own ``unavailable_reasons`` are asserted separately,
  so the under-power of this run is recorded rather than papered over (I-7).

Cost and routing
----------------
``@pytest.mark.slow``: every example drives the real SimPy twin
(``1 scenario x 2 arms x 1-3 replicates`` over a one- or two-step horizon, through
:func:`uplift.harness.run_closed_loop`). Owned by ``.github/workflows/ci.yml``'s
``uplift-verify`` job at ``HYPOTHESIS_PROFILE=heavy -m slow`` (task 12.2). No subprocess,
no socket, no artifact written to the repository, no ``MIN_SCENARIOS``-scale run.
``max_examples`` is never hardcoded -- it comes from the root ``conftest.py`` profiles
(``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).
"""

from __future__ import annotations

import dataclasses
import json
import math
import re
from pathlib import Path
from typing import Final, cast

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.baselines import Par_Level_Reorder, Static_Pricing
from uplift.contract import cohens_d, load_contract, relative_pct_change
from uplift.fidelity import FidelityReport
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    KPI_FIELDS,
    HarnessResult,
    LoopConfig,
    aggregate_arm,
    assemble_uplift_result,
    build_uplift_artifact,
    build_uplift_report,
    replicate_seed,
    resolve_provenance,
    run_closed_loop,
)
from uplift.interfaces import (
    ArmResult,
    DecisionPolicy,
    Direction,
    Outcome,
    Scenario,
    ScenarioRun,
    UpliftResult,
)
from uplift.uplift_floor import (
    MIN_POWERED_REPLICATES,
    UPLIFT_FLOOR,
    PoweredProof,
    UnprovenFloorRaiseError,
    is_proven_uplift,
    ratchet_to_measured,
)

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: The committed configuration the noise tolerance is read from, and the row that
#: records it. Never a literal in this file (task 10.7).
RATCHETS_FILE: Final[Path] = ROOT / "infrastructure" / "quality" / "ratchets.json"
RATCHET_ID: Final[str] = "uplift-noise-tolerance"

#: The pre-registered contract is fixed input to the measurement; load it once. The
#: headline KPI and its direction are read from it rather than written down here.
_CONTRACT = load_contract()
_HEADLINE_KPI: Final[str] = next(iter(_CONTRACT.primary_kpis))
_HEADLINE_DIRECTION: Final[Direction] = _CONTRACT.primary_kpis[_HEADLINE_KPI]

#: Fixed fidelity so the assembled result depends only on the seeds and the policies
#: (the live C34 gauge is another property's subject).
_FIDELITY = FidelityReport(kl_divergence=0.05, threshold=0.1)

#: Provenance for the artifact this run honestly produces. Pinned rather than resolved
#: from the environment so the artifact's shortfalls are the run's, not the shell's.
_REVISION: Final[str] = "prop16deadbeef"
_RUN_ID: Final[str] = "prop16-local-run"
_WRITTEN_AT: Final[str] = "2026-02-20T00:00:00Z"

#: The two exact binary fractions used by the non-vacuity perturbation below. Chosen so
#: the expected relative change is exactly +100.0 with no floating-point residue.
_PERTURBED_BASELINE: Final[float] = 0.25
_PERTURBED_CONSENSUS: Final[float] = 0.5
_PERTURBED_HEADLINE_PP: Final[float] = 100.0


# ---------------------------------------------------------------------------
# The committed tolerance
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class _CommittedTolerance:
    """The recorded noise-tolerance ceiling, plus what it claims to guard."""

    bound: float
    direction: str
    status: str
    shipped_file: str
    shipped_extractor: str
    shipped_value: float

    def shipped_read(self) -> float | None:
        """Re-read the live constant through the recorded extractor, or ``None``.

        A pure text read (``encoding='utf-8'``, E-S13-07) of the file the row names -- no
        import of :mod:`uplift.cli`, which would pull the whole consensus assembly in.
        """
        kind, separator, pattern = self.shipped_extractor.partition(":")
        if kind != "regex" or not separator:
            return None
        source = ROOT / self.shipped_file
        if not source.is_file():
            return None
        match = re.search(pattern, source.read_text(encoding="utf-8"), re.MULTILINE)
        if match is None:
            return None
        return float(match.group("value"))


def _load_tolerance() -> _CommittedTolerance:
    """Read the ``uplift-noise-tolerance`` row. A missing row is a hard failure.

    Not a skip: a property whose tolerance cannot be found has not been evaluated, and an
    unevaluated property is never a pass (I-7).
    """
    record = json.loads(RATCHETS_FILE.read_text(encoding="utf-8"))["ratchets"][RATCHET_ID]
    return _CommittedTolerance(
        bound=float(record["bound"]),
        direction=str(record["direction"]),
        status=str(record["status"]),
        shipped_file=str(record["shipped"]["file"]),
        shipped_extractor=str(record["shipped"]["extractor"]),
        shipped_value=float(record["shipped"]["value"]),
    )


TOLERANCE: Final[_CommittedTolerance] = _load_tolerance()


# ---------------------------------------------------------------------------
# Generated configuration
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class _ArmSpec:
    """A pre-registered baseline policy, described so it can be built twice."""

    kind: str
    par_s: int
    par_S: int  # noqa: N815 - mirrors the (s, S) policy's own parameter name
    markup: float
    seed: int

    def build(self, name: str) -> DecisionPolicy:
        """Build one instance of this policy under ``name``.

        Called twice per example with two different names, so the consensus-named arm is
        a *copy* of the baseline arm -- constructed by the same code from the same
        parameters -- exactly as R2.6's scratch-branch substitution describes. For the
        frozen-dataclass baseline the copy is literally
        :func:`dataclasses.replace`-shaped; for the plain-class baseline it is a second
        construction from the identical arguments.
        """
        if self.kind == "par_level":
            policy = Par_Level_Reorder(s=self.par_s, S=self.par_S, seed=self.seed)
            policy.name = name
            return policy
        # ``Static_Pricing`` is a frozen dataclass, so its ``name`` is a read-only
        # attribute while ``DecisionPolicy`` declares ``name`` as a settable variable.
        # mypy therefore refuses the assignment. The cast records that the mismatch is
        # pre-existing and not introduced here: ``uplift/cli.py:167``'s ``build_arms``
        # carries the identical error under ``mypy --strict`` today. Reported, not
        # repaired -- neither the protocol nor the baseline is this task's to edit.
        return cast("DecisionPolicy", Static_Pricing(markup=self.markup, seed=self.seed, name=name))


@dataclasses.dataclass(frozen=True)
class _NullConfig:
    """One generated identical-arms experiment."""

    scenario: Scenario
    arm: _ArmSpec
    replicates: int
    loop: LoopConfig
    emission_factor: float


_multiplier = st.floats(
    min_value=0.8, max_value=1.5, allow_nan=False, allow_infinity=False
)


@st.composite
def _arm_specs(draw: st.DrawFn) -> _ArmSpec:
    low = draw(st.integers(min_value=0, max_value=40))
    return _ArmSpec(
        kind=draw(st.sampled_from(("par_level", "static_pricing"))),
        par_s=low,
        par_S=low + draw(st.integers(min_value=1, max_value=80)),
        markup=draw(
            st.floats(min_value=1.0, max_value=3.0, allow_nan=False, allow_infinity=False)
        ),
        seed=draw(st.integers(min_value=0, max_value=64)),
    )


@st.composite
def _null_configs(draw: st.DrawFn) -> _NullConfig:
    return _NullConfig(
        scenario=Scenario(
            name=draw(st.sampled_from(("prop16-a", "prop16-b"))),
            seed=draw(st.integers(min_value=0, max_value=2**31 - 1)),
            shock=ShockParams(
                demand_multiplier=draw(_multiplier),
                lead_time_multiplier=draw(_multiplier),
                failure_rate_multiplier=draw(_multiplier),
                spoilage_rate_multiplier=draw(_multiplier),
            ),
            cold_start=draw(st.booleans()),
        ),
        arm=draw(_arm_specs()),
        replicates=draw(st.integers(min_value=1, max_value=3)),
        loop=LoopConfig(
            duration_hours=draw(st.sampled_from((1.0, 2.0))), step_hours=1.0
        ),
        emission_factor=draw(
            st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False)
        ),
    )


# ---------------------------------------------------------------------------
# Running the reduced-cost matrix in-process
# ---------------------------------------------------------------------------
_BASELINE_ARM: Final[str] = "baseline-prop16"


def _run_matrix(
    config: _NullConfig, policies: tuple[DecisionPolicy, ...]
) -> HarnessResult:
    """Run one scenario x ``policies`` x ``replicates`` closed-loop matrix.

    Calls :func:`uplift.harness.run_closed_loop` directly with the same per-scenario
    replicate seed sequence for every arm (the attribution guarantee), which is the
    reduced-cost path ``uplift.cli`` uses in smoke mode. It deliberately bypasses the
    INV-TW-002 ``n >= MIN_SCENARIOS`` guard -- that guard is another property's subject,
    and a powered run here is forbidden (I-0).
    """
    seeds = [replicate_seed(config.scenario.seed, index) for index in range(config.replicates)]
    arm_results: dict[tuple[str, str], ArmResult] = {}
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    all_runs: list[ScenarioRun] = []
    for policy in policies:
        runs = [
            run_closed_loop(
                config.scenario,
                policy,
                seed,
                policy.name,
                config.loop,
                config.emission_factor,
            )
            for seed in seeds
        ]
        pair = (config.scenario.name, policy.name)
        runs_by_pair[pair] = runs
        arm_results[pair] = aggregate_arm(policy.name, runs)
        all_runs.extend(runs)
    return HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=(config.scenario,),
        arm_names=tuple(policy.name for policy in policies),
    )


def _with_headline_kpi(runs: list[ScenarioRun], value: float) -> list[ScenarioRun]:
    """A copy of ``runs`` whose completed runs all carry ``value`` for the headline KPI.

    A pure data transform over already-recorded runs: it costs no twin work and is the
    non-vacuity lever below. A failed run carries no KPI vector and is passed through
    unchanged.
    """
    perturbed: list[ScenarioRun] = []
    for run in runs:
        if run.failed or run.kpis is None:
            perturbed.append(run)
            continue
        perturbed.append(
            dataclasses.replace(
                run, kpis=dataclasses.replace(run.kpis, **{_HEADLINE_KPI: value})
            )
        )
    return perturbed


def _assemble(harness_result: HarnessResult) -> UpliftResult:
    """Assemble under the pre-registered contract with fidelity held fixed."""
    return assemble_uplift_result(
        harness_result,
        _CONTRACT,
        fidelity=_FIDELITY,
        consensus_arm=DEFAULT_CONSENSUS_ARM,
    )


def _stipulated_proof(headline: float) -> PoweredProof:
    """The measured ``headline`` in an otherwise ideal proof.

    Power, completeness and fidelity are stipulated so the only thing
    :func:`is_proven_uplift` can object to is the measurement itself. Stated as such in
    the module docstring: this is not a powered run and is not presented as one.
    """
    return PoweredProof(
        headline_uplift=headline,
        replicates=MIN_POWERED_REPLICATES,
        incomplete=False,
        within_fidelity_bound=True,
    )


# ---------------------------------------------------------------------------
# The committed tolerance is real configuration, and it agrees with the code
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 16: Identical arms measure no uplift
def test_the_noise_tolerance_is_read_from_committed_configuration() -> None:
    """The tolerance this property applies is committed, tightening-only, and agreed.

    An example, not a property: three reads of two committed files. It is here because a
    tolerance nobody can trace is worse than a literal -- it looks like configuration and
    behaves like a guess.
    """
    assert TOLERANCE.direction == "down", (
        "the noise tolerance is a ceiling: only a tightening commit is admissible, so "
        "the ratchet direction must be 'down'"
    )
    assert math.isfinite(TOLERANCE.bound)
    assert TOLERANCE.bound > 0.0, (
        "a zero tolerance would make the band assertion identical to the exact-zero one "
        "and would silently drop R2.6's stated form"
    )
    # The row must still describe the constant it guards (R7.8): the recorded value, and
    # the value the live constant actually holds, are both compared to the bound.
    assert TOLERANCE.shipped_value == TOLERANCE.bound
    shipped = TOLERANCE.shipped_read()
    assert shipped is not None, (
        f"the recorded extractor {TOLERANCE.shipped_extractor!r} no longer resolves "
        f"against {TOLERANCE.shipped_file}"
    )
    assert shipped == TOLERANCE.bound, (
        f"{TOLERANCE.shipped_file} ships {shipped} but {RATCHET_ID} records "
        f"{TOLERANCE.bound}"
    )
    # I-7: 1.0 pp is a declared reproduction tolerance, not a measured noise
    # distribution. Measuring one is a MIN_POWERED_REPLICATES run, i.e. uplift.yml's job.
    assert TOLERANCE.status in ("measured", "unmeasured")


# ---------------------------------------------------------------------------
# Property 16
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 16: Identical arms measure no uplift
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(config=_null_configs())
def test_identical_arms_measure_no_uplift(config: _NullConfig) -> None:
    """R2.6: the Consensus_Arm replaced by a copy of the Baseline_Arm reads zero."""
    baseline = config.arm.build(_BASELINE_ARM)
    consensus = config.arm.build(DEFAULT_CONSENSUS_ARM)

    # A copy, not the same object: R2.6's substitution is two arms, not one arm run twice.
    assert consensus is not baseline
    assert consensus.name == DEFAULT_CONSENSUS_ARM
    assert baseline.name == _BASELINE_ARM

    harness_result = _run_matrix(config, (consensus, baseline))
    consensus_pair = (config.scenario.name, DEFAULT_CONSENSUS_ARM)
    baseline_pair = (config.scenario.name, _BASELINE_ARM)
    consensus_runs = harness_result.runs_by_pair[consensus_pair]
    baseline_runs = harness_result.runs_by_pair[baseline_pair]

    # -- the two arms ran the same replicates and produced the same runs --------------
    assert len(consensus_runs) == len(baseline_runs) == config.replicates
    for left, right in zip(consensus_runs, baseline_runs, strict=True):
        assert left.seed == right.seed
        assert left.failed is right.failed
        assert left.error == right.error
        assert left.kpis == right.kpis

    consensus_aggregate = harness_result.arm_results[consensus_pair]
    baseline_aggregate = harness_result.arm_results[baseline_pair]
    assert consensus_aggregate.completed == baseline_aggregate.completed
    assert consensus_aggregate.failed == baseline_aggregate.failed
    assert consensus_aggregate.kpi_mean == baseline_aggregate.kpi_mean
    assert consensus_aggregate.kpi_std == baseline_aggregate.kpi_std

    # -- non-vacuity: a control with nothing recorded measures nothing (I-7) ----------
    assert consensus_aggregate.completed > 0, (
        "no replicate completed, so the zero below would be the absence of a "
        "measurement rather than a measurement of zero"
    )

    # -- every KPI, not only the headline one, shows no effect ------------------------
    for kpi in KPI_FIELDS:
        consensus_samples = harness_result.kpi_samples(
            config.scenario.name, DEFAULT_CONSENSUS_ARM, kpi
        )
        baseline_samples = harness_result.kpi_samples(
            config.scenario.name, _BASELINE_ARM, kpi
        )
        assert consensus_samples == baseline_samples
        assert consensus_samples, f"no completed sample recorded for {kpi}"
        assert relative_pct_change(consensus_samples, baseline_samples) == 0.0
        assert cohens_d(consensus_samples, baseline_samples) == 0.0

    # -- the headline number: exactly zero, and inside the committed tolerance --------
    result = _assemble(harness_result)
    assert math.isfinite(result.headline_uplift)
    assert abs(result.headline_uplift) <= TOLERANCE.bound, (
        f"identical arms measured {result.headline_uplift} pp, outside the committed "
        f"noise tolerance of {TOLERANCE.bound} pp ({RATCHET_ID})"
    )
    # Stronger than the tolerance band, and true by construction: identical arms on
    # shared replicate seeds produce equal samples, so the point estimate is exact.
    assert result.headline_uplift == 0.0

    # -- no pair is credited to SYNAPSE ----------------------------------------------
    assert result.per_scenario, "no (scenario, KPI) pair was classified"
    for pair, outcome in result.per_scenario.items():
        assert outcome is Outcome.TIE_INCONCLUSIVE, (pair, outcome)
    for kpi, outcome in result.per_kpi.items():
        assert outcome is Outcome.TIE_INCONCLUSIVE, (kpi, outcome)
    assert result.all_wins_warning is False

    # -- R2.6's second clause: this is not a proven gain ------------------------------
    # Power, completeness and fidelity are stipulated ideal, so the refusal below can
    # only come from the measurement.
    null_proof = _stipulated_proof(result.headline_uplift)
    assert is_proven_uplift(null_proof, UPLIFT_FLOOR) is False
    # The discriminating converse: the same stipulation with a positive headline IS
    # proven, so the refusal is attributable to the null reading.
    proven = _stipulated_proof(UPLIFT_FLOOR + TOLERANCE.bound + 1.0)
    assert is_proven_uplift(proven, UPLIFT_FLOOR) is True
    # R2.10: a null measurement can back no floor raise either.
    with pytest.raises(UnprovenFloorRaiseError):
        ratchet_to_measured(UPLIFT_FLOOR, UPLIFT_FLOOR + 1.0, null_proof)

    # -- and the artifact this run actually produced is honestly inadmissible ---------
    # The stipulation above is a statement about the measurement; this is the statement
    # about the run. Its replicate count is below MIN_POWERED_REPLICATES by design, and
    # the artifact says so rather than presenting a small run as a proof.
    report = build_uplift_report(result)
    artifact = build_uplift_artifact(
        result,
        report,
        resolve_provenance(
            arms=[consensus.name, baseline.name],
            replicates_per_arm=config.replicates,
            seeds=[config.scenario.seed],
            revision=_REVISION,
            run_id=_RUN_ID,
            written_at=_WRITTEN_AT,
        ),
        noise_tolerance_pp=TOLERANCE.bound,
        harness_result=harness_result,
    )
    assert artifact.headline_uplift == 0.0
    assert artifact.noise_tolerance_pp == TOLERANCE.bound
    assert artifact.is_proof_grade is False
    assert any("powered" in reason for reason in artifact.unavailable_reasons), (
        artifact.unavailable_reasons
    )
    assert is_proven_uplift(artifact.as_powered_proof(), UPLIFT_FLOOR) is False

    # -- non-vacuity for the zero itself ---------------------------------------------
    # The same assembly path, fed arms that differ, reports a non-zero headline. Without
    # this the zero above could hold because the headline is constant -- which is the
    # class of vacuous measurement this whole feature exists to remove. The perturbation
    # is a pure transform over the runs already recorded, so it costs no twin work.
    perturbed = HarnessResult(
        arm_results={
            consensus_pair: aggregate_arm(
                DEFAULT_CONSENSUS_ARM,
                _with_headline_kpi(consensus_runs, _PERTURBED_CONSENSUS),
            ),
            baseline_pair: aggregate_arm(
                _BASELINE_ARM, _with_headline_kpi(baseline_runs, _PERTURBED_BASELINE)
            ),
        },
        runs_by_pair={
            consensus_pair: _with_headline_kpi(consensus_runs, _PERTURBED_CONSENSUS),
            baseline_pair: _with_headline_kpi(baseline_runs, _PERTURBED_BASELINE),
        },
        all_runs=list(consensus_runs) + list(baseline_runs),
        results_path=None,
        scenarios=(config.scenario,),
        arm_names=(DEFAULT_CONSENSUS_ARM, _BASELINE_ARM),
    )
    expected = (
        _PERTURBED_HEADLINE_PP
        if _HEADLINE_DIRECTION is Direction.HIGHER_IS_BETTER
        else -_PERTURBED_HEADLINE_PP
    )
    assert _assemble(perturbed).headline_uplift == expected, (
        "the headline did not move when the arms were made to differ, so the zero "
        "measured above is not evidence that the arms were identical"
    )
