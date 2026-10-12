"""Property-based test that the uplift harness is deterministic across OS processes.

Feature: purpose-achievement-audit, Property 15: The harness is deterministic across
processes

    *For any* seed set, two runs of the harness in two separate operating-system
    processes produce byte-identical canonical arm KPI aggregates and byte-identical
    canonical artifact bytes, differing only in the two fields a second run legitimately
    changes -- the run identifier and the write instant.

**Validates: Requirements 2.5**

Why this has to cross a process boundary
----------------------------------------
Task 10.1 gave ``uplift/harness.py`` a canonical serialisation and said so in its own
docstring: ``canonical_arm_aggregates`` "excludes ``run_id`` and ``written_at``, the only
two artifact fields that legitimately differ between two runs of the same seed set. Two
OS processes replaying the same seeds must produce this string byte for byte." R2.5 is
that sentence turned into a claim, and it is only a claim if the two runs are two
processes.

An in-process repeat cannot see the failure modes R2.5 exists to exclude:

* **Hash-seed dependence.** ``PYTHONHASHSEED`` is randomised per process. A KPI
  aggregate assembled by iterating a ``set``, or a mapping whose key order reached the
  serialiser unsorted, is stable within one interpreter and unstable across two. The two
  child processes below are launched with *different, explicit* hash seeds and the
  payload carries each child's seed back, so the assertion that the two seeds differ is
  itself checked rather than assumed.
* **Process-global state.** A module-level cache, an RNG seeded once at import, or a
  ``numpy`` global reached during aggregation all replay identically inside one
  interpreter and can diverge between two.
* **Byte-level drift that compares equal after parsing.** The comparison here is on the
  serialised strings, not on parsed objects, so a formatting or key-order difference
  fails even when the two runs agree numerically. That is the difference between "two
  artifacts are equal" and "a diff of two artifacts is a diff of their measurements".

The two children also differ in ``SYNAPSE_RUN_ID``, and each emits *two* renderings of
the one run it performed: one with the provenance pinned to a fixed
``(revision, run_id, written_at)``, and one with the provenance resolved from its own
environment. That costs no extra twin work -- both are built from the same
``HarnessResult`` -- and it lets one pair of processes pin both halves of R2.5's scope:
the pinned bytes must be identical, and the environment-derived bytes must differ *only*
in ``run_id`` and ``written_at``.

Deliberately **not** restated here
----------------------------------
* ``tests/uplift/test_seed_reproducibility_property.py`` (feature ``core-purpose-uplift``,
  Property 11) already owns "two *in-process* runs of the same seed configuration produce
  headline values within the committed noise tolerance, and in fact exactly equal". It
  compares one float, in one interpreter. Neither the process boundary, the aggregate
  surface, nor the serialised bytes are in its scope.
* ``tests/uplift/test_reproduction_stability_property.py`` (Property 23) makes the same
  in-process, single-float claim through the CLI's reduced-cost path.
* ``tests/uplift/test_uplift_artifact_canonical_roundtrip_property.py`` (Property 14)
  owns the artifact's serialisation *contract* -- lossless round-trip, sorted compact
  keys, two constructions of one logical value agreeing byte for byte, and rejection of
  an unsayable artifact. It constructs every artifact from generated data and never runs
  the harness. This file supplies the other half: two real runs, in two processes,
  reaching the same bytes.
* ``tests/uplift/test_replicate_seed_arm_independence_property.py`` owns
  ``replicate_seed``'s independence from the arm. The seed sequences compared below are
  compared *across processes* (and against the parent's own recomputation), which is a
  different claim: that the derivation is not interpreter-dependent.
* ``tests/uplift/test_arm_aggregate_property.py`` owns the mean/std arithmetic. Nothing
  here re-derives it; the aggregates are compared to each other, never to a formula.

Scope this property does **not** cover, stated plainly
-----------------------------------------------------
* **The consensus arm is not exercised.** The arms are two of the pre-registered
  deterministic baselines, one of them carrying the consensus arm's name so result
  assembly treats it as the consensus side. Standing up the real eight-agent
  ``ConsensusProtocol`` inside two child processes per Hypothesis example is not
  affordable, and it is a different subject: a hash-seed or global-state dependence
  *inside* ``ConsensusProtocol`` would not be caught here. It would surface in the
  powered run owned by ``.github/workflows/uplift.yml``.
* **The replicate count is small and generated, never ``MIN_SCENARIOS``.** Each example
  runs ``1 scenario x 2 arms x 1-2 replicates`` per process over a one- or two-step
  horizon, by calling :func:`uplift.harness.run_closed_loop` directly -- the same path
  the CLI's reduced-cost mode uses. **What that costs the claim:** determinism is a
  structural property (same inputs, same bytes), so a small replicate count exercises
  the same code path as a large one and a divergence would show at ``n = 1`` as readily
  as at ``n = 1000``. What a small count does *not* establish is that the aggregation
  stays byte-stable at scale -- ``numpy``'s pairwise summation makes float addition
  order-sensitive, and ``aggregate_arm`` sorts by seed precisely to remove that
  dependence, but that sort only becomes load-bearing once there are enough summands for
  the pairwise blocking to engage. A powered 1000-replicate-per-arm cross-process
  comparison is the only thing that would close that gap, and it belongs to
  ``.github/workflows/uplift.yml`` (task 10.5), never to a dev box (I-0 forbids
  ``MIN_SCENARIOS``-scale runs there).

Cost and routing
----------------
``@pytest.mark.slow``: each example drives the real SimPy twin in two spawned OS
processes, so interpreter start-up dominates. Owned by ``.github/workflows/ci.yml``'s
``uplift-verify`` job at ``HYPOTHESIS_PROFILE=heavy -m slow`` (task 12.2). ``max_examples``
is never hardcoded -- it comes from the root ``conftest.py`` profiles (``dev``=10,
``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

Every child is run through :func:`subprocess.run` with a timeout, so it is reaped in the
same call that started it and no background process survives the test. A child that
fails, times out, or writes no payload **fails** this test with its captured output: a
harness that cannot run is not evidence that it is deterministic (I-7 -- a SKIP is never
a PASS, and this file contains no skip).
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.harness import DEFAULT_CONSENSUS_ARM, UpliftArtifact, replicate_seed

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: The two hash seeds the children are launched with. Different, and explicit, so the
#: cross-process comparison genuinely spans two hash orderings rather than relying on
#: CPython's default randomisation (which CI may pin).
_HASH_SEEDS: Final[tuple[str, str]] = ("0", "104729")

#: The revision both children run at -- two runs of the same seed set at the same
#: revision is exactly the pair R2.5 quantifies over.
_REVISION: Final[str] = "prop15deadbeef"

#: Pinned provenance for the byte-identity comparison. ``run_id`` and ``written_at`` are
#: the only artifact fields a second run legitimately changes, so the pinned rendering
#: holds them fixed and the environment-derived rendering lets them move.
_PINNED_RUN_ID: Final[str] = "prop15-pinned-run"
_PINNED_WRITTEN_AT: Final[str] = "2026-02-20T00:00:00Z"

#: Per-child run identifiers, distinct so the environment-derived rendering must differ.
_RUN_IDS: Final[tuple[str, str]] = ("prop15-run-a", "prop15-run-b")

#: Fixed fidelity, so the artifact depends only on the seeds and the policies (the live
#: C34 gauge is another property's subject).
_KL_DIVERGENCE: Final[float] = 0.05
_KL_THRESHOLD: Final[float] = 0.1

#: Passed through to the artifact; its *value* is Property 16's subject, not this one's.
_NOISE_TOLERANCE_PP: Final[float] = 1.0

#: Generous per-child wall clock. Exceeding it fails the test (and reaps the child).
_CHILD_TIMEOUT_SECONDS: Final[float] = 900.0

# ---------------------------------------------------------------------------
# The worker: a separate OS process that runs the harness once and writes the
# canonical bytes. Executed as a file (argv[1] = config, argv[2] = payload) so nothing
# is parsed out of stdout, where incidental structlog output could land.
# ---------------------------------------------------------------------------
_WORKER_SOURCE: Final[str] = '''
# Cross-process uplift determinism worker (purpose-achievement-audit, Property 15).
# Runs the reduced-cost closed-loop matrix once and writes the canonical artifact bytes
# plus the canonical arm-aggregate string. Calls run_closed_loop directly -- the CLI's
# reduced-cost path -- so no ProcessPoolExecutor is involved and this process is the
# only one that touches the twin.
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.baselines import Par_Level_Reorder, Static_Pricing
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    HarnessResult,
    LoopConfig,
    aggregate_arm,
    arm_aggregates,
    assemble_uplift_result,
    build_uplift_artifact,
    build_uplift_report,
    canonical_arm_aggregates,
    replicate_seed,
    resolve_provenance,
    run_closed_loop,
)
from uplift.interfaces import Scenario


def build_policy(spec: dict[str, Any]) -> Any:
    # A pre-registered baseline, constructed from the spec. The consensus-named arm is
    # built exactly the same way from its own spec, so neither arm is privileged.
    if spec["kind"] == "par_level":
        policy = Par_Level_Reorder(s=spec["s"], S=spec["S"], seed=spec["seed"])
        policy.name = spec["name"]
        return policy
    return Static_Pricing(markup=spec["markup"], seed=spec["seed"], name=spec["name"])


def main() -> int:
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    loop = LoopConfig(
        duration_hours=config["duration_hours"], step_hours=config["step_hours"]
    )
    scenarios = tuple(
        Scenario(
            name=entry["name"],
            seed=entry["seed"],
            shock=ShockParams(**entry["shock"]),
            cold_start=entry["cold_start"],
        )
        for entry in config["scenarios"]
    )
    arms = tuple(build_policy(entry) for entry in config["arms"])
    replicates = config["replicates"]
    emission_factor = config["emission_factor"]

    arm_results: dict[tuple[str, str], Any] = {}
    runs_by_pair: dict[tuple[str, str], list[Any]] = {}
    all_runs: list[Any] = []
    replicate_seeds: dict[str, list[int]] = {}
    for scenario in scenarios:
        seeds = [replicate_seed(scenario.seed, index) for index in range(replicates)]
        replicate_seeds[scenario.name] = seeds
        for policy in arms:
            runs = [
                run_closed_loop(
                    scenario, policy, seed, policy.name, loop, emission_factor
                )
                for seed in seeds
            ]
            pair = (scenario.name, policy.name)
            runs_by_pair[pair] = runs
            arm_results[pair] = aggregate_arm(policy.name, runs)
            all_runs.extend(runs)

    harness_result = HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=scenarios,
        arm_names=tuple(policy.name for policy in arms),
    )
    result = assemble_uplift_result(
        harness_result,
        load_contract(),
        fidelity=FidelityReport(
            kl_divergence=config["kl_divergence"], threshold=config["threshold"]
        ),
        consensus_arm=config["consensus_arm"],
    )
    report = build_uplift_report(result)

    arm_names = [policy.name for policy in arms]
    base_seeds = [scenario.seed for scenario in scenarios]
    pinned = resolve_provenance(
        arms=arm_names,
        replicates_per_arm=replicates,
        seeds=base_seeds,
        revision=config["revision"],
        run_id=config["pinned_run_id"],
        written_at=config["pinned_written_at"],
    )
    # Resolved from this process's own environment: same revision, different run id.
    from_env = resolve_provenance(
        arms=arm_names, replicates_per_arm=replicates, seeds=base_seeds
    )
    # The parent asserts the two children carry distinct run identifiers; fail loudly
    # here if the environment did not actually supply this process's own one.
    if from_env.run_id != config["run_id"]:
        raise SystemExit(
            "environment run_id "
            + repr(from_env.run_id)
            + " is not the expected "
            + repr(config["run_id"])
        )
    tolerance = config["noise_tolerance_pp"]
    pinned_artifact = build_uplift_artifact(
        result,
        report,
        pinned,
        noise_tolerance_pp=tolerance,
        harness_result=harness_result,
    )
    env_artifact = build_uplift_artifact(
        result,
        report,
        from_env,
        noise_tolerance_pp=tolerance,
        harness_result=harness_result,
    )

    payload = {
        "pinned_artifact": pinned_artifact.to_canonical_json(),
        "env_artifact": env_artifact.to_canonical_json(),
        "aggregates": canonical_arm_aggregates(arm_aggregates(harness_result)),
        "digest": pinned_artifact.arm_aggregates_digest,
        "replicate_seeds": replicate_seeds,
        "completed": {
            "|".join(pair): aggregate.completed
            for pair, aggregate in arm_results.items()
        },
        "hash_seed": os.environ.get("PYTHONHASHSEED", ""),
        "pid": os.getpid(),
    }
    Path(sys.argv[2]).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# ---------------------------------------------------------------------------
# Generated configuration. Small on purpose (see the cost note in the module
# docstring): the subject is byte-stability across processes, not statistical power.
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class _RunConfig:
    """One generated harness configuration, shared verbatim by both child processes."""

    scenario_name: str
    seed: int
    shock: ShockParams
    cold_start: bool
    replicates: int
    duration_hours: float
    step_hours: float
    emission_factor: float
    arms: tuple[dict[str, Any], ...]

    def payload(self, *, run_id: str) -> dict[str, Any]:
        """The config mapping handed to a child. Identical for both children."""
        return {
            "scenarios": [
                {
                    "name": self.scenario_name,
                    "seed": self.seed,
                    "shock": dataclasses.asdict(self.shock),
                    "cold_start": self.cold_start,
                }
            ],
            "arms": [dict(arm) for arm in self.arms],
            "replicates": self.replicates,
            "duration_hours": self.duration_hours,
            "step_hours": self.step_hours,
            "emission_factor": self.emission_factor,
            "consensus_arm": DEFAULT_CONSENSUS_ARM,
            "kl_divergence": _KL_DIVERGENCE,
            "threshold": _KL_THRESHOLD,
            "noise_tolerance_pp": _NOISE_TOLERANCE_PP,
            "revision": _REVISION,
            "pinned_run_id": _PINNED_RUN_ID,
            "pinned_written_at": _PINNED_WRITTEN_AT,
            "run_id": run_id,
        }


# Shock multipliers in a modest band: the shock is real (it feeds ``TwinConfig`` and the
# engine constructor) without exploding the event count of a one-step run.
_multiplier = st.floats(
    min_value=0.8, max_value=1.5, allow_nan=False, allow_infinity=False
)


@st.composite
def _par_level_arm(draw: st.DrawFn, name: str) -> dict[str, Any]:
    low = draw(st.integers(min_value=0, max_value=40))
    return {
        "kind": "par_level",
        "name": name,
        "s": low,
        "S": low + draw(st.integers(min_value=1, max_value=80)),
        "seed": draw(st.integers(min_value=0, max_value=64)),
    }


@st.composite
def _static_pricing_arm(draw: st.DrawFn, name: str) -> dict[str, Any]:
    return {
        "kind": "static_pricing",
        "name": name,
        "markup": draw(
            st.floats(min_value=1.0, max_value=3.0, allow_nan=False, allow_infinity=False)
        ),
        "seed": draw(st.integers(min_value=0, max_value=64)),
    }


@st.composite
def _arm(draw: st.DrawFn, name: str) -> dict[str, Any]:
    if draw(st.booleans()):
        return draw(_par_level_arm(name))
    return draw(_static_pricing_arm(name))


@st.composite
def _run_configs(draw: st.DrawFn) -> _RunConfig:
    """One scenario, two arms, one or two replicates, over a one- or two-step horizon."""
    return _RunConfig(
        scenario_name=draw(st.sampled_from(("prop15-a", "prop15-b"))),
        seed=draw(st.integers(min_value=0, max_value=2**31 - 1)),
        shock=ShockParams(
            demand_multiplier=draw(_multiplier),
            lead_time_multiplier=draw(_multiplier),
            failure_rate_multiplier=draw(_multiplier),
            spoilage_rate_multiplier=draw(_multiplier),
        ),
        cold_start=draw(st.booleans()),
        replicates=draw(st.integers(min_value=1, max_value=2)),
        duration_hours=draw(st.sampled_from((1.0, 2.0))),
        step_hours=1.0,
        emission_factor=draw(
            st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False)
        ),
        # The consensus-named arm and a baseline arm. Two *different* policies, so the
        # two recorded aggregate rows are distinguishable and a bug that collapsed them
        # into one row could not hide behind the byte comparison.
        arms=(
            draw(_arm(DEFAULT_CONSENSUS_ARM)),
            draw(_arm("baseline-prop15")),
        ),
    )


# ---------------------------------------------------------------------------
# Child execution
# ---------------------------------------------------------------------------
def _run_child(
    worker: Path,
    config: _RunConfig,
    *,
    index: int,
    workdir: Path,
) -> dict[str, Any]:
    """Run one child process and return its payload, failing loudly on any problem."""
    config_path = workdir / f"config-{index}.json"
    payload_path = workdir / f"payload-{index}.json"
    payload_path.unlink(missing_ok=True)
    config_path.write_text(
        json.dumps(config.payload(run_id=_RUN_IDS[index]), sort_keys=True),
        encoding="utf-8",
    )

    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = _HASH_SEEDS[index]
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["SYNAPSE_REVISION"] = _REVISION
    environment["SYNAPSE_RUN_ID"] = _RUN_IDS[index]

    try:
        # Fixed argv, no shell, repo-local interpreter and script.
        completed = subprocess.run(
            [sys.executable, str(worker), str(config_path), str(payload_path)],
            cwd=str(ROOT),
            env=environment,
            capture_output=True,
            text=True,
            timeout=_CHILD_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:  # the child is reaped by subprocess.run
        pytest.fail(
            f"determinism worker {index} exceeded {_CHILD_TIMEOUT_SECONDS}s: {expired}"
        )

    if completed.returncode != 0 or not payload_path.is_file():
        pytest.fail(
            f"determinism worker {index} failed (exit {completed.returncode})\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )

    parsed = json.loads(payload_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _normalised(text: str, *, run_id: str, written_at: str) -> str:
    """``text`` re-serialised with the run identifier and write instant substituted.

    The two fields R2.5 excludes are the two an honest second run must be allowed to
    change. Substituting them and comparing what remains is how "identical except for
    those two" is asserted rather than assumed.
    """
    artifact = UpliftArtifact.from_canonical_json(text)
    provenance = artifact.provenance.model_copy(
        update={"run_id": run_id, "written_at": written_at}
    )
    return artifact.model_copy(update={"provenance": provenance}).to_canonical_json()


# ---------------------------------------------------------------------------
# Property 15
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 15: The harness is deterministic across processes
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.data_too_large,
        HealthCheck.function_scoped_fixture,
    ],
)
@given(config=_run_configs())
def test_two_processes_replaying_one_seed_set_agree_byte_for_byte(
    config: _RunConfig, tmp_path: Path
) -> None:
    """R2.5: two OS processes, one seed set, byte-identical arm KPI aggregates."""
    worker = tmp_path / "determinism_worker.py"
    worker.write_text(_WORKER_SOURCE, encoding="utf-8")

    first = _run_child(worker, config, index=0, workdir=tmp_path)
    second = _run_child(worker, config, index=1, workdir=tmp_path)

    # -- the two runs really were two processes, under two hash orderings -------------
    assert first["pid"] != second["pid"], "both payloads came from one process"
    assert first["hash_seed"] == _HASH_SEEDS[0]
    assert second["hash_seed"] == _HASH_SEEDS[1]
    assert first["hash_seed"] != second["hash_seed"]

    # -- non-vacuity: the compared bytes carry a measurement -------------------------
    # Byte-equality of two empty aggregate sets would be trivially true, so the
    # aggregate set is required to be the full (scenario, arm) grid with at least one
    # completed replicate behind it.
    parsed = UpliftArtifact.from_canonical_json(first["pinned_artifact"])
    assert len(parsed.arm_aggregates) == len(config.arms)  # one scenario x two arms
    assert {aggregate.arm for aggregate in parsed.arm_aggregates} == {
        arm["name"] for arm in config.arms
    }
    assert sum(aggregate.completed for aggregate in parsed.arm_aggregates) > 0, (
        "no replicate completed in either arm, so the compared aggregates measure "
        "nothing"
    )
    assert first["aggregates"] not in ("", "[]")
    assert math.isfinite(parsed.headline_uplift)
    assert parsed.provenance.replicates_per_arm == config.replicates

    # -- R2.5: byte-identical arm KPI aggregates -------------------------------------
    assert first["aggregates"] == second["aggregates"]
    assert first["digest"] == second["digest"]
    assert parsed.arm_aggregates_digest == first["digest"]

    # -- byte-identical canonical artifact, provenance pinned ------------------------
    assert first["pinned_artifact"] == second["pinned_artifact"]

    # -- the replicate seed derivation is not interpreter-dependent -------------------
    # Compared across the two children AND against the parent's own recomputation, so a
    # third process witnesses it.
    expected_seeds = [
        replicate_seed(config.seed, index) for index in range(config.replicates)
    ]
    assert first["replicate_seeds"] == second["replicate_seeds"]
    assert first["replicate_seeds"][config.scenario_name] == expected_seeds

    # -- the completed/failed split is process-independent too ------------------------
    assert first["completed"] == second["completed"]

    # -- and the scope of the exclusion: run_id and written_at, nothing else ----------
    env_first = UpliftArtifact.from_canonical_json(first["env_artifact"])
    env_second = UpliftArtifact.from_canonical_json(second["env_artifact"])
    assert env_first.provenance.revision == env_second.provenance.revision == _REVISION
    assert env_first.provenance.run_id == _RUN_IDS[0]
    assert env_second.provenance.run_id == _RUN_IDS[1]
    # Distinct run identifiers, so these bytes MUST differ ...
    assert first["env_artifact"] != second["env_artifact"]
    # ... and once the two excluded fields are substituted, nothing else does.
    assert _normalised(
        first["env_artifact"],
        run_id=_PINNED_RUN_ID,
        written_at=_PINNED_WRITTEN_AT,
    ) == _normalised(
        second["env_artifact"],
        run_id=_PINNED_RUN_ID,
        written_at=_PINNED_WRITTEN_AT,
    )
    # The environment-derived rendering is the same measurement as the pinned one.
    assert env_first.arm_aggregates_digest == first["digest"]
    assert env_second.arm_aggregates_digest == second["digest"]
