"""The E5 suite: the consensus arm against arm E, as checkpoint B-prime tuned it.

Feature: decision-quality-proof, session 12 (wave 2; task 22.1's code half; R2.1, R2.5, R7.1,
R7.14, R7.19, R7.20; decision D12.2=a). ``python -m uplift.cli --suite e5-primary`` runs this.

**One cell, one contrast.** The primary world cell, unshocked, the consensus arm against
``tuned_static`` -- arm E at the levels :mod:`uplift.bprime_record` read from the committed
B-prime artifact. Arm E' (``tuned_static_in_sample``, B-prime's in-sample re-choice) runs beside
it as a recorded baseline that the named contrast does not read.

**Arm E is measured under the physics B-prime tuned it under, and every difference is
listed.** B-prime drove arm E through ``uplift.foresight.run_single_arm``: an engine built as
``SupplyChainSimulation(seed=seed, world=world)``, started, ``set_policy(restock_threshold=...)``,
then ``uplift.foresight._cadence(hours)`` slices of observe -> decide -> reorders -> advance.
The harness reproduces that here because (i) :func:`e5_scenario` carries the primary world, which
``uplift.harness._build_twin`` now passes to the engine; (ii) the scenario is unshocked, so every
multiplier ``_build_twin`` applies is the engine's own neutral 1.0; (iii) :data:`E5_LOOP` is
``_cadence(24.0)``'s cadence with ``levers="reorders_only"``, so only ``reorder_quantities``
reach the twin, through the same ``_apply_reorders``; and (iv) both read the committed restock
threshold and price the end state with the committed objective. The differences that remain:
``_build_twin`` pins ``TwinConfig``'s arrival rate and pick-pack mean at their defaults, while
``_new_arm_engine`` reads them from ``TW_*`` environment variables -- identical unless one is
set; and the replicate SEEDS differ on purpose (below). The slow clause of Property 97
asserts the objective equality with ``==`` at three seeds.

**The seeds.** Replicate ``i`` runs at ``replicate_seed(E5_SCENARIO_SEED, i)``, the harness's own
derivation, and :func:`e5_replicate_seeds` refuses any that lands on a B-prime tuning seed
(arm E's levels would then be in-sample there) or a B-prime measurement seed (E5 would re-draw
the realisations B-prime's split was measured on). Disjointness is a refusal, not luck.

**The consensus arm moves reorders only** (``levers=frozenset({"reorder"})``, the decision
API2.md records): arm E was tuned and B-prime's comparator measured under a reorders-only
driver, and a cost objective with no revenue term would let an arm that may also move price
"win" by suppressing demand. Assembly failure degrades to
:class:`~uplift.policies.UnavailableConsensusArm`, exactly as the canonical suite degrades.

**R7.21's probe states come from ONE sampler (finding 109).** :func:`e5_probe_observations`
observes one primary-cell twin run through ``uplift.harness.observe``. The E5 CLI's probe step
calls it, and so does the slow probe test, so the states a published probe report describes are
the states its test checks.

**The reproduction (API2 amendment 2): ONE implementation, which the E5 CLI and the controls
both call.** A physics digest names a tree; it is not evidence that the tree reproduces
B-prime. :func:`measure_bprime_reproduction` re-measures arms E, E' and O at B-prime's own
measurement seeds, through :func:`production_arm_cost` -- ``uplift.foresight.run_single_arm``
priced exactly as ``uplift/regret.py`` prices it -- and compares each arm's mean with the one
B-prime recorded, with ``==``. Exact, because the claim is "this environment executes B-prime's
physics", and a tolerance would admit a different physics whose mean happened to land near. A
non-reproduction is a recorded fact, not a refusal: E5 runs in the full closure (numpy 1.26.4)
and B-prime ran in the thin one (numpy 2.4.6), and numpy does not promise ``Generator`` streams
across versions, so what a claim may say about it is the main agent's call, not this module's.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from digital_twin.simulation.engine import SupplyChainSimulation
from digital_twin.simulation.monte_carlo import ShockParams
from digital_twin.simulation.policy import comparator_restock_threshold
from digital_twin.simulation.world import load_world
from uplift.consensus_arm import build_consensus_arm
from uplift.controls import SeedRange
from uplift.foresight import _cadence, run_single_arm, stocked_skus
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    LoopConfig,
    _derive_unit_costs,
    observe,
    replicate_seed,
)
from uplift.interfaces import ArmSpec, Scenario
from uplift.kpi import committed_objective
from uplift.oracle_arm import build_structure_aware_arm
from uplift.policies import NamedPolicy, UnavailableConsensusArm
from uplift.tuned_static import TUNED_STATIC_ARM, GroupParLevelReorder, sku_groups

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from collections.abc import Callable, Sequence

    from digital_twin.simulation.world import ResolvedWorld
    from uplift.bprime_record import BprimeRecord
    from uplift.interfaces import DecisionPolicy, Observation

__all__ = [
    "BPRIME_REPRODUCTION_KIND",
    "E5_COMPARATOR",
    "E5_CONSENSUS_LEVERS",
    "E5_HOURS",
    "E5_IN_SAMPLE_ARM",
    "E5_LOOP",
    "E5_PROBE_OBSERVE_AT_HOURS",
    "E5_PROBE_ORDER_EVERY_HOURS",
    "E5_PROBE_ORDER_UNITS",
    "E5_PROBE_TWIN_SEED",
    "E5_REPRODUCED_ARMS",
    "E5_SCENARIO_NAME",
    "E5_SCENARIO_SEED",
    "E5_SUITE",
    "REPRODUCED_ARMS",
    "ArmReproduction",
    "BprimeReproduction",
    "BprimeReproductionError",
    "ReproducedArm",
    "build_e5_arms",
    "e5_baseline_arms",
    "e5_consensus_policy",
    "e5_probe_observations",
    "e5_replicate_seeds",
    "e5_scenario",
    "e5_world",
    "measure_bprime_reproduction",
    "production_arm_cost",
    "read_bprime_reproduction",
    "write_bprime_reproduction",
]

#: The ``--suite`` value that selects this suite.
E5_SUITE: Final[str] = "e5-primary"

#: The scenario's name, as every record of the run keys it.
E5_SCENARIO_NAME: Final[str] = "e5_primary_unshocked"

#: The base seed every E5 replicate seed is derived from. ITS VALUE IS IMMATERIAL; ITS FIXITY IS
#: THE POINT. Chosen once, in the 5xxx block beside the adversarial suite's 4001-4004, it makes
#: the replicate seed set pre-registered and replayable, and :func:`e5_replicate_seeds` makes its
#: disjointness from B-prime's seeds a checked fact. Changing it re-draws every realisation, so a
#: run at another value is another experiment, not this one repeated.
E5_SCENARIO_SEED: Final[int] = 5001

#: The horizon B-prime tuned and measured arm E over (its ``hours_per_replicate``).
E5_HOURS: Final[float] = 24.0

_E5_SLICES, _E5_SLICE_HOURS = _cadence(E5_HOURS)

#: 24 h at regret's cadence -- ``uplift.foresight._cadence(24.0)``, read rather than restated, is
#: ``(24, 1.0)``: one decision per hour, 24 of them -- applying reorders only, as ``_drive_arm``
#: does. Property 97 pins ``n_steps`` and ``step_hours`` to ``_cadence``'s pair.
E5_LOOP: Final[LoopConfig] = LoopConfig(
    duration_hours=E5_HOURS,
    step_hours=_E5_SLICE_HOURS,
    levers="reorders_only",
)

#: The contrast's named comparator: arm E. ``GroupParLevelReorder``'s own name.
E5_COMPARATOR: Final[str] = TUNED_STATIC_ARM

#: Arm E-prime's arm name; a :class:`~uplift.policies.NamedPolicy` gives it, because the
#: policy's own name is arm E's and two arms with one name would share one record.
E5_IN_SAMPLE_ARM: Final[str] = "tuned_static_in_sample"

#: The levers the consensus arm may move in E5 (B2's ``build_consensus_arm(levers=...)``).
E5_CONSENSUS_LEVERS: Final[frozenset[str]] = frozenset({"reorder"})

#: An arm B-prime measured whose mean a reproduction compares: arm E (``tuned_static``), arm E'
#: (``tuned_static_in_sample``) and arm O (``structure_aware``) -- the names the B-prime artifact's
#: ``mean_<arm>_cost`` keys and every E5/E3 record use for them.
ReproducedArm = Literal["tuned_static", "tuned_static_in_sample", "structure_aware"]

#: Every :data:`ReproducedArm`, for runtime refusal: a ``Literal`` is not checked at run time.
REPRODUCED_ARMS: Final[tuple[ReproducedArm, ...]] = (
    "tuned_static",
    "tuned_static_in_sample",
    "structure_aware",
)

#: The arms the E5 CLI re-measures before its harness runs: arm E and arm E', the two baselines
#: E5 registers. Arm O is the positive control's (``uplift.controls_run``), not E5's.
E5_REPRODUCED_ARMS: Final[tuple[ReproducedArm, ...]] = ("tuned_static", "tuned_static_in_sample")

#: :class:`BprimeReproduction`'s declared kind.
BPRIME_REPRODUCTION_KIND: Final[Literal["bprime-reproduction"]] = "bprime-reproduction"

_SHA256_HEX: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")


def e5_world() -> ResolvedWorld:
    """The committed primary cell, resolved: the world B-prime tuned arm E in."""
    world = load_world()
    return world.resolve(world.primary_cell)


def e5_scenario() -> Scenario:
    """The E5 scenario: the primary world cell, the neutral shock, :data:`E5_SCENARIO_SEED`.

    Raises:
        PolicyUnavailableError: The committed world cannot be read or resolved.
    """
    return Scenario(
        name=E5_SCENARIO_NAME,
        seed=E5_SCENARIO_SEED,
        shock=ShockParams(),
        world=e5_world(),
    )


def e5_replicate_seeds(n: int, record: BprimeRecord) -> tuple[int, ...]:
    """The twin seeds of E5's first ``n`` replicates, refused if any collides with B-prime's.

    Exactly ``replicate_seed(E5_SCENARIO_SEED, i)`` for ``i < n`` -- the seeds
    ``UpliftHarness.run`` derives for :func:`e5_scenario` -- returned in replicate order.

    Raises:
        ValueError: ``n`` is not a positive ``int``; two replicates derive one seed (one
            realisation would count twice); or a seed is one of ``record``'s tuning seeds or
            lies in its measurement range -- naming each colliding seed and its clause.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError(f"an E5 run needs a positive replicate count, got {n!r}")
    seeds = tuple(replicate_seed(E5_SCENARIO_SEED, index) for index in range(n))
    if len(set(seeds)) != n:
        raise ValueError(
            f"two of E5's first {n} replicates derive one twin seed from base seed "
            f"{E5_SCENARIO_SEED}; one realisation would be counted as two replicates"
        )
    tuning = set(record.tuning_seeds)
    measured = range(record.measurement_seeds.start, record.measurement_seeds.stop)
    on_tuning = sorted(seed for seed in seeds if seed in tuning)
    on_measurement = sorted(seed for seed in seeds if seed in measured)
    if on_tuning or on_measurement:
        raise ValueError(
            f"E5 replicate seeds collide with B-prime's: on its tuning seeds {on_tuning[:5]} "
            "(arm E's levels would be in-sample there), on its measurement seeds "
            f"{on_measurement[:5]} ({record.measurement_seeds.describe()}; B-prime's split was "
            "measured on those realisations). E5 must run on seeds disjoint from both"
        )
    return seeds


