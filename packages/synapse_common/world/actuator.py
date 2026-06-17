"""Sync world-actuation client (ADR-052): an agent's execute() mutates the world.

Agents run in their own processes, so ``execute()`` reaches the twin's standing world
over HTTP A2A (``apply_action``). The agent handlers are synchronous, so this is a small
synchronous client (``httpx.Client``) — the mirror of the async ``A2AWorldClient`` the
SensorLoop uses to perceive.

Honest by construction (I-7): every failure path returns ``{"applied": False, ...}`` and
logs; it never raises, so a slow/absent world degrades the actuation instead of crashing
the agent or fabricating a success.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    from synapse_common.world.models import WorldAction

logger = structlog.get_logger(__name__)

TWIN_ENDPOINT = os.environ.get("SYNAPSE_TWIN_ENDPOINT", "http://digital-twin:8009")


@runtime_checkable
class Actuator(Protocol):
    """Anything that can apply a WorldAction (real client or a test fake)."""

    def apply(self, action: WorldAction) -> dict[str, Any]: ...


class WorldActuator:
    """Production actuator — POSTs ``apply_action`` to the twin's standing world."""

    def __init__(self, twin_url: str = TWIN_ENDPOINT, timeout: float = 5.0) -> None:
        self._url = twin_url.rstrip("/")
        self._timeout = timeout

    def apply(self, action: WorldAction) -> dict[str, Any]:
        rpc = {
            "jsonrpc": "2.0",
            "id": action.action_id,
            "method": "apply_action",
            "params": json.loads(action.to_deterministic_json()),
        }
        try:
            import httpx

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(f"{self._url}/a2a", json=rpc)
                resp.raise_for_status()
                body: dict[str, Any] = resp.json()
        except Exception as exc:  # noqa: BLE001 — actuation degrades honestly, never raises (I-7)
            logger.warning("world_actuation_failed", kind=action.kind.value, error=str(exc))
            return {"applied": False, "error": str(exc)}
        if isinstance(body, dict) and body.get("error"):
            return {"applied": False, "error": body["error"]}
        result = body.get("result") if isinstance(body, dict) else None
        return {"applied": True, "result": result or {}}
