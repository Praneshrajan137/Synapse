"""Every policy a comparison may build, by name, from the same inputs whatever the cell.

A comparison names a component and a world; it never names a cell, because nothing a policy is built
from may depend on one (PREREG-1 section 1). :func:`build` is the one constructor the isolation
harness calls in the challenger's process; :func:`names` lists what it can build. ``params`` holds a
component's fitted numbers (the surge threshold, factor tables), read from a committed file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from synapse_kernel.challengers.guarded import Guarded
from synapse_kernel.challengers.sentinel_release import SentinelAsBuilt, SentinelForThisWorld
from synapse_kernel.challengers.shelf import LaneIncumbent, LaneSensing
from synapse_kernel.challengers.supply import SupplyResponse
from synapse_kernel.challengers.surge import SurgeCalibration, SurgeResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synapse_kernel.release.engine import ReleasePolicy
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["build", "names"]

_NAMES = (
    "lane_incumbent",
    "sensing",
    "surge_today",
    "surge_ahead",
    "supply",
    "sentinel_as_built",
    "sentinel_world",
    "surge_calibration",
    "synapse",
)


def names() -> tuple[str, ...]:
    """The components :func:`build` knows."""
    return _NAMES


def _table(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    return None if value is None else np.asarray(value, dtype=np.float64)


def build(
    name: str,
    world: ReleaseWorld,
    tables: Mapping[str, IncumbentTables],
    params: Mapping[str, Any],
) -> ReleasePolicy:
    """The policy ``name``, built from cell N's declared world, the tables and its parameters;
    behind the D-4(b) guard around the lane incumbent if ``params["guard"]`` is true.

    Raises:
        ValueError: An unknown name, or a component built without the parameter it needs.
    """
    policy = _build(name, world, tables, params)
    if params.get("guard") is True:
        reporting = (
            SurgeCalibration,
            SurgeResponse,
            SupplyResponse,
        )  # the composition guards itself
        report = policy.report if isinstance(policy, reporting) else None
        return Guarded(policy, world, tables["I2-P"], tables["I2-L"], name, report)
    return policy


def _build(
    name: str,
    world: ReleaseWorld,
    tables: Mapping[str, IncumbentTables],
    params: Mapping[str, Any],
) -> ReleasePolicy:
    normal, short = tables["I2-P"], tables["I2-L"]
    if name == "lane_incumbent":
        return LaneIncumbent(world, normal, short)
    if name == "sensing":
        return LaneSensing(world, normal, short)
    if name in ("surge_today", "surge_ahead"):
        if "surge_threshold" not in params:
            raise ValueError("the surge component needs its fitted threshold")
        plan = name.removeprefix("surge_")
        return SurgeResponse(
            world,
            normal,
            short,
            float(params["surge_threshold"]),
            _table(params, f"{name}_kappa"),
            plan,
        )
    if name == "supply":
        return SupplyResponse(world, normal, short, _table(params, "supply_kappa"))
    if name == "sentinel_as_built":
        return SentinelAsBuilt(world)
    if name == "sentinel_world":
        return SentinelForThisWorld(world, normal)
    if name == "surge_calibration":
        return SurgeCalibration(world, normal, short)
    if name == "synapse":
        from synapse_kernel.challengers.composition import Composition

        return Composition(world, tables, params, _build)
    raise ValueError(f"unknown component {name!r}; known: {names()}")