def e5_consensus_policy() -> DecisionPolicy:
    """The consensus arm, moving reorders only -- or the honest stand-in when it cannot stand up.

    Any assembly failure is surfaced as :class:`~uplift.policies.UnavailableConsensusArm`, whose
    every decision fails, so each consensus run is recorded failed and the contrast incomplete:
    the canonical suite's degradation (R1.5, R2.7), never a fabricated decision.
    """
    try:
        return build_consensus_arm(levers=E5_CONSENSUS_LEVERS)
    except Exception as exc:  # noqa: BLE001 — any assembly failure => honest stand-in
        return UnavailableConsensusArm(
            f"consensus arm unavailable in this environment: {type(exc).__name__}: {exc}"
        )


def e5_baseline_arms(record: BprimeRecord) -> tuple[ArmSpec, ArmSpec]:
    """Arms E and E', as B-prime tuned them, each declaring role ``baseline``.

    ``sku_group`` is ``uplift.tuned_static.sku_groups`` over the primary world's stocked SKUs,
    exactly as ``uplift/regret.py::_measure`` derives it (``stocked_skus(0, world=...)``). The
    rule draws nothing, so its construction seed is :data:`E5_SCENARIO_SEED` and affects no
    decision.

    Raises:
        ValueError: The record describes another cell or another horizon than E5 runs, so its
            levels were tuned for a different experiment.
        PolicyUnavailableError: The committed world cannot be read or resolved.
        TuningUnavailableError: A stocked SKU has no supplier group (``sku_groups``).
    """
    world = e5_world()
    if record.cell != world.cell:
        raise ValueError(
            f"the B-prime record tuned arm E in cell {record.cell!r} but E5 runs the primary "
            f"cell {world.cell!r}; levels tuned for another world are not arm E here"
        )
    if record.hours_per_replicate != E5_HOURS:
        raise ValueError(
            f"the B-prime record tuned arm E over {record.hours_per_replicate!r} h replicates "
            f"but E5 runs {E5_HOURS!r} h; levels tuned for another horizon are not arm E here"
        )
    groups = sku_groups(world, stocked_skus(0, world=world))
    arm_e = GroupParLevelReorder(record.arm_e_levels(), groups, seed=E5_SCENARIO_SEED)
    arm_e_prime = NamedPolicy(
        GroupParLevelReorder(record.arm_e_prime_levels(), groups, seed=E5_SCENARIO_SEED),
        E5_IN_SAMPLE_ARM,
    )
    return ArmSpec(arm_e, "baseline"), ArmSpec(arm_e_prime, "baseline")


