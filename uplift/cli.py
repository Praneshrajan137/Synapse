"""
SYNAPSE Decision-Integrity Uplift Proof — the one-command reproduction CLI (R7).

``python -m uplift.cli`` is the single, ``$0``, synthetic-seed-only command that runs
the closed-loop counterfactual :class:`~uplift.harness.UpliftHarness` on the declared
adversarial seeds (:data:`~uplift.scenarios.ADVERSARIAL_SUITE`), assembles the
:class:`~uplift.interfaces.UpliftResult` under the pre-registered
:class:`~uplift.contract.MetricContract`, and prints the **headline uplift number
co-located with its twin-:class:`~uplift.fidelity.FidelityReport`** (R7.2, R7.7,
R5.2/R5.6). It also persists the result to the ``artifacts/uplift/result.json`` artifact
the C60 ``uplift_truth`` gate reads. That artifact is not under version control: the gate
is trigger-aware (AD-9, CF-4), so it returns PASS/FAIL only when it is invoked with
``--require-fresh-run`` in the same job that ran this command, and SKIP everywhere else.

Honesty invariants surfaced by this command:

* **Synthetic seed data only (R7.5).** Every scenario is driven by the harness's seeded
  synthetic demand realization (``numpy.random.SeedSequence``-derived replicate seeds);
  no real, scraped, or purchased data is read.
* **No external paid service (R7.6).** The whole pipeline is in-process — the twin, the
  baselines, and (when available) the in-process consensus arm. Nothing dials a paid
  API. The consensus arm requires an injected in-process protocol + transport and, when
  that cannot be stood up in a plain environment, its runs fail honestly (recorded as
  failed runs, excluded from aggregation) rather than crashing or fabricating a decision.
* **Version-controlled noise tolerance (≤ 1.0 pp).** :data:`NOISE_TOLERANCE_PP` is the
  committed run-to-run reproduction tolerance; it is stated in the output.
* **Missing required input ⇒ honest failure (R7.8).** A missing/malformed metric
  contract (:class:`~uplift.contract.MetricContractError`) exits with a non-zero status,
  naming the missing input, and prints **no** headline number.

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
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from digital_twin.simulation.monte_carlo import MIN_SCENARIOS

from uplift.baselines import (
    Greedy_Routing,
    NoOpDisruption,
    Par_Level_Reorder,
    Static_Pricing,
)
from uplift.consensus_arm import ConsensusArmUnavailable, build_consensus_arm
from uplift.contract import MetricContractError, load_contract
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    EXIT_SUCCESS,
    HarnessResult,
    LoopConfig,
    UpliftHarness,
    UpliftProvenance,
    aggregate_arm,
    assemble_uplift_result,
    build_uplift_artifact,
    build_uplift_report,
    replicate_seed,
    resolve_provenance,
    run_closed_loop,
    uplift_exit_code,
)
from uplift.interfaces import DecisionPolicy, Observation, PolicyAction, Scenario
from uplift.kpi import DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY
from uplift.scenarios import adversarial_suite

# ---------------------------------------------------------------------------
# Version-controlled constants
# ---------------------------------------------------------------------------
#: The committed run-to-run reproduction noise tolerance, in percentage points (R7.3).
#: A headline-uplift difference between two reproductions of the same seeded config must
#: not exceed this many percentage points. Version-controlled here (≤ 1.0 pp) so the
#: tolerance the reproduction is judged against cannot be quietly widened.
NOISE_TOLERANCE_PP: float = 1.0

#: Default replicate count for reduced-cost smoke reproduction (well below the
#: INV-TW-002 ``MIN_SCENARIOS`` floor; NOT a fully-powered proof — see module docstring).
SMOKE_REPLICATES: int = 5

#: Reduced closed-loop cadence used by smoke mode (short horizon for fast turnaround).
SMOKE_LOOP = LoopConfig(duration_hours=2.0, step_hours=1.0)

#: Non-zero exit status for a missing/malformed required input (R7.8). Distinct from the
#: harness's own no-completed-run failure so a missing input is diagnosable.
EXIT_MISSING_INPUT: int = 2

# Exit code re-exported for callers/tests that want the success sentinel by name.
__all__ = ["NOISE_TOLERANCE_PP", "EXIT_MISSING_INPUT", "build_arms", "main"]


# ---------------------------------------------------------------------------
# Consensus arm (honest-failure path)
# ---------------------------------------------------------------------------
class _UnavailableConsensusArm:
    """A stand-in consensus arm whose every decision fails honestly (R2.7, R7.6).

    The real :class:`~uplift.consensus_arm.ConsensusArm` needs an injected in-process
    consensus protocol + A2A transport (the full eight-agent + twin network), which a
    plain ``$0`` environment cannot stand up. Rather than crash the whole run or
    fabricate a decision, the CLI substitutes this arm under the canonical consensus
    name: each :meth:`decide` raises :class:`ConsensusArmUnavailable`, so the harness
    records every consensus run as a *failed* run, excludes it from aggregation, and
    continues — exactly the honest-failure contract. The assembled result is then marked
    incomplete and the consensus-vs-baseline headline is not credited to SYNAPSE.
    """

    def __init__(self, reason: str, name: str = DEFAULT_CONSENSUS_ARM) -> None:
        self.name = name
        self._reason = reason

    def decide(self, obs: Observation) -> PolicyAction:  # noqa: ARG002 — always fails
        raise ConsensusArmUnavailable(self._reason)


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
            f"consensus arm unavailable in this environment: "
            f"{type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# Arm construction
# ---------------------------------------------------------------------------
def build_arms(seed: int = 0) -> tuple[DecisionPolicy, ...]:
    """Build the arm suite: the consensus arm plus the four transparent baselines.

    The consensus arm is named :data:`DEFAULT_CONSENSUS_ARM` (``"consensus"``) so result
    assembly identifies it and pools every other (baseline) arm into "the transparent
    operator without SYNAPSE". The four baselines are the pre-registered control suite
    (R1.1): ``Par_Level_Reorder`` (the fill-rate-relevant reorder control),
    ``Static_Pricing``, ``Greedy_Routing``, and ``NoOpDisruption``.
    """
    return (
        _build_consensus_arm(),
        Par_Level_Reorder(s=20, S=100, seed=seed),
        Static_Pricing(markup=1.5, seed=seed),
        Greedy_Routing(),
        NoOpDisruption(),
    )


# ---------------------------------------------------------------------------
# Reduced-cost (smoke) harness execution — bypasses the INV-TW-002 guard
# ---------------------------------------------------------------------------
def _run_reduced(
    scenarios: Sequence[Scenario],
    arms: Sequence[DecisionPolicy],
    n_replicates: int,
    loop_config: LoopConfig,
    emission_factor: float,
) -> HarnessResult:
    """Run a reduced-cost harness matrix by calling the closed loop directly (smoke).

    This deliberately **bypasses** :meth:`UpliftHarness.run_arm`'s INV-TW-002
    ``n >= MIN_SCENARIOS`` under-power guard so ``make prove-uplift`` and the
    reproduction tests run in seconds. It reuses the exact same per-scenario replicate
    seeding (:func:`replicate_seed`) so every arm still sees the identical seeded demand
    realization (the attribution guarantee, R2.1/R2.5). A result produced this way is a
    fast smoke reproduction, NOT a fully-powered proof — only ``n >= MIN_SCENARIOS``
    (``--full``) satisfies INV-TW-002.
    """
    arm_results: dict[tuple[str, str], object] = {}
    runs_by_pair: dict[tuple[str, str], list] = {}
    all_runs: list = []

    for scenario in scenarios:
        seeds = [replicate_seed(scenario.seed, index) for index in range(n_replicates)]
        for policy in arms:
            runs = [
                run_closed_loop(
                    scenario, policy, seed, policy.name, loop_config, emission_factor
                )
                for seed in seeds
            ]
            pair = (scenario.name, policy.name)
            runs_by_pair[pair] = runs
            arm_results[pair] = aggregate_arm(policy.name, runs)
            all_runs.extend(runs)

    return HarnessResult(
        arm_results=arm_results,  # type: ignore[arg-type]
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=tuple(policy.name for policy in arms),
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
    result,
    report,
    *,
    harness_result: HarnessResult | None = None,
    provenance: UpliftProvenance | None = None,
) -> Path:
    """Write the canonical :class:`~uplift.harness.UpliftArtifact` to ``path``.

    The gate (:func:`scripts.audit.uplift_truth.admit`) parses this file through
    :meth:`~uplift.harness.UpliftArtifact.read`, so every field it needs must be present:
    a finite ``headline_uplift``, a boolean ``incomplete``, the fidelity block that
    co-locates the KL context (R5.6), and the provenance record naming the revision, run,
    seed set, arms, and replicates-per-arm count the audit's R2.3 requires -- an artifact
    missing any of them is inadmissible, not silently readable. Serialisation is canonical
    (``sort_keys=True``, tight separators) so two runs of the same seed set at the same
    revision produce byte-identical files.

    ``provenance`` is resolved from the environment when not supplied; a caller with no
    ``harness_result`` gets an artifact with no arm aggregates and a zero replicate
    count, which is honest (and inadmissible as proof) rather than fabricated.
    """
    resolved = (
        provenance
        if provenance is not None
        else resolve_provenance(arms=(), replicates_per_arm=0, seeds=())
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
            "its twin-fidelity report. Synthetic seed data only; no external paid "
            "service."
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
        loop = LoopConfig(
            duration_hours=SMOKE_LOOP.duration_hours, step_hours=args.step_hours
        )
    else:
        loop = LoopConfig(step_hours=args.step_hours)

    return n, loop, reduced


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m uplift.cli`` (R7.2, R7.5–R7.8).

    Returns ``0`` when at least one scenario completed (a valid outcome regardless of
    which arm wins, R4.6), :data:`EXIT_MISSING_INPUT` when a required input is missing
    or malformed (R7.8, printing no headline number), or the harness's
    ``EXIT_NO_COMPLETED_RUN`` when nothing completed.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --- required input: the pre-registered metric contract (R7.8, R3.10) ---
    # Load it FIRST, before any headline number is computed or printed, so a missing or
    # malformed contract exits failure naming the input with no number ever emitted.
    contract_path = args.contract
    try:
        contract = (
            load_contract(contract_path) if contract_path is not None else load_contract()
        )
    except MetricContractError as exc:
        named = contract_path if contract_path is not None else "uplift/metric_contract.yaml"
        print(
            f"[FAIL] required input missing or malformed: metric contract "
            f"({named}): {exc}",
            file=sys.stderr,
        )
        print(
            "No headline uplift number is produced without a valid metric contract.",
            file=sys.stderr,
        )
        return EXIT_MISSING_INPUT

    n, loop, reduced = _resolve_run_config(args)
    scenarios = adversarial_suite()
    arms = build_arms(seed=args.seed)
    emission_factor = DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY

    mode = "reduced-cost SMOKE (NOT a fully-powered proof)" if reduced else "fully-powered PROOF"
    print(f"uplift reproduction — mode: {mode}")
    print(
        f"  scenarios: {len(scenarios)} adversarial seeds "
        f"({', '.join(s.name for s in scenarios)})"
    )
    print(f"  replicates per arm: {n} (INV-TW-002 floor: {MIN_SCENARIOS})")
    print(f"  closed-loop horizon: {loop.duration_hours}h in {loop.step_hours}h steps")

    # --- run the harness on the declared seeds (R7.2) ---
    if reduced:
        harness_result = _run_reduced(scenarios, arms, n, loop, emission_factor)
    else:
        harness = UpliftHarness(loop_config=loop, emission_factor=emission_factor)
        harness_result = harness.run(scenarios, arms, n_per_arm=n)

    result = assemble_uplift_result(
        harness_result, contract, consensus_arm=DEFAULT_CONSENSUS_ARM
    )
    report = build_uplift_report(result)

    # --- headline number co-located with its FidelityReport (R7.7, R5.2/R5.6) ---
    print()
    print(report.render())

    # --- honesty disclosures (R7.5, R7.6) + version-controlled noise tolerance ---
    print()
    print(f"applied noise tolerance: <= {NOISE_TOLERANCE_PP:.1f} percentage point "
          "(version-controlled reproduction tolerance)")
    print("data provenance: synthetic seed-generated data only (no real/scraped/paid data)")
    print("external services: none — fully in-process (no external paid service)")
    if reduced:
        print(
            "note: reduced-cost smoke run — a fully-powered proof requires "
            f"n >= {MIN_SCENARIOS} per arm (--full)."
        )
    if result.incomplete:
        print(
            "note: result marked INCOMPLETE — at least one arm (e.g. the consensus arm) "
            "could not complete every scenario; no incomplete pair is credited to SYNAPSE."
        )
    if result.all_wins_warning:
        print(
            "self-scrutiny warning: every classified pair is SYNAPSE_WINS — scrutinize "
            "for measurement bias before trusting this result."
        )

    # --- persist the artifact the C60 uplift_truth gate reads ---
    # The provenance record is what makes this run attributable: the seed set is the
    # scenario base seeds (every replicate seed is derived from them by
    # ``replicate_seed``), and the revision is what marks a run as measured before or
    # after the ADR-054 dispatch choke point, across which uplift is not comparable.
    output_path = args.output if args.output is not None else _default_artifact_path()
    provenance = resolve_provenance(
        arms=[policy.name for policy in arms],
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
            "[FAIL] no scenario completed for any arm — nothing to report.",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":  # pragma: no cover — module entrypoint
    sys.exit(main())
