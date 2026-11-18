"""The E5 miniature: E5's own cost function on its first replicate seeds, priced in parallel.

Each task prices one 24-hour replicate of one arm at one seed with
``uplift.e5_suite.production_arm_cost``, building the arm afresh as truth session 2's
``mini_e5.py`` did, so the pinned costs are the costs that instrument printed (truth LOG M-23).
Workers are separate processes (the twin and the eight agents are CPU-bound Python); on Windows
they start by importing this module, so nothing heavy runs at import time.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The per-process context a worker builds once: E5's suite module, the B-prime record and the
#: resolved primary world.
_CONTEXT: dict[str, Any] = {}

CONSENSUS: Final[str] = "consensus"
TUNED: Final[str] = "tuned"


def _silence_logging() -> None:
    """Keep the agents' structured logs off the console: the verdict prints its own report."""
    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )
    logging.disable(logging.CRITICAL)


def init_worker(root: str) -> None:
    """Process-pool initializer: import E5's suite and read the B-prime record once."""
    _silence_logging()
    from uplift import e5_suite
    from uplift.bprime_record import read_bprime_record

    _CONTEXT["suite"] = e5_suite
    _CONTEXT["record"] = read_bprime_record(Path(root))
    _CONTEXT["world"] = e5_suite.e5_world()


def price(task: tuple[int, str, int]) -> tuple[int, str, int, float]:
    """Price one replicate: ``(seed, arm, run)`` to ``(seed, arm, run, cost)``.

    Raises:
        RuntimeError: The consensus arm could not be assembled in this environment (E5's suite
            returns an honest stand-in whose every decision fails; pricing it would not measure
            the consensus).
    """
    seed, arm, run = task
    suite = _CONTEXT["suite"]
    if arm == CONSENSUS:
        policy = suite.e5_consensus_policy()
        from uplift.policies import UnavailableConsensusArm

        if isinstance(policy, UnavailableConsensusArm):
            raise RuntimeError(f"consensus arm unavailable: {policy!r}")
    elif arm == TUNED:
        policy = suite.e5_baseline_arms(_CONTEXT["record"])[0].policy
    else:
        raise ValueError(f"unknown arm {arm!r}")
    return seed, arm, run, float(suite.production_arm_cost(seed, policy, _CONTEXT["world"]))


def price_many(tasks: Sequence[tuple[int, str, int]]) -> list[tuple[int, str, int, float | str]]:
    """Price ``tasks`` in order in this process; a failed task yields its error text, not a cost.

    One call per process keeps every replicate after the first free of the agent stack's import,
    which costs about 12 s per process on the laptop (measured, truth session 3).
    """
    results: list[tuple[int, str, int, float | str]] = []
    for task in tasks:
        try:
            results.append(price(task))
        except Exception as exc:  # noqa: BLE001 -- reported by the caller, never hidden
            results.append((task[0], task[1], task[2], f"{type(exc).__name__}: {exc}"))
    return results


def replicate_seeds(root: Path, count: int) -> Sequence[int]:
    """E5's first ``count`` replicate seeds, exactly as E5 derives them."""
    from uplift import e5_suite
    from uplift.bprime_record import read_bprime_record

    return tuple(e5_suite.e5_replicate_seeds(count, read_bprime_record(root)))