def build_e5_arms(record: BprimeRecord) -> tuple[ArmSpec, ...]:
    """E5's three arms, in order: ``consensus``, ``tuned_static`` (E), ``tuned_static_in_sample``.

    The consensus arm declares role ``consensus`` and is named
    :data:`~uplift.harness.DEFAULT_CONSENSUS_ARM`; arms E and E' are :func:`e5_baseline_arms`.

    Raises:
        As :func:`e5_baseline_arms`; the consensus arm's own failure degrades, never raises.
    """
    consensus = e5_consensus_policy()
    if consensus.name != DEFAULT_CONSENSUS_ARM:
        raise ValueError(
            f"the consensus arm is named {consensus.name!r}, not {DEFAULT_CONSENSUS_ARM!r}; "
            "result assembly identifies the subject by that name"
        )
    return (ArmSpec(consensus, "consensus"), *e5_baseline_arms(record))


# ---------------------------------------------------------------------------
# R7.21's probe states (finding 109): the one production sampler
# ---------------------------------------------------------------------------
#: The twin seed the probe's states are drawn at. Fixed, and immaterial beyond being fixed: the
#: probe is not a measurement replicate.
E5_PROBE_TWIN_SEED: Final[int] = 296

#: Orders every three hours keep stock in transit (supplier means 4/6/8 h, policy.yaml) while
#: earlier orders land, so the observations carry on-order stock AND realised lead times.
E5_PROBE_ORDER_EVERY_HOURS: Final[int] = 3

