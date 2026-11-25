"""Compare a challenger on the frozen world with the challenger in a process of its own.

The harness (this process) holds the world, builds each replicate's scenario and runs the frozen
engine; the challenger answers in a child process (:mod:`scripts.challengers.child`) that sees only
observations, over a pipe. For every replicate (truth session 6, gate item 9):

* a **fresh child** per (world, cell, replicate, arm) in reported runs, so nothing a challenger saw
  in one replicate, such as seed ``j``'s demand in cell N, can reach seed ``j`` in another cell;
* the **outcome replay**: the orders the child gave, replayed through the frozen engine by a policy
  that only reads its log, must give the same outcome;
* the **decision replay** (``replay_decisions``): a second fresh child, fed the same observations,
  must give the same orders, which catches hidden state and nondeterminism;
* the child's **handshake** (spawn arguments, environment, request) is digested, so a test can show
  it is the same whatever the cell.

Windows starts child processes by re-importing the main module, so every script that calls into
here runs under ``if __name__ == "__main__":`` (E-TP-01).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING, Any

import numpy as np

from scripts.challengers import child
from synapse_kernel.release import integrity
from synapse_kernel.release.engine import run
from synapse_kernel.release.objective import fill_rate, item_costs, replicate_costs
from synapse_kernel.release.scenario import build_scenario

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synapse_kernel.release.engine import Outcome
    from synapse_kernel.release.observation import StoreObservation

I64 = np.ndarray
SPAWN = multiprocessing.get_context("spawn")


@dataclasses.dataclass(frozen=True)
class Spec:
    """What the child builds: a component, a world, its parameters. Never a cell."""

    component: str
    world: str = "W"
    params: str | None = None

    def to_bytes(self) -> bytes:
        return json.dumps(dataclasses.asdict(self), sort_keys=True, separators=(",", ":")).encode()


class ChildPolicy:
    """A :class:`~synapse_kernel.release.engine.ReleasePolicy` answered by a child process."""

    def __init__(self, spec: Spec) -> None:
        self.parent, child_end = SPAWN.Pipe()
        self.process = SPAWN.Process(target=child.serve, args=(child_end, spec.to_bytes()))
        self.process.start()
        kind, info = self.parent.recv()
        if kind != "ready":
            raise RuntimeError(f"the child did not start: {kind}")
        self.handshake: dict[str, str] = info
        self.observations: list[StoreObservation] = []
        self.orders: list[I64] = []

    def start(self, replicates: int) -> None:
        self.parent.send(("start", replicates))
        if self.parent.recv()[0] != "ok":
            raise RuntimeError("the child refused to start a replicate")

    def decide(self, obs: StoreObservation) -> I64:
        self.observations.append(obs)
        # The fields, not the object: pickling a frozen dataclass caches ``__slotnames__`` on its
        # class, which the freeze check rightly reports as a binding added after import.
        fields = {f.name: getattr(obs, f.name) for f in dataclasses.fields(obs)}
        self.parent.send(("decide", fields))
        kind, orders = self.parent.recv()
        if kind != "orders":
            raise RuntimeError(f"the child answered {kind}")
        self.orders.append(np.asarray(orders))
        return self.orders[-1]

    def report(self) -> dict[str, Any]:
        """The component's own summary of what it saw, as plain data."""
        self.parent.send(("report",))
        kind, summary = self.parent.recv()
        if kind != "report":
            raise RuntimeError(f"the child answered {kind}")
        out: dict[str, Any] = dict(summary)
        return out

    def close(self) -> None:
        try:
            self.parent.send(("stop",))
            kind, ok = self.parent.recv()
            if kind != "done" or not ok:
                raise RuntimeError("the child's closing freeze check failed")
        finally:
            self.process.join(timeout=30)
            if self.process.is_alive():
                self.process.kill()


class LoggedOrders:
    """A policy that only replays a log of orders: the outcome replay's challenger-free side."""

    def __init__(self, orders: Sequence[I64]) -> None:
        self.log = list(orders)
        self.calls = 0

    def start(self, replicates: int) -> None:
        self.calls = 0

    def decide(self, obs: StoreObservation) -> I64:
        out = self.log[self.calls]
        self.calls += 1
        return out


def _digest(arrays: Sequence[I64]) -> str:
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(a, dtype=np.int64).tobytes())
    return h.hexdigest()


def summarise(world: Any, outcome: Outcome) -> dict[str, Any]:
    """One replicate's priced outcome, as the analysis takes it (prices are per item)."""
    prices = [item.price for item in world.items]

    def priced(counts: I64) -> float:  # exactly rounded, the same bits on every platform
        return math.fsum(p * float(c) for p, c in zip(prices, counts.tolist(), strict=True))

    return {
        "cost": replicate_costs(world, outcome)[0],
        "fill": fill_rate(outcome)[0],
        "lost": priced(outcome.lost[0]),
        "wasted": priced(outcome.wasted[0]),
        "held": priced(outcome.holding2[0]) / 48.0,
        "end_on_hand": int(outcome.end_on_hand[0].sum()),
        "item_cost": item_costs(world, outcome)[0].tolist(),
    }


def run_one(spec: Spec, cell: str, seed: int, replay_decisions: bool = True) -> dict[str, Any]:
    """One replicate of ``cell`` at ``seed``, the challenger in a fresh child; both replays run."""
    world, _tables, _files = child.load(spec.world)
    integrity.assert_frozen()
    scenario = build_scenario(world, cell, seed)
    policy = ChildPolicy(spec)
    try:
        outcome = run(world, [scenario], policy)
        report = policy.report()
    finally:
        policy.close()
    replayed = run(world, [scenario], LoggedOrders(policy.orders))
    outcome_replay = all(
        np.array_equal(getattr(outcome, f.name), getattr(replayed, f.name))
        for f in dataclasses.fields(outcome)
    )
    decision_replay: bool | None = None
    if replay_decisions:
        again = ChildPolicy(spec)
        try:
            again.start(1)
            orders = [again.decide(obs) for obs in policy.observations]
            report_again = again.report()
        finally:
            again.close()
        # The orders and the component's own report (a fitted number may come from it) must both
        # be re-derived exactly by a fresh child fed the same observations.
        decision_replay = report_again == report and all(
            np.array_equal(a, b) for a, b in zip(orders, policy.orders, strict=True)
        )
    integrity.assert_frozen()
    return {
        "cell": cell,
        "seed": seed,
        **summarise(world, outcome),
        "orders_digest": _digest(policy.orders),
        "outcome_replay": outcome_replay,
        "decision_replay": decision_replay,
        "handshake": policy.handshake,
        "report": report,
    }


def run_many(
    spec: Spec, cell: str, seeds: Sequence[int], workers: int = 8, replay_decisions: bool = True
) -> list[dict[str, Any]]:
    """Every seed of ``cell``, each in its own harness worker and its own challenger child."""
    with ProcessPoolExecutor(max_workers=workers, mp_context=SPAWN) as pool:
        futures = [pool.submit(run_one, spec, cell, seed, replay_decisions) for seed in seeds]
        return [f.result() for f in futures]
