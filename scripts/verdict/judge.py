"""The verdict's judgment: pure functions from measurements to one outcome.

No I/O and no import of the decision stack, so every rule here is unit-tested directly
(``tests/verdict/test_judge.py``). Costs are compared exactly: the proof is deterministic and
repeats to the last bit (truth LOG M-23), so any difference is a real change in decisions,
physics or prices, never noise.
"""

from __future__ import annotations

import dataclasses
import enum
import math
import statistics
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class Outcome(enum.IntEnum):
    """The verdict's outcomes; each value is the command's exit code."""

    PASS = 0
    """Safety tests pass; every pinned cost reproduces to the bit; the repeats are identical."""
    SAFETY = 1
    """A safety test shard failed (any non-zero pytest exit, including "no tests collected")."""
    WORSE = 2
    """The consensus arm's decisions changed and its mean cost on the pinned seeds rose."""
    CHANGED = 3
    """The consensus arm's decisions changed and its mean cost did not rise: re-pin to accept."""
    NONDETERMINISTIC = 4
    """A seed priced twice gave two different costs."""
    CONTROL_MOVED = 5
    """The tuned control's cost changed: the physics, the prices or the control moved."""
    REFUSED_ENV = 6
    """A ``TW_`` environment variable is set, which silently changes the twin (finding F-33)."""
    INCOMPLETE = 7
    """A measurement could not be taken (an arm failed, or the pins name other seeds)."""
    KERNEL_DIVERGED = 8
    """The kernel's port of the decision core (``synapse_kernel.policies.sentinel``) no longer
    costs what the consensus pins say: the browser would show other decisions than SYNAPSE's."""


#: Which outcome wins when several apply, most severe first. A refusal or a missing measurement
#: says nothing about the code; a failed safety test outranks every quality signal; a
#: nondeterminism makes every cost comparison meaningless; a moved control makes the consensus
#: arm's change uninterpretable as a decision change. A kernel divergence ranks after a change of
#: the consensus arm: a change to the agents still reads as WORSE or CHANGED, and once its pins are
#: re-written the port must move with it, or this outcome remains.
PRIORITY: Final[tuple[Outcome, ...]] = (
    Outcome.REFUSED_ENV,
    Outcome.INCOMPLETE,
    Outcome.SAFETY,
    Outcome.NONDETERMINISTIC,
    Outcome.CONTROL_MOVED,
    Outcome.WORSE,
    Outcome.CHANGED,
    Outcome.KERNEL_DIVERGED,
    Outcome.PASS,
)

ARMS: Final[tuple[str, ...]] = ("consensus", "tuned")


@dataclasses.dataclass(frozen=True)
class Pins:
    """The committed costs: per arm, per seed, exactly (stored as ``float.hex``)."""

    seeds: tuple[int, ...]
    costs: Mapping[str, Mapping[int, float]]


@dataclasses.dataclass(frozen=True)
class Measurement:
    """What one verdict run measured."""

    costs: Mapping[str, Mapping[int, float]]
    """Per arm, per seed: the first pricing of every pinned seed."""
    repeats: Mapping[str, Mapping[int, float]]
    """Per arm, per seed: a second, independent pricing of some seeds."""
    shard_exit_codes: Mapping[str, int]
    """Per safety shard: the pytest exit code."""
    failures: Sequence[str] = ()
    """Measurements that could not be taken, each described."""
    physics_moved: Sequence[str] = ()
    """Refusals by the proof's own records because the physics they describe changed (the
    B-prime record's physics digest): the control and the physics moved, so nothing was priced."""
    kernel: Mapping[int, float] = dataclasses.field(default_factory=dict)
    """Per seed: the kernel's Sentinel alone priced on the kernel's legacy world. It reads no legacy
    physics, so it is priced whatever the legacy twin does; a pinned seed missing here is a gap."""


@dataclasses.dataclass(frozen=True)
class Delta:
    """How one arm's costs moved against its pins."""

    arm: str
    changed_seeds: tuple[int, ...]
    mean_delta: float
    """Mean of (measured - pinned) over every pinned seed; positive means dearer."""
    worse_seeds: int
    better_seeds: int
    standard_error: float | None
    """Standard error of that mean over seeds; ``None`` with fewer than two seeds."""


@dataclasses.dataclass(frozen=True)
class Verdict:
    """The outcome, every finding behind it, and the arms' movements."""

    outcome: Outcome
    findings: tuple[str, ...]
    deltas: Mapping[str, Delta]


def arm_delta(arm: str, pinned: Mapping[int, float], measured: Mapping[int, float]) -> Delta:
    """Compare ``measured`` with ``pinned`` over the pinned seeds, exactly.

    Raises:
        KeyError: A pinned seed was not measured (the caller reports it as incomplete first).
    """
    seeds = sorted(pinned)
    deltas = [measured[seed] - pinned[seed] for seed in seeds]
    changed = tuple(seed for seed in seeds if measured[seed] != pinned[seed])
    error = statistics.stdev(deltas) / math.sqrt(len(deltas)) if len(deltas) > 1 else None
    return Delta(
        arm=arm,
        changed_seeds=changed,
        mean_delta=statistics.fmean(deltas) if deltas else 0.0,
        worse_seeds=sum(delta > 0 for delta in deltas),
        better_seeds=sum(delta < 0 for delta in deltas),
        standard_error=error,
    )