#: The units of every SKU each of those orders places.
E5_PROBE_ORDER_UNITS: Final[float] = 25.0

#: The simulated hours the twin is observed at, each before that hour's order is placed.
E5_PROBE_OBSERVE_AT_HOURS: Final[tuple[int, ...]] = (10, 12, 14)


def e5_probe_observations() -> list[Observation]:
    """The states R7.21's pathway probe decides: one primary-cell twin run, observed three times.

    The ONE production sampler (G2), moved from the slow probe test: the E5 CLI's probe step and
    that test both call it. The twin is built in :func:`e5_world` at :data:`E5_PROBE_TWIN_SEED`,
    started, and given the committed restock threshold. Then, for each simulated hour from 0:
    the twin is observed through ``uplift.harness.observe`` (the one construction of what a
    policy sees) if the hour is in :data:`E5_PROBE_OBSERVE_AT_HOURS`; every
    :data:`E5_PROBE_ORDER_EVERY_HOURS` hours it orders :data:`E5_PROBE_ORDER_UNITS` of every
    SKU; and it advances one hour. The states are returned in the order they were observed.

    Drives the real twin for 15 simulated hours: a CI workload, never a fast test's.

    Raises:
        PolicyUnavailableError: The committed world or restock threshold cannot be read.
    """
    sim = SupplyChainSimulation(seed=E5_PROBE_TWIN_SEED, world=e5_world())
    sim.start()
    sim.set_policy(restock_threshold=comparator_restock_threshold())
    unit_costs = _derive_unit_costs()
    observations: list[Observation] = []
    for hour in range(max(E5_PROBE_OBSERVE_AT_HOURS) + 1):
        if hour in E5_PROBE_OBSERVE_AT_HOURS:
            observations.append(observe(sim, unit_costs=unit_costs))
        if hour % E5_PROBE_ORDER_EVERY_HOURS == 0:
            for sku in sorted(sim.inventory):
                sim.place_order(sku, E5_PROBE_ORDER_UNITS)
        sim.advance(1.0)
    return observations


