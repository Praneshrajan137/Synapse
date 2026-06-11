"""Orchestrator posture computation tests (ADR-044 D4).

``GET /api/v1/status/posture`` (serve.py) delegates to
``orchestrator.inference.posture.compute_posture`` — a pure read of two
in-process registries, import-light so it tests without the consensus
stack (pymoo) and stays cheap enough for the frontend's 15s poll.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
from synapse_common.breakers import get_breaker, reset_registry

from orchestrator.consensus.brownout import (
    BrownoutController,
    clear_registry,
    register,
    registered_controllers,
)
from orchestrator.inference.posture import compute_posture


@pytest.fixture(autouse=True)
def _clean_registries() -> Iterator[None]:
    clear_registry()
    reset_registry()
    yield
    clear_registry()
    reset_registry()


def test_empty_registries_report_healthy() -> None:
    posture = compute_posture()
    assert posture == {"brownout": {}, "breakers": {}, "degraded": False}


def test_healthy_posture_with_registered_controllers() -> None:
    register(BrownoutController("bengaluru"))
    register(BrownoutController("mumbai"))
    get_breaker("ollama")
    posture = compute_posture()
    assert posture["brownout"] == {"bengaluru": "NONE", "mumbai": "NONE"}
    assert posture["breakers"] == {"ollama": "closed"}
    assert posture["degraded"] is False


def test_manual_brownout_override_reports_degraded() -> None:
    controller = BrownoutController("bengaluru")
    from orchestrator.consensus.brownout import BrownoutLevel

    controller.set_manual_override(BrownoutLevel.SHED_T4)
    register(controller)
    posture = compute_posture()
    assert posture["brownout"]["bengaluru"] == "SHED_T4"
    assert posture["degraded"] is True


@pytest.mark.asyncio
async def test_open_breaker_reports_degraded() -> None:
    breaker = get_breaker("postgres", fail_max=1)
    # Trip it: one recorded failure opens a fail_max=1 breaker.
    try:
        async with breaker.guard():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    posture = compute_posture()
    assert posture["breakers"]["postgres"] == "open"
    assert posture["degraded"] is True


def test_registered_controllers_returns_copy() -> None:
    register(BrownoutController("bengaluru"))
    snapshot = registered_controllers()
    snapshot.clear()
    assert registered_controllers(), "mutating the snapshot must not touch the registry"