def judge(pins: Pins, measurement: Measurement) -> Verdict:
    """The single outcome for ``measurement`` against ``pins``, with every finding that applies."""
    found: dict[Outcome, list[str]] = {}

    def note(outcome: Outcome, text: str) -> None:
        found.setdefault(outcome, []).append(text)

    for failure in measurement.failures:
        note(Outcome.INCOMPLETE, failure)
    for reason in measurement.physics_moved:
        note(Outcome.CONTROL_MOVED, f"the proof's record refuses this tree: {reason}")
    for arm in ARMS if not measurement.physics_moved else ():
        missing = [seed for seed in pins.seeds if seed not in measurement.costs.get(arm, {})]
        if missing:
            note(
                Outcome.INCOMPLETE,
                f"{arm}: {len(missing)} pinned seed(s) not measured {missing[:3]}",
            )
    unpriced = [seed for seed in pins.seeds if seed not in measurement.kernel]
    if unpriced:
        note(
            Outcome.INCOMPLETE,
            f"kernel: {len(unpriced)} pinned seed(s) not priced by the Sentinel alone "
            f"{unpriced[:3]}",
        )
    else:
        diverged = [
            seed for seed in pins.seeds if measurement.kernel[seed] != pins.costs["consensus"][seed]
        ]
        if diverged:
            first = diverged[0]
            note(
                Outcome.KERNEL_DIVERGED,
                f"the kernel's Sentinel alone differs from the consensus pins on {len(diverged)} "
                f"of {len(pins.seeds)} seeds (first: seed {first}, pinned "
                f"{pins.costs['consensus'][first].hex()}, kernel "
                f"{measurement.kernel[first].hex()}): synapse_kernel/policies/sentinel.py must "
                "move with the agents",
            )
    for shard, code in sorted(measurement.shard_exit_codes.items()):
        if code != 0:
            note(Outcome.SAFETY, f"safety shard {shard!r} exited {code}")
    if not measurement.shard_exit_codes:
        note(Outcome.SAFETY, "no safety shard ran")
    for arm, seeds in sorted(measurement.repeats.items()):
        for seed, again in sorted(seeds.items()):
            first = measurement.costs.get(arm, {}).get(seed)
            if first is not None and first != again:
                note(
                    Outcome.NONDETERMINISTIC,
                    f"{arm} at seed {seed}: {first.hex()} then {again.hex()}",
                )
    deltas: dict[str, Delta] = {}
    if Outcome.INCOMPLETE not in found and not measurement.physics_moved:
        for arm in ARMS:
            pinned = {seed: pins.costs[arm][seed] for seed in pins.seeds}
            deltas[arm] = arm_delta(arm, pinned, measurement.costs[arm])
        tuned, consensus = deltas["tuned"], deltas["consensus"]
        if tuned.changed_seeds:
            note(
                Outcome.CONTROL_MOVED,
                f"tuned control moved on {len(tuned.changed_seeds)} of {len(pins.seeds)} seeds "
                f"(mean {tuned.mean_delta:+.6f}): the physics, the prices or the control changed",
            )
        if consensus.changed_seeds:
            target = Outcome.WORSE if consensus.mean_delta > 0 else Outcome.CHANGED
            note(
                target,
                f"consensus decisions changed on {len(consensus.changed_seeds)} of "
                f"{len(pins.seeds)} seeds: mean cost {consensus.mean_delta:+.6f} "
                f"(dearer on {consensus.worse_seeds}, cheaper on {consensus.better_seeds})",
            )
    outcome = next(o for o in PRIORITY if o in found or o is Outcome.PASS)
    findings = tuple(text for o in PRIORITY for text in found.get(o, []))
    return Verdict(outcome=outcome, findings=findings, deltas=deltas)


def kernel_reproduces(
    consensus: Mapping[int, float], kernel: Mapping[int, float], seeds: Sequence[int]
) -> bool:
    """Whether the kernel's port priced every seed exactly as the consensus arm was measured.

    ``--repin`` writes new consensus pins only when this holds, so a change to the agents and the
    port's matching change land together (or the re-pinned tree reads KERNEL_DIVERGED).
    """
    return bool(seeds) and all(
        seed in kernel and seed in consensus and kernel[seed] == consensus[seed] for seed in seeds
    )


def pins_to_document(pins: Pins, note: str) -> dict[str, object]:
    """The pins as the JSON document committed to the repository (floats as exact hex)."""
    return {
        "schema": 1,
        "note": note,
        "seeds": list(pins.seeds),
        "costs": {
            arm: {str(seed): pins.costs[arm][seed].hex() for seed in pins.seeds} for arm in ARMS
        },
    }


def pins_from_document(document: Mapping[str, object]) -> Pins:
    """The inverse of :func:`pins_to_document`.

    Raises:
        ValueError: The document is not schema 1, or an arm lacks a seed it names.
    """
    if document.get("schema") != 1:
        raise ValueError(f"verdict pins: unknown schema {document.get('schema')!r}")
    raw_seeds = document.get("seeds")
    raw_costs = document.get("costs")
    if not isinstance(raw_seeds, list) or not isinstance(raw_costs, dict):
        raise ValueError("verdict pins: 'seeds' must be a list and 'costs' a mapping")
    seeds = tuple(int(seed) for seed in raw_seeds)
    costs: dict[str, dict[int, float]] = {}
    for arm in ARMS:
        table = raw_costs.get(arm)
        if not isinstance(table, dict) or sorted(table) != sorted(str(s) for s in seeds):
            raise ValueError(f"verdict pins: arm {arm!r} does not pin exactly the listed seeds")
        costs[arm] = {int(seed): float.fromhex(value) for seed, value in table.items()}
    return Pins(seeds=seeds, costs=costs)