# ---------------------------------------------------------------------------
# The reproduction of B-prime's comparator (API2 amendment 2)
# ---------------------------------------------------------------------------
class BprimeReproductionError(ValueError):
    """A reproduction that cannot be stated: refused, never given a substituted mean."""


class ArmReproduction(BaseModel):
    """One arm re-measured at B-prime's measurement seeds, beside the mean B-prime recorded.

    ``reproduces`` is RE-DERIVED, never trusted: construction refuses any value other than
    ``measured_mean == recorded_mean``, compared exactly. Both means are finite, and
    ``replicates`` counts the costs ``measured_mean`` aggregates.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    arm: ReproducedArm
    replicates: int = Field(strict=True, ge=1)
    recorded_mean: float
    measured_mean: float
    reproduces: StrictBool

    @model_validator(mode="after")
    def _reproduces_is_derived(self) -> ArmReproduction:
        derived = self.measured_mean == self.recorded_mean
        if self.reproduces != derived:
            relation = "==" if derived else "!="
            raise ValueError(
                f"{self.arm}: reproduces={self.reproduces} contradicts measured_mean "
                f"{self.measured_mean!r} {relation} recorded_mean {self.recorded_mean!r}; the "
                "flag is derived from the two means, never asserted beside them"
            )
        return self


class BprimeReproduction(BaseModel):
    """B-prime's comparator re-measured in this environment, arm by arm (API2 amendment 2).

    ``seeds`` is the B-prime record's measurement range, and every arm was re-measured at each
    of its seeds; ``arms`` is in the order requested, each arm at most once. Written in the
    repository's one canonical JSON form; :attr:`all_reproduce` is derived, never recorded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["bprime-reproduction"]
    bprime_artifact_sha256: str
    seeds: SeedRange
    arms: tuple[ArmReproduction, ...]

    @field_validator("bprime_artifact_sha256")
    @classmethod
    def _artifact_digest(cls, value: str) -> str:
        if _SHA256_HEX.fullmatch(value) is None:
            raise ValueError(f"bprime_artifact_sha256 {value!r} is not 64 lowercase hex digits")
        return value

    @model_validator(mode="after")
    def _one_measurement_per_arm(self) -> BprimeReproduction:
        names = [arm.arm for arm in self.arms]
        if not names:
            raise ValueError("a reproduction of no arm reproduces nothing")
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(f"arm(s) {repeated} are recorded more than once")
        short = [arm.arm for arm in self.arms if arm.replicates != self.seeds.count]
        if short:
            raise ValueError(
                f"arm(s) {short} were not re-measured at every one of the "
                f"{self.seeds.count} seeds ({self.seeds.describe()})"
            )
        return self

    @property
    def all_reproduce(self) -> bool:
        """Whether every arm's re-measured mean equals the one B-prime recorded, exactly."""
        return all(arm.reproduces for arm in self.arms)

    def to_canonical_json(self) -> str:
        """The reproduction in the repository's one canonical JSON form."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def write_bprime_reproduction(path: Path, reproduction: BprimeReproduction) -> Path:
    """Write ``reproduction``'s canonical JSON to ``path`` (no trailing newline); return it."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(reproduction.to_canonical_json(), encoding="utf-8")
    return target


