"""
SYNAPSE Decision-Integrity Uplift Proof -- the one-command reproduction CLI (R7).

``python -m uplift.cli`` is the single, ``$0``, synthetic-seed-only command that runs
the closed-loop counterfactual :class:`~uplift.harness.UpliftHarness` on the declared
adversarial seeds (:data:`~uplift.scenarios.ADVERSARIAL_SUITE`), assembles the
:class:`~uplift.interfaces.UpliftResult` under the pre-registered
:class:`~uplift.contract.MetricContract`, and prints the **headline uplift number
co-located with its interval, its verdict, its comparator and its
twin-:class:`~uplift.fidelity.FidelityReport`** (R7.2, R7.7, R7.14, R5.2/R5.6). Under
Metric_Contract v2 (decision-quality-proof task 29.4) the headline is the mean seed-paired
difference of the committed ADR-055 D2 objective, comparator minus consensus, in objective
units -- positive means the consensus arm is cheaper. It is never a fill-rate percentage.

It also persists the result to the ``artifacts/uplift/result.json`` artifact
the C60 ``uplift_truth`` gate reads. That artifact is not under version control: the gate
is trigger-aware (AD-9, CF-4), so it returns PASS/FAIL only when it is invoked with
``--require-fresh-run`` in the same job that ran this command, and SKIP everywhere else.

Honesty invariants surfaced by this command:

* **Synthetic seed data only (R7.5).** Every scenario is driven by the harness's seeded
  synthetic demand realization (``numpy.random.SeedSequence``-derived replicate seeds);
  no real, scraped, or purchased data is read.
* **No external paid service (R7.6).** The whole pipeline is in-process -- the twin, the
  baselines, and (when available) the in-process consensus arm. Nothing dials a paid
  API. The consensus arm requires an injected in-process protocol + transport and, when
  that cannot be stood up in a plain environment, its runs fail honestly (recorded as
  failed runs, excluded from aggregation) rather than crashing or fabricating a decision.
* **The comparator is explicit (AD-16, R6.14, task 15.5).** Every arm is registered with the
  role it plays. The canonical five arms :func:`build_arms` returns default to the pool of
  their four baseline-role arms, and the artifact records that pool by name. Any other arm
  set must pass ``--baseline-arm NAME`` (that arm alone) or ``--pooled-baseline`` (every
  baseline-role arm); an unrecognised arm with neither is refused, never pooled by default.
* **Version-controlled noise tolerance.** :data:`NOISE_TOLERANCE_PP` is the committed
  run-to-run reproduction tolerance, stated in the output. Its value and name are kept
  unchanged, and its unit is now in question: it was committed in percentage points of the
  version-1 fill-rate headline, and the headline is now in objective units.
* **Missing required input => honest failure (R7.8).** A missing/malformed metric
  contract (:class:`~uplift.contract.MetricContractError`), or a comparator that cannot be
  resolved, exits with a non-zero status naming the input and prints **no** headline
  number.
* **Two suites (session 12).** ``--suite canonical`` (the default) is everything above,
  unchanged. ``--suite e5-primary`` is :mod:`uplift.e5_suite`: the consensus arm against arm E
  of checkpoint B-prime in the primary world cell, unshocked, reorders only, at B-prime's 24 h
  cadence. It reads the committed B-prime record (:mod:`uplift.bprime_record`), whose absence or
  defect is a missing required input like a missing contract; it requires
  ``--baseline-arm tuned_static`` and refuses ``--pooled-baseline``, ``--smoke``, fewer than
  ``MIN_SCENARIOS`` replicates, and a cadence other than B-prime's -- each before any replicate
  runs. After those refusals and before anything is measured, it runs R7.21's pathway probe
  over a FRESH consensus arm and writes ``pathway-probe.json``, or ``pathway-probe-refused.json``
  naming why no rate exists; the probe never refuses the run. Before its harness runs it
  re-measures B-prime's arms E and E' at B-prime's own seeds and writes ``reproduction.json``.
  Beside the headline it prints whether that reproduced exactly, the dispatch line R7.20 asks
  for, worded as "recommendations, if executed" (Q2=a), and the probe's line per input; and it
  writes ``dispatch.json`` beside the artifact.

Cost / runtime (INV-TW-002 tradeoff). A real, fully-powered proof requires ``n >= 1000``
completed scenarios per arm (:data:`digital_twin.simulation.monte_carlo.MIN_SCENARIOS`)
and drives the real twin, which is slow. The default full run enforces that floor via
:meth:`UpliftHarness.run`. For fast reproduction (``make prove-uplift`` and the
reproduction tests 14.3/14.4) a reduced-cost **smoke** mode (``--smoke`` / ``--n`` below
the floor) runs a handful of replicates over a short horizon by calling
:func:`~uplift.harness.run_closed_loop` directly, deliberately bypassing the
INV-TW-002 under-power guard. Smoke mode is clearly labelled in the output as NOT a
fully-powered proof; only ``--full`` (or ``--n >= 1000``) produces a proof-grade result.

Run::

    python -m uplift.cli --smoke                 # fast reduced-cost reproduction
    python -m uplift.cli --full                  # fully-powered proof (n >= 1000, slow)
    python -m uplift.cli --n 2000                # explicit replicate count
    python -m uplift.cli --contract path.yaml    # alternate pre-registered contract
    python -m uplift.cli --smoke --baseline-arm Par_Level_Reorder   # one named comparator
    python -m uplift.cli --full --suite e5-primary --baseline-arm tuned_static \\
        --duration-hours 24                      # E5, exactly as uplift.yml runs it (CI only)
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from digital_twin.simulation.monte_carlo import MIN_SCENARIOS
from digital_twin.simulation.policy import PolicyUnavailableError
from uplift.baselines import (
    Greedy_Routing,
    NoOpDisruption,
    Par_Level_Reorder,
    Static_Pricing,
)
from uplift.bprime_record import (
    BPRIME_ARTIFACT_PATH,
    BPRIME_PROVENANCE_PATH,
    BprimeRecordError,
    read_bprime_record,
)
from uplift.consensus_arm import build_consensus_arm
from uplift.contract import MetricContractError, load_contract
from uplift.dispatch import (
    PathwayConsultant,
    PathwayProbeError,
    PathwayProbeRefusal,
    PathwayProbeReport,
    run_pathway_probe,
    summarise_dispatch,
    write_dispatch_report,
    write_probe_refusal,
    write_probe_report,
)
from uplift.e5_suite import (
    E5_COMPARATOR,
    E5_LOOP,
    E5_REPRODUCED_ARMS,
    E5_SUITE,
    build_e5_arms,
    e5_consensus_policy,
    e5_probe_observations,
    e5_replicate_seeds,
    e5_scenario,
    measure_bprime_reproduction,
    production_arm_cost,
    write_bprime_reproduction,
)
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    EXIT_SUCCESS,
    HarnessResult,
    LoopConfig,
    UpliftHarness,
    UpliftProvenance,
    UpliftReport,
    aggregate_arm,
    assemble_uplift_result,
    build_uplift_artifact,
    build_uplift_report,
    registered_roles,
    replicate_seed,
    resolve_provenance,
    run_closed_loop,
    uplift_exit_code,
)
from uplift.interfaces import (
    ArmResult,
    ArmSpec,
    DecisionPolicy,
    Scenario,
    ScenarioRun,
    UpliftResult,
)
from uplift.kpi import DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY
from uplift.policies import UnavailableConsensusArm
from uplift.scenarios import adversarial_suite
from uplift.tuning import TuningUnavailableError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from uplift.contract import MetricContract
    from uplift.dispatch import DispatchReport
    from uplift.e5_suite import BprimeReproduction

# ---------------------------------------------------------------------------
# Version-controlled constants
# ---------------------------------------------------------------------------
#: The committed run-to-run reproduction noise tolerance (R7.3): a headline-uplift difference
#: between two reproductions of the same seeded config must not exceed it. Version-controlled
#: here so the tolerance a reproduction is judged against cannot be quietly widened.
#:
#: **Committed in percentage points, when the headline was a fill-rate relative percentage.**
#: Under Metric_Contract v2 the headline is a paired difference of the committed objective, in
#: objective units, so every comparison of a headline difference against this number now
#: compares objective units with a bound stated in another unit. The value and the name are
#: deliberately unchanged here; re-deciding the bound is not this module's call.
NOISE_TOLERANCE_PP: float = 1.0

#: Default replicate count for reduced-cost smoke reproduction (well below the
#: INV-TW-002 ``MIN_SCENARIOS`` floor; NOT a fully-powered proof -- see module docstring).
SMOKE_REPLICATES: int = 5

#: Reduced closed-loop cadence used by smoke mode (short horizon for fast turnaround).
SMOKE_LOOP = LoopConfig(duration_hours=2.0, step_hours=1.0)

#: Non-zero exit status for a missing/malformed required input (R7.8). Distinct from the
#: harness's own no-completed-run failure so a missing input is diagnosable.
EXIT_MISSING_INPUT: int = 2

#: The five arm names :func:`build_arms` registers, in its order: the consensus subject, then
#: the four transparent baselines. A run over EXACTLY this tuple may leave its comparator
#: implicit, and then compares against the pool of the four baseline-role arms; any other arm
#: set must name its comparator (:func:`resolve_control_spec`). Literal names rather than a
#: call to :func:`build_arms`, because building the arms stands up the consensus network.
CANONICAL_ARM_NAMES: Final[tuple[str, ...]] = (
    DEFAULT_CONSENSUS_ARM,
    "Par_Level_Reorder",
    "static_pricing",
    "greedy_routing",
    "no_op_disruption",
)

#: ``--suite`` values. ``canonical`` is the adversarial five-arm suite this command has always
#: run; ``e5-primary`` is :mod:`uplift.e5_suite` (session 12).
CANONICAL_SUITE: Final[str] = "canonical"
SUITES: Final[tuple[str, ...]] = (CANONICAL_SUITE, E5_SUITE)

#: The dispatch record the E5 suite writes beside the result artifact (R7.20).
DISPATCH_FILENAME: Final[str] = "dispatch.json"

#: The record of B-prime's comparator re-measured in this environment, written beside the result
#: artifact BEFORE the E5 harness runs (API2 amendment 2).
REPRODUCTION_FILENAME: Final[str] = "reproduction.json"

#: R7.21's pathway probe report, written beside the dispatch record before anything is measured
#: (finding 109: until then only a slow test produced one, under ``tmp_path``).
PROBE_FILENAME: Final[str] = "pathway-probe.json"

#: Written IN PLACE of :data:`PROBE_FILENAME` when the probe states no rate: the arm has no
#: pathway to consult, an input has zero pairs, or the probe could not run. A run's directory
#: holds exactly one of the two.
PROBE_REFUSAL_FILENAME: Final[str] = "pathway-probe-refused.json"

#: The repository root the committed B-prime record is read under. A module global, read at
#: call time, so a test can point the E5 suite at a tree with no record (or a fixture record)
#: and prove every refusal before a replicate runs.
REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

# The public surface: the constants and the comparator vocabulary callers and tests name.
__all__ = [
    "CANONICAL_ARM_NAMES",
    "CANONICAL_SUITE",
    "DISPATCH_FILENAME",
    "EXIT_MISSING_INPUT",
    "NOISE_TOLERANCE_PP",
    "PROBE_FILENAME",
    "PROBE_REFUSAL_FILENAME",
    "REPO_ROOT",
    "REPRODUCTION_FILENAME",
    "SUITES",
    "ControlSpec",
    "build_arms",
    "main",
    "resolve_control_spec",
]


# ---------------------------------------------------------------------------
# Consensus arm (honest-failure path)
# ---------------------------------------------------------------------------
#: The stand-in consensus arm whose every decision fails honestly (R2.7, R7.6). It lives in
#: :mod:`uplift.policies` from session 12, so the E5 suite degrades exactly as this suite does
#: without importing the CLI; the private name is kept because tests and two specs cite it.
_UnavailableConsensusArm = UnavailableConsensusArm


def _build_consensus_arm() -> DecisionPolicy:
    """Assemble the real in-process consensus arm, degrading honestly when unavailable.

    Calls :func:`~uplift.consensus_arm.build_consensus_arm`, which stands up the eight
    real agent ``handle_request`` handlers plus the twin handler behind an in-process
    A2A transport and a real :class:`ConsensusProtocol`, so the harness measures
    SYNAPSE's actual four-tier consensus with no socket opened and no paid service
    (R1.1, R1.2, R7.6). Standing that network up is not possible in every environment;
    any assembly failure (:class:`ConsensusArmUnavailable` or otherwise) is caught and
    surfaced as :class:`_UnavailableConsensusArm` so the affected consensus runs are
    recorded as *failed* runs and the result is marked incomplete, rather than the CLI
    crashing or a decision being fabricated (R1.5, R7.5, R2.7).
    """
    try:
        return build_consensus_arm()
    except Exception as exc:  # noqa: BLE001 — any assembly failure ⇒ honest stub
        return _UnavailableConsensusArm(
            f"consensus arm unavailable in this environment: {type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# Arm construction and the comparator (AD-16, task 15.5)
# ---------------------------------------------------------------------------
def build_arms(seed: int = 0) -> tuple[ArmSpec, ...]:
    """Build the arm suite: the consensus arm plus the four transparent baselines, with roles.

    Registered in :data:`CANONICAL_ARM_NAMES` order. The consensus arm is named
    :data:`DEFAULT_CONSENSUS_ARM` (``"consensus"``) and declares role ``consensus``, so result
    assembly identifies it as the subject. The four baselines are the pre-registered control
    suite (R1.1) -- ``Par_Level_Reorder``, ``Static_Pricing``, ``Greedy_Routing`` and
    ``NoOpDisruption`` -- and each declares role ``baseline``, which is what lets the pooled
    comparator absorb them; an oracle or excluded arm added later is never pooled.
    """
    return (
        ArmSpec(_build_consensus_arm(), "consensus"),
        ArmSpec(Par_Level_Reorder(s=20, S=100, seed=seed), "baseline"),
        ArmSpec(Static_Pricing(markup=1.5, seed=seed), "baseline"),
        ArmSpec(Greedy_Routing(), "baseline"),
        ArmSpec(NoOpDisruption(), "baseline"),
    )


@dataclasses.dataclass(frozen=True)
class ControlSpec:
    """The comparator a run's headline is measured against (AD-16, R6.14).

    Exactly one of two forms, and construction refuses anything else:

    * ``ControlSpec(baseline_arm="NAME", pooled=False)`` -- that one registered arm alone, the
      form R6.14 requires of both controls;
    * ``ControlSpec(baseline_arm=None, pooled=True)`` -- the pool of every arm whose declared
      role is ``baseline``, recorded in the artifact as ``"pooled:"`` plus the sorted names.
    """

    baseline_arm: str | None
    pooled: bool

    def __post_init__(self) -> None:
        if self.pooled == (self.baseline_arm is not None):
            raise ValueError(
                "a ControlSpec names one comparator arm or asks for the pool, exactly one of "
                f"the two: got baseline_arm={self.baseline_arm!r}, pooled={self.pooled!r}"
            )
        if self.baseline_arm is not None and not self.baseline_arm.strip():
            raise ValueError("a named comparator must have a non-empty name")


def resolve_control_spec(
    *,
    baseline_arm: str | None,
    pooled_baseline: bool,
    arm_names: Sequence[str],
) -> ControlSpec:
    """Resolve the comparator a run measures against, or refuse before any replicate runs.

    * ``baseline_arm`` names one registered arm: that arm alone, never pooled.
    * ``pooled_baseline`` asks for the pool of every baseline-role arm.
    * Neither: allowed ONLY when ``arm_names`` is exactly :data:`CANONICAL_ARM_NAMES`, and then
      it is the pool -- recorded as a pool, never left implicit. Any other arm set has no
      default, because an arm the canonical suite does not contain (an oracle, a copy of a
      baseline) would otherwise be compared against whatever the pool happened to hold.

    Raises:
        ValueError: When both are given, when ``baseline_arm`` is not one of ``arm_names``, or
            when neither is given and ``arm_names`` is not exactly the canonical five.
    """
    if pooled_baseline and baseline_arm is not None:
        raise ValueError(
            "--pooled-baseline and --baseline-arm are mutually exclusive: a contrast is "
            "against one named arm or against the pool, never both"
        )
    if baseline_arm is not None:
        if baseline_arm not in arm_names:
            raise ValueError(
                f"--baseline-arm {baseline_arm!r} is not a registered arm "
                f"(registered: {list(arm_names)})"
            )
        return ControlSpec(baseline_arm=baseline_arm, pooled=False)
    if not pooled_baseline and tuple(arm_names) != CANONICAL_ARM_NAMES:
        raise ValueError(
            f"the arm set {list(arm_names)} is not exactly the canonical five "
            f"{list(CANONICAL_ARM_NAMES)}, so its comparator must be stated: pass "
            "--baseline-arm NAME or --pooled-baseline. An unrecognised arm is never pooled "
            "by default (AD-16)"
        )
    return ControlSpec(baseline_arm=None, pooled=True)


def _describe_control(control: ControlSpec) -> str:
    """ASCII one-liner naming the comparator a run is about to be measured against."""
    if control.baseline_arm is not None:
        return f"{control.baseline_arm} (named; never pooled)"
    return "pool of every baseline-role arm (recorded in the artifact as 'pooled:...')"


# ---------------------------------------------------------------------------
# Reduced-cost (smoke) harness execution -- bypasses the INV-TW-002 guard
# ---------------------------------------------------------------------------
def _run_reduced(
    scenarios: Sequence[Scenario],
    arms: Sequence[ArmSpec],
    n_replicates: int,
    loop_config: LoopConfig,
    emission_factor: float,
) -> HarnessResult:
    """Run a reduced-cost harness matrix by calling the closed loop directly (smoke).

    This deliberately **bypasses** :meth:`UpliftHarness.run_arm`'s INV-TW-002
    ``n >= MIN_SCENARIOS`` under-power guard so ``make prove-uplift`` and the
    reproduction tests run in seconds. It reuses the exact same per-scenario replicate
    seeding (:func:`replicate_seed`) so every arm still sees the identical seeded demand
    realization (the attribution guarantee, R2.1/R2.5), and it registers the arms through
    :func:`~uplift.harness.registered_roles` exactly as :meth:`UpliftHarness.run` does --
    before any replicate runs, so an arm with no role costs no twin work. A result produced
    this way is a fast smoke reproduction, NOT a fully-powered proof -- only
    ``n >= MIN_SCENARIOS`` (``--full``) satisfies INV-TW-002.
    """
    roles = registered_roles(arms)
    arm_results: dict[tuple[str, str], ArmResult] = {}
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    all_runs: list[ScenarioRun] = []

    for scenario in scenarios:
        seeds = [replicate_seed(scenario.seed, index) for index in range(n_replicates)]
        for spec in arms:
            runs = [
                run_closed_loop(
                    scenario, spec.policy, seed, spec.name, loop_config, emission_factor
                )
                for seed in seeds
            ]
            pair = (scenario.name, spec.name)
            runs_by_pair[pair] = runs
            arm_results[pair] = aggregate_arm(spec.name, runs)
            all_runs.extend(runs)

    return HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=tuple(spec.name for spec in arms),
        arm_roles=roles,
    )


# ---------------------------------------------------------------------------
# Artifact persistence (feeds the C60 uplift_truth gate)
# ---------------------------------------------------------------------------
def _default_artifact_path() -> Path:
    """The canonical result-artifact path the C60 gate reads.

    Imported from :mod:`scripts.audit.uplift_truth` so the CLI writes exactly where the
    gate reads; falls back to the same repo-relative path if that import is unavailable.
    """
    try:
        from scripts.audit.uplift_truth import RESULT_ARTIFACT

        return Path(RESULT_ARTIFACT)
    except Exception:  # noqa: BLE001 — replicate the path consistently on import failure
        root = Path(__file__).resolve().parents[1]
        return root / "artifacts" / "uplift" / "result.json"


def _write_result_artifact(
    path: Path,
    result: UpliftResult,
    report: UpliftReport,
    *,
    harness_result: HarnessResult | None = None,
    provenance: UpliftProvenance | None = None,
) -> Path:
    """Write the canonical :class:`~uplift.harness.UpliftArtifact` to ``path``.

    The gate (:func:`scripts.audit.uplift_truth.admit`) parses this file through
    :meth:`~uplift.harness.UpliftArtifact.read`, so every field it needs must be present:
    a finite ``headline_uplift`` with its interval and verdict, a boolean ``incomplete``, the
    fidelity block that co-locates the KL context (R5.6), and the provenance record naming the
    revision, run, seed set, arms, arm roles, and replicates-per-arm count the audit's R2.3
    requires -- an artifact missing any of them is inadmissible, not silently readable.
    Serialisation is canonical (``sort_keys=True``, tight separators) so two runs of the same
    seed set at the same revision produce byte-identical files.

    ``provenance`` is resolved from the environment when not supplied; a caller with no
    provenance gets a record with no arms, no roles and a zero replicate count, which is
    honest (and inadmissible as proof) rather than fabricated.
    """
    resolved = (
        provenance
        if provenance is not None
        else resolve_provenance(arms=(), arm_roles={}, replicates_per_arm=0, seeds=())
    )
    artifact = build_uplift_artifact(
        result,
        report,
        resolved,
        noise_tolerance_pp=NOISE_TOLERANCE_PP,
        harness_result=harness_result,
    )
    return artifact.write(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m uplift.cli",
        description=(
            "Run the closed-loop counterfactual uplift harness on the declared "
            "adversarial seeds and print the headline uplift number co-located with "
            "its interval, verdict, comparator and twin-fidelity report. Synthetic seed "
            "data only; no external paid service."
        ),
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help=(
            "Reduced-cost reproduction: a few replicates over a short horizon "
            "(bypasses the INV-TW-002 n>=1000 guard). Fast, but NOT a fully-powered "
            "proof."
        ),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            f"Fully-powered proof: n>={MIN_SCENARIOS} completed scenarios per arm "
            "(INV-TW-002). Drives the real twin and is slow."
        ),
    )
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Replicates per arm. Values below "
            f"{MIN_SCENARIOS} run in reduced-cost mode; "
            f">= {MIN_SCENARIOS} runs a fully-powered proof."
        ),
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to the pre-registered metric contract YAML (required input).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="Where to write the result artifact (default: artifacts/uplift/result.json).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        metavar="N",
        help="Base construction seed for the seeded baseline policies (default: 0).",
    )
    parser.add_argument(
        "--duration-hours",
        type=float,
        default=None,
        help="Closed-loop horizon in hours (default: full=4.0, smoke=2.0).",
    )
    parser.add_argument(
        "--step-hours",
        type=float,
        default=1.0,
        help="Per-step advance duration in hours (default: 1.0).",
    )
    comparator = parser.add_mutually_exclusive_group()
    comparator.add_argument(
        "--pooled-baseline",
        action="store_true",
        help=(
            "Compare the consensus arm against the pool of every baseline-role arm. The "
            "default for the canonical five arms; required to pool any other arm set."
        ),
    )
    comparator.add_argument(
        "--baseline-arm",
        default=None,
        metavar="NAME",
        help=(
            "Compare the consensus arm against this one registered arm alone, never pooled "
            "(R6.14). Mutually exclusive with --pooled-baseline."
        ),
    )
    parser.add_argument(
        "--suite",
        choices=SUITES,
        default=CANONICAL_SUITE,
        help=(
            f"Which experiment to run (default: {CANONICAL_SUITE}, the adversarial five-arm "
            f"suite). {E5_SUITE}: the consensus arm against B-prime's arm E in the primary "
            f"cell, unshocked; requires the committed B-prime record, --baseline-arm "
            f"{E5_COMPARATOR} and a powered replicate count, and runs B-prime's 24 h cadence."
        ),
    )
    return parser


def _resolve_run_config(args: argparse.Namespace) -> tuple[int, LoopConfig, bool]:
    """Resolve (replicates, loop config, reduced?) from the parsed flags.

    Reduced-cost mode is used for ``--smoke`` or any explicit ``--n`` below the
    INV-TW-002 floor; otherwise a fully-powered run at ``max(n, MIN_SCENARIOS)`` is used.
    """
    if args.n is not None:
        n = args.n
    elif args.full:
        n = MIN_SCENARIOS
    elif args.smoke:
        n = SMOKE_REPLICATES
    else:
        # Default with no mode flag: reduced-cost so the one-command reproduction is
        # runnable out of the box; use --full (or --n >= MIN_SCENARIOS) for a proof.
        n = SMOKE_REPLICATES

    reduced = args.smoke or n < MIN_SCENARIOS

    if args.duration_hours is not None:
        loop = LoopConfig(duration_hours=args.duration_hours, step_hours=args.step_hours)
    elif reduced:
        loop = LoopConfig(duration_hours=SMOKE_LOOP.duration_hours, step_hours=args.step_hours)
    else:
        loop = LoopConfig(step_hours=args.step_hours)

    return n, loop, reduced


def _print_disclosures(result: UpliftResult, *, reduced: bool) -> None:
    """The honesty disclosures every suite prints after its headline (R7.5, R7.6).

    One copy for both suites, so the canonical output is byte-for-byte what it was and the E5
    output cannot omit a line the canonical one carries.
    """
    print()
    print(
        f"applied noise tolerance: <= {NOISE_TOLERANCE_PP:.1f} percentage point "
        "(version-controlled reproduction tolerance, committed for the version-1 fill-rate "
        "headline; the headline above is in objective units)"
    )
    print("data provenance: synthetic seed-generated data only (no real/scraped/paid data)")
    print("external services: none -- fully in-process (no external paid service)")
    if reduced:
        print(
            "note: reduced-cost smoke run -- a fully-powered proof requires "
            f"n >= {MIN_SCENARIOS} per arm (--full)."
        )
    if result.incomplete:
        print(
            "note: result marked INCOMPLETE -- the consensus arm or a comparator arm could "
            "not complete every scenario; no incomplete pair is credited to SYNAPSE."
        )
    elif result.run_incomplete:
        print(
            "note: an arm outside this contrast failed a replicate (run_incomplete); the "
            "contrast itself completed, so its verdict is unaffected."
        )
    if result.all_wins_warning:
        print(
            "self-scrutiny warning: every classified pair is SYNAPSE_WINS -- scrutinize "
            "for measurement bias before trusting this result."
        )


# ---------------------------------------------------------------------------
# The E5 suite (session 12; task 22.1's code half)
# ---------------------------------------------------------------------------
def _e5_refusals(args: argparse.Namespace, *, n: int, reduced: bool) -> list[str]:
    """Every flag the E5 suite refuses, each named with why; empty when all are admissible.

    E5 exists to be powered, so it never runs reduced; it is one named contrast against arm E
    (R6.14), so it neither pools nor names another comparator; and arm E was tuned at B-prime's
    cadence and horizon, so neither may move. ``--duration-hours`` may be omitted -- E5 runs
    :data:`~uplift.e5_suite.E5_LOOP` -- but a different value is refused rather than ignored.
    """
    reasons: list[str] = []
    if args.smoke:
        reasons.append("--smoke: the E5 suite exists to be powered and never runs reduced")
    elif reduced:
        reasons.append(
            f"{n} replicates per arm is below the INV-TW-002 floor {MIN_SCENARIOS}: pass --full "
            f"or --n >= {MIN_SCENARIOS}; the E5 suite never runs reduced"
        )
    if args.pooled_baseline:
        reasons.append(
            "--pooled-baseline: E5 is one named contrast against arm E, never a pool (R6.14)"
        )
    elif args.baseline_arm != E5_COMPARATOR:
        reasons.append(
            f"--baseline-arm {args.baseline_arm!r}: E5 requires --baseline-arm {E5_COMPARATOR}"
        )
    if args.step_hours != E5_LOOP.step_hours:
        reasons.append(
            f"--step-hours {args.step_hours!r}: E5 runs at the cadence B-prime tuned arm E at, "
            f"{E5_LOOP.step_hours!r} h"
        )
    if args.duration_hours is not None and args.duration_hours != E5_LOOP.duration_hours:
        reasons.append(
            f"--duration-hours {args.duration_hours!r}: E5 runs the horizon B-prime tuned arm E "
            f"over, {E5_LOOP.duration_hours!r} h"
        )
    return reasons


def _dispatch_lines(report: DispatchReport) -> list[str]:
    """The claim's scope and R7.20's dispatch line, read off the record ``dispatch.json`` holds.

    One source: what is printed is what is recorded. The rate is ``dispatched / total``, or --
    when no decision was counted -- unavailable with the record's own stated reason, never 0.
    Under Q2=a a recommendation withheld for confidence ALONE is applied
    (``uplift.consensus_arm._APPLIED_BUCKETS``), so the line names it applied; a blocked or an
    untranslatable one reaches no lever.
    """
    counts = report.counts
    if report.dispatch_rate is None:
        rate = f"rate unavailable: {report.rate_unavailable_reason}"
    else:
        rate = f"rate {report.dispatch_rate:.4f}"
    scope = (
        f"claim scope: {report.wording} (Q2=a) -- a binding recommendation of the "
        "consensus arm reached the twin if it was dispatched or withheld for confidence alone; "
        "a blocked or untranslatable one applied nothing"
    )
    dispatch = (
        f"dispatch: {counts.dispatched}/{counts.total} binding decisions dispatched ({rate}); "
        f"withheld for confidence {counts.withheld_for_confidence} (applied, Q2=a); "
        f"guardrail-blocked {counts.guardrail_blocked}, untranslatable {counts.untranslatable} "
        "(neither applied)"
    )
    return [scope, dispatch]


def _reproduction_lines(reproduction: BprimeReproduction) -> list[str]:
    """One line per re-measured arm: its mean here beside the mean B-prime recorded."""
    seeds = reproduction.seeds.describe()
    lines = [f"B-prime's comparator re-measured in this environment ({seeds}, exact):"]
    for arm in reproduction.arms:
        verdict = "reproduces" if arm.reproduces else "NOT reproduced"
        lines.append(
            f"  {arm.arm}: measured {arm.measured_mean!r}, B-prime recorded "
            f"{arm.recorded_mean!r} -- {verdict}"
        )
    return lines


def _comparator_line(reproduction: BprimeReproduction) -> str:
    """Beside the headline: whether this environment reproduced B-prime's comparator exactly.

    API2 amendment 2's wording. A non-reproduction is reported, never refused: E5 runs in the
    full closure (numpy 1.26.4) and B-prime ran in the thin one (numpy 2.4.6), and what a claim
    may then say is the main agent's decision, not this command's.
    """
    if reproduction.all_reproduce:
        arms = ", ".join(arm.arm for arm in reproduction.arms)
        return f"comparator at B-prime's levels, reproduced exactly in this environment ({arms})"
    missed = "; ".join(
        f"{arm.arm} measured {arm.measured_mean!r}, recorded {arm.recorded_mean!r}"
        for arm in reproduction.arms
        if not arm.reproduces
    )
    return f"comparator at B-prime's levels, not reproduced in this environment: {missed}"


def _unconsultable_reason(arm: DecisionPolicy) -> str:
    """Why an arm that is not a :class:`~uplift.dispatch.PathwayConsultant` cannot be probed."""
    return (
        f"the consensus arm built for the probe is {type(arm).__name__}, not a pathway the probe "
        "can consult (a PathwayConsultant has levers and consult; UnavailableConsensusArm, the "
        "stand-in E5 builds when the in-process consensus network cannot be assembled, has "
        "neither), so there is no binding decision to withhold an input from"
    )


def _e5_pathway_probe(directory: Path) -> tuple[PathwayProbeReport | PathwayProbeRefusal, Path]:
    """R7.21's probe of a FRESH consensus arm, written to ``directory``: its report, or why none.

    The arm is built anew by :func:`~uplift.e5_suite.e5_consensus_policy`, never the harness's
    instance, so the probe moves neither the measured arm's tally nor its audit trail. Three
    outcomes state no rate, and each writes a :class:`~uplift.dispatch.PathwayProbeRefusal` to
    :data:`PROBE_REFUSAL_FILENAME` naming its reason: an arm that is not a
    :class:`~uplift.dispatch.PathwayConsultant` (the
    :class:`~uplift.policies.UnavailableConsensusArm` stand-in), a probe that refuses a rate
    (:class:`~uplift.dispatch.PathwayProbeError`: zero pairs), and a probe that could not run.
    Otherwise the report is written to :data:`PROBE_FILENAME`. The other file, if an earlier run
    left one here, is removed, so the directory never holds both. NEVER a refusal of the E5
    run: the probe's absence is a finding reported beside the headline (R7.21).

    ``e5_consensus_policy``, ``e5_probe_observations`` and ``run_pathway_probe`` are read from
    this module's globals at call time: the seam a fast test injects, so that no twin and no
    protocol runs there.
    """
    arm = e5_consensus_policy()
    outcome: PathwayProbeReport | PathwayProbeRefusal
    if not isinstance(arm, PathwayConsultant):
        outcome = PathwayProbeRefusal.of(arm=arm.name, reason=_unconsultable_reason(arm))
    else:
        try:
            outcome = run_pathway_probe(arm, e5_probe_observations())
        except PathwayProbeError as exc:
            outcome = PathwayProbeRefusal.of(
                arm=arm.name,
                reason=f"the probe states no rate: {type(exc).__name__}: {exc}",
            )
        except Exception as exc:  # noqa: BLE001 - the probe's failure is a finding, never E5's
            outcome = PathwayProbeRefusal.of(
                arm=arm.name,
                reason=f"the probe could not run: {type(exc).__name__}: {exc}",
            )
    if isinstance(outcome, PathwayProbeReport):
        (directory / PROBE_REFUSAL_FILENAME).unlink(missing_ok=True)
        return outcome, write_probe_report(directory / PROBE_FILENAME, outcome)
    (directory / PROBE_FILENAME).unlink(missing_ok=True)
    return outcome, write_probe_refusal(directory / PROBE_REFUSAL_FILENAME, outcome)


def _probe_lines(outcome: PathwayProbeReport | PathwayProbeRefusal) -> list[str]:
    """R7.21's lines beside the headline, read off the record the probe step wrote.

    One line per input, then the inputs no pair changed -- or, when the probe stated no rate,
    the refusal's reason. Worded so that no input's silence relabels the headline: an
    unresponsive pathway, and a probe that could not run, are findings beside E5's number.
    """
    if isinstance(outcome, PathwayProbeRefusal):
        return [
            f"pathway probe (R7.21): refused: {outcome.reason} -- the probe's absence is a "
            "finding beside the headline, which it does not relabel"
        ]
    lines = [
        f"pathway probe (R7.21): {result.input_name} changed {result.changed}/{result.pairs} "
        "binding decisions"
        for result in outcome.inputs
    ]
    lines.append(
        f"unresponsive inputs: {list(outcome.unresponsive_inputs)} -- a finding beside the "
        "headline; no input's silence relabels it (R7.21)"
    )
    return lines


def _refuse_e5(reason: str, what: str) -> int:
    """Print an E5 refusal naming the input, and no headline (R7.8)."""
    print(f"[FAIL] {reason}", file=sys.stderr)
    print(f"No headline uplift number is produced without {what}.", file=sys.stderr)
    return EXIT_MISSING_INPUT


def _run_e5_suite(args: argparse.Namespace, contract: MetricContract) -> int:
    """``--suite e5-primary``: the consensus arm against B-prime's arm E (task 22.1).

    Every refusal comes before any replicate runs, and each is a missing required input
    (:data:`EXIT_MISSING_INPUT`) printing no headline: a refused flag, a missing or defective
    B-prime record (:class:`~uplift.bprime_record.BprimeRecordError`), E5 seeds colliding with
    B-prime's, a world that cannot be resolved, or arms that cannot be built. Then, in order:

    1. R7.21's pathway probe over a FRESH consensus arm (:func:`_e5_pathway_probe`), written to
       ``pathway-probe.json`` -- or ``pathway-probe-refused.json``, naming why no rate exists --
       before anything is measured, because it costs seconds. It refuses nothing: the probe's
       absence is a finding beside the headline, and the headline still runs.
    2. B-prime's comparator is re-measured in this environment -- arms E and E' at B-prime's
       measurement seeds, by :func:`~uplift.e5_suite.measure_bprime_reproduction` priced with
       :func:`~uplift.e5_suite.production_arm_cost` -- and ``reproduction.json`` is written,
       BEFORE the harness runs. ``production_arm_cost`` is read from this module's globals at
       call time, which is the seam a test injects so that no twin runs. A non-reproduction is
       printed beside the headline and is not a refusal (API2 amendment 2).
    3. ``UpliftHarness(loop_config=E5_LOOP).run([e5_scenario()], build_e5_arms(record), n)``.
    4. R7.20's dispatch record, summarised from the consensus arm's runs ALONE --
       ``summarise_dispatch`` refuses another arm's (API2 amendment 1.1). It is built before
       anything is printed or written, so a tally the record refuses -- a defect in what the
       consensus arm counted -- raises, and no headline is published without its record.
    5. The headline, assembled against ``tuned_static`` alone, with the reproduction verdict,
       the dispatch line and the probe's lines beside it; then the result artifact, written
       exactly as the canonical suite writes it, and ``dispatch.json`` beside it.
    """
    n, _canonical_loop, reduced = _resolve_run_config(args)
    refusals = _e5_refusals(args, n=n, reduced=reduced)
    if refusals:
        return _refuse_e5(
            f"required input unresolvable: suite {E5_SUITE} refuses " + "; ".join(refusals),
            "an admissible E5 invocation",
        )
    try:
        record = read_bprime_record(REPO_ROOT)
    except BprimeRecordError as exc:
        return _refuse_e5(
            f"required input missing or malformed: B-prime record ({BPRIME_PROVENANCE_PATH}, "
            f"{BPRIME_ARTIFACT_PATH}): {exc}",
            "the committed B-prime record",
        )
    try:
        e5_replicate_seeds(n, record)
        scenario = e5_scenario()
        arms = build_e5_arms(record)
        arm_names = [spec.name for spec in arms]
        roles = registered_roles(arms)
        control = resolve_control_spec(
            baseline_arm=args.baseline_arm, pooled_baseline=False, arm_names=arm_names
        )
    except (KeyError, PolicyUnavailableError, TuningUnavailableError, ValueError) as exc:
        return _refuse_e5(
            f"required input unresolvable: suite {E5_SUITE}: {type(exc).__name__}: {exc}",
            "a resolvable E5 suite",
        )

    emission_factor = DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY
    output_path = args.output if args.output is not None else _default_artifact_path()
    print(f"uplift reproduction -- suite: {E5_SUITE} -- mode: fully-powered PROOF")
    print(
        f"  scenario: {scenario.name} (world cell {record.cell}, no shock, base seed "
        f"{scenario.seed})"
    )
    print(f"  replicates per arm: {n} (INV-TW-002 floor: {MIN_SCENARIOS})")
    print(
        f"  closed-loop horizon: {E5_LOOP.duration_hours}h in {E5_LOOP.step_hours}h steps "
        f"(levers: {E5_LOOP.levers})"
    )
    print(f"  arms: {', '.join(arm_names)}")
    print(f"  comparator: {_describe_control(control)}")
    print(
        f"  B-prime record: run {record.source_run_id} at {record.source_revision_sha}, "
        f"artifact sha256 {record.artifact_sha256}"
    )

    # --- 1. R7.21's pathway probe of a FRESH arm, before anything is measured (finding 109) ---
    probe, probe_path = _e5_pathway_probe(output_path.parent)

    # --- 2. B-prime's comparator, re-measured here BEFORE the harness runs (amendment 2) ---
    reproduction = measure_bprime_reproduction(
        record, E5_REPRODUCED_ARMS, cost_of=production_arm_cost
    )
    reproduction_path = write_bprime_reproduction(
        output_path.parent / REPRODUCTION_FILENAME, reproduction
    )
    print()
    for line in _reproduction_lines(reproduction):
        print(line)

    # --- 3. the harness, then 4. R7.20's record from the consensus arm's runs alone ---
    harness = UpliftHarness(loop_config=E5_LOOP, emission_factor=emission_factor)
    harness_result = harness.run([scenario], arms, n_per_arm=n)
    dispatch = summarise_dispatch(
        harness_result.runs_by_pair[(scenario.name, DEFAULT_CONSENSUS_ARM)],
        arm=DEFAULT_CONSENSUS_ARM,
    )
    result = assemble_uplift_result(
        harness_result,
        contract,
        consensus_arm=DEFAULT_CONSENSUS_ARM,
        baseline_arm=control.baseline_arm,
    )
    report = build_uplift_report(result)

    # --- 5. the headline; beside it the reproduction verdict, the dispatch and probe lines ---
    print()
    print(report.render())
    print(_comparator_line(reproduction))
    for line in _dispatch_lines(dispatch):
        print(line)
    for line in _probe_lines(probe):
        print(line)

    _print_disclosures(result, reduced=False)

    # --- persist the artifact C60 reads, then the dispatch record beside it ---
    provenance = resolve_provenance(
        arms=arm_names,
        arm_roles=roles,
        replicates_per_arm=n,
        seeds=[scenario.seed],
    )
    written = _write_result_artifact(
        output_path,
        result,
        report,
        harness_result=harness_result,
        provenance=provenance,
    )
    dispatch_path = write_dispatch_report(output_path.parent / DISPATCH_FILENAME, dispatch)
    probe_kind = "refusal" if isinstance(probe, PathwayProbeRefusal) else "record"
    print()
    print(f"wrote pathway probe {probe_kind}: {probe_path}")
    print(f"wrote reproduction record: {reproduction_path}")
    print(f"wrote result artifact: {written}")
    print(f"wrote dispatch record: {dispatch_path}")

    exit_code = uplift_exit_code(harness_result)
    if exit_code != EXIT_SUCCESS:
        print(
            "[FAIL] no scenario completed for any arm -- nothing to report.",
            file=sys.stderr,
        )
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m uplift.cli`` (R7.2, R7.5-R7.8, R6.14).

    Returns ``0`` when at least one scenario completed (a valid outcome regardless of
    which arm wins, R4.6), :data:`EXIT_MISSING_INPUT` when a required input is missing
    or malformed -- the metric contract, or a comparator that cannot be resolved -- printing
    no headline number (R7.8), or the harness's ``EXIT_NO_COMPLETED_RUN`` when nothing
    completed. ``--pooled-baseline`` with ``--baseline-arm`` is refused by the argument
    parser itself (exit status 2, its usage message).

    ``--suite e5-primary`` (session 12) runs :func:`_run_e5_suite` after the contract is
    loaded; its own refusals, and a missing or defective B-prime record, are missing required
    inputs too. The default ``--suite canonical`` is the path below, unchanged.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --- required input: the pre-registered metric contract (R7.8, R3.10) ---
    # Load it FIRST, before any headline number is computed or printed, so a missing or
    # malformed contract exits failure naming the input with no number ever emitted.
    contract_path = args.contract
    try:
        contract = load_contract(contract_path) if contract_path is not None else load_contract()
    except MetricContractError as exc:
        named = contract_path if contract_path is not None else "uplift/metric_contract.yaml"
        print(
            f"[FAIL] required input missing or malformed: metric contract ({named}): {exc}",
            file=sys.stderr,
        )
        print(
            "No headline uplift number is produced without a valid metric contract.",
            file=sys.stderr,
        )
        return EXIT_MISSING_INPUT

    if args.suite == E5_SUITE:
        return _run_e5_suite(args, contract)

    n, loop, reduced = _resolve_run_config(args)
    scenarios = adversarial_suite()
    arms = build_arms(seed=args.seed)
    arm_names = [spec.name for spec in arms]

    # --- required input: the comparator, resolved BEFORE any replicate runs (AD-16) ---
    try:
        roles = registered_roles(arms)
        control = resolve_control_spec(
            baseline_arm=args.baseline_arm,
            pooled_baseline=args.pooled_baseline,
            arm_names=arm_names,
        )
        if control.baseline_arm == DEFAULT_CONSENSUS_ARM:
            raise ValueError(
                f"--baseline-arm {DEFAULT_CONSENSUS_ARM!r} is the consensus arm itself; a "
                "contrast of an arm with itself is zero by construction and measures nothing"
            )
    except ValueError as exc:
        print(f"[FAIL] required input unresolvable: comparator: {exc}", file=sys.stderr)
        print(
            "No headline uplift number is produced without a resolvable comparator.",
            file=sys.stderr,
        )
        return EXIT_MISSING_INPUT

    emission_factor = DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY

    mode = "reduced-cost SMOKE (NOT a fully-powered proof)" if reduced else "fully-powered PROOF"
    print(f"uplift reproduction -- mode: {mode}")
    print(
        f"  scenarios: {len(scenarios)} adversarial seeds ({', '.join(s.name for s in scenarios)})"
    )
    print(f"  replicates per arm: {n} (INV-TW-002 floor: {MIN_SCENARIOS})")
    print(f"  closed-loop horizon: {loop.duration_hours}h in {loop.step_hours}h steps")
    print(f"  comparator: {_describe_control(control)}")

    # --- run the harness on the declared seeds (R7.2) ---
    if reduced:
        harness_result = _run_reduced(scenarios, arms, n, loop, emission_factor)
    else:
        harness = UpliftHarness(loop_config=loop, emission_factor=emission_factor)
        harness_result = harness.run(scenarios, arms, n_per_arm=n)

    result = assemble_uplift_result(
        harness_result,
        contract,
        consensus_arm=DEFAULT_CONSENSUS_ARM,
        baseline_arm=control.baseline_arm,
    )
    report = build_uplift_report(result)

    # --- headline number co-located with its interval, verdict and FidelityReport ---
    print()
    print(report.render())

    # --- honesty disclosures (R7.5, R7.6) + version-controlled noise tolerance ---
    _print_disclosures(result, reduced=reduced)

    # --- persist the artifact the C60 uplift_truth gate reads ---
    # The provenance record is what makes this run attributable: the seed set is the
    # scenario base seeds (every replicate seed is derived from them by
    # ``replicate_seed``), the roles are what each arm declared, and the revision is what
    # marks a run as measured before or after the ADR-054 dispatch choke point, across which
    # uplift is not comparable.
    output_path = args.output if args.output is not None else _default_artifact_path()
    provenance = resolve_provenance(
        arms=arm_names,
        arm_roles=roles,
        replicates_per_arm=n,
        seeds=[scenario.seed for scenario in scenarios],
    )
    written = _write_result_artifact(
        output_path,
        result,
        report,
        harness_result=harness_result,
        provenance=provenance,
    )
    print()
    print(f"wrote result artifact: {written}")

    exit_code = uplift_exit_code(harness_result)
    if exit_code != EXIT_SUCCESS:
        print(
            "[FAIL] no scenario completed for any arm -- nothing to report.",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":  # pragma: no cover — module entrypoint
    sys.exit(main())
