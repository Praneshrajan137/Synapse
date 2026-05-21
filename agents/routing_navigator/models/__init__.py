"""SYNAPSE Routing Navigator — model components.

Pure-Python CVRPTW solver is eagerly importable. Torch-based encoder/decoder/
student models are lazy so callers that only need the deterministic solver
do not pay the torch import cost.
"""

from agents.routing_navigator.models.cvrptw import (
    Route,
    Stop,
    haversine_km,
    solve_cvrptw,
)


def __getattr__(name: str) -> object:  # pragma: no cover — lazy import shim
    if name in {"PointerDecoder", "RouteEncoder", "DistilledStudent"}:
        from importlib import import_module

        modmap = {
            "PointerDecoder": "decoder",
            "RouteEncoder": "encoder",
            "DistilledStudent": "student",
        }
        return getattr(
            import_module(f"agents.routing_navigator.models.{modmap[name]}"),
            name,
        )
    raise AttributeError(name)


__all__ = [
    "DistilledStudent",
    "PointerDecoder",
    "Route",
    "RouteEncoder",
    "Stop",
    "haversine_km",
    "solve_cvrptw",
]