def read_bprime_reproduction(path: Path) -> BprimeReproduction:
    """Read a reproduction :func:`write_bprime_reproduction` wrote, re-deriving every check."""
    return BprimeReproduction.model_validate_json(Path(path).read_text(encoding="utf-8"))


def production_arm_cost(seed: int, policy: DecisionPolicy, world: ResolvedWorld) -> float:
    """One replicate of ``policy`` at twin ``seed``, priced exactly as ``uplift/regret.py`` does.

    The physics is ``uplift.foresight.run_single_arm`` at 24 h and the committed restock
    threshold: ``_new_arm_engine`` then ``_drive_arm``, the one construction and the one driver
    every comparator arm runs through, so an arm is measured here as B-prime measured it. The
    price is :func:`~uplift.kpi.committed_objective`'s ``cost`` over EXACTLY the five engine
    reads ``uplift/regret.py::_measure._observation`` makes (lines 1143-1154 when this was
    written): ``stockout_rate``, ``spoilage_rate``, ``fill_rate``,
    ``avg_on_hand_units(sim.sim_time_min)`` and ``avg_delivery_time_min``, unclamped.

    Drives the real twin for 24 simulated hours: a CI workload, never a fast test's.
    """
    sim = run_single_arm(
        seed,
        hours=E5_HOURS,
        restock_threshold=comparator_restock_threshold(),
        policy=policy,
        world=world,
    )
    metrics = sim.metrics
    return committed_objective().cost(
        stockout_rate=metrics.stockout_rate,
        spoilage_rate=metrics.spoilage_rate,
        fill_rate=metrics.fill_rate,
        avg_on_hand_units=metrics.avg_on_hand_units(sim.sim_time_min),
        avg_delivery_time_min=metrics.avg_delivery_time_min,
    )


def _structure_aware_arm(world: ResolvedWorld, seed: int) -> DecisionPolicy:
    """Arm O at ``seed``, built as ``uplift/foresight.py::run_three_pass`` builds it.

    ``run_three_pass`` (lines 788-798 when this was written) passes ``hours``,
    ``review_min=slice_hours * 60.0`` with ``slice_hours`` from ``_cadence(hours)`` (line 668),
    and ``n_skus=len(structure_aware_sim.inventory)``, read from the arm's own started engine.
    ``stocked_skus(seed, world=world)`` starts an engine at the same seed in the same world and
    reads the same catalogue: ``set_policy``, the only call between that engine's ``start()``
    and the read, moves no SKU.
    """
    return build_structure_aware_arm(
        world,
        seed=seed,
        hours=E5_HOURS,
        review_min=_E5_SLICE_HOURS * 60.0,
        n_skus=len(stocked_skus(seed, world=world)),
    )


def _requested_arms(arms: Sequence[ReproducedArm]) -> tuple[ReproducedArm, ...]:
    """``arms`` in the order given, or a refusal -- before any arm is priced."""
    requested = tuple(arms)
    if not requested:
        raise BprimeReproductionError("no arm was requested, so nothing would be re-measured")
    unknown = sorted({str(arm) for arm in requested if arm not in REPRODUCED_ARMS})
    if unknown:
        raise BprimeReproductionError(
            f"arm(s) {unknown} were not measured by B-prime (it measured {list(REPRODUCED_ARMS)})"
        )
    repeated = sorted({arm for arm in requested if requested.count(arm) > 1})
    if repeated:
        raise BprimeReproductionError(
            f"arm(s) {repeated} are requested more than once; each arm is re-measured once"
        )
    return requested


def _recorded_mean(record: BprimeRecord, arm: ReproducedArm) -> float:
    """The mean B-prime recorded for ``arm``, read from the artifact key of the same name."""
    recorded = {
        "tuned_static": record.mean_tuned_static_cost,
        "tuned_static_in_sample": record.mean_in_sample_tuned_static_cost,
        "structure_aware": record.mean_structure_aware_cost,
    }
    return recorded[arm]


def measure_bprime_reproduction(
    record: BprimeRecord,
    arms: Sequence[ReproducedArm],
    *,
    cost_of: Callable[[int, DecisionPolicy, ResolvedWorld], float],
) -> BprimeReproduction:
    """Re-measure ``arms`` at ``record``'s measurement seeds; compare each mean with B-prime's.

    Each arm is priced by ``cost_of(seed, policy, world)`` at every seed of
    ``record.measurement_seeds``, in order, in the primary world (:func:`e5_world`), and its mean
    is ``committed_objective().aggregate`` of those costs, the rule ``uplift/regret.py`` applies
    to the costs it recorded. Arms E and E' are :func:`e5_baseline_arms`' policies, the record's
    levels exactly as :func:`build_e5_arms` builds them: ``GroupParLevelReorder`` draws nothing
    and keeps no state between decisions, so one instance serves every seed. Arm O is built PER
    SEED, as ``run_three_pass`` builds it. ``cost_of`` is REQUIRED: production passes
    :func:`production_arm_cost`, and a fast test injects a cost so that no twin runs.

    Raises:
        BprimeReproductionError: ``arms`` is empty, names an arm twice or one B-prime did not
            measure -- each refused before ``cost_of`` is called -- or a cost is not finite, so
            no mean exists to compare and none is substituted.
        ValueError: As :func:`e5_baseline_arms`: the record is for another cell or horizon.
        PolicyUnavailableError: The committed world or objective cannot be read.
    """
    requested = _requested_arms(arms)
    world = e5_world()
    arm_e, arm_e_prime = e5_baseline_arms(record)
    fixed: dict[ReproducedArm, DecisionPolicy] = {
        "tuned_static": arm_e.policy,
        "tuned_static_in_sample": arm_e_prime.policy,
    }
    objective = committed_objective()
    seeds = range(record.measurement_seeds.start, record.measurement_seeds.stop)
    measured: list[ArmReproduction] = []
    for arm in requested:
        costs: list[float] = []
        for seed in seeds:
            policy = _structure_aware_arm(world, seed) if arm == "structure_aware" else fixed[arm]
            cost = cost_of(seed, policy, world)
            if not math.isfinite(cost):
                raise BprimeReproductionError(
                    f"{arm} costs {cost!r} at seed {seed}; a mean over a non-finite cost is no "
                    "mean, so the reproduction cannot be stated"
                )
            costs.append(cost)
        mean = objective.aggregate(costs)
        recorded = _recorded_mean(record, arm)
        measured.append(
            ArmReproduction(
                arm=arm,
                replicates=len(costs),
                recorded_mean=recorded,
                measured_mean=mean,
                reproduces=mean == recorded,
            )
        )
    return BprimeReproduction(
        kind=BPRIME_REPRODUCTION_KIND,
        bprime_artifact_sha256=record.artifact_sha256,
        seeds=record.measurement_seeds,
        arms=tuple(measured),
    )
