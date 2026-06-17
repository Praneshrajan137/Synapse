"""Tests for the ADR-052 WorldActuator (the sync world-actuation HTTP client).

The agent execute() tests use a FakeActuator, so the real WorldActuator transport path
(httpx) was otherwise uncovered. These cover its three outcomes — success, a2a-level
error, and transport failure — by patching httpx.Client (no real server)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from synapse_common.world.actuator import WorldActuator
from synapse_common.world.models import WorldAction, WorldActionKind

if TYPE_CHECKING:
    import pytest


def _action() -> WorldAction:
    return WorldAction(
        action_id="a1",
        kind=WorldActionKind.REORDER,
        city="bengaluru",
        sku_id="sku_0",
        params={"quantity": 10.0},
        decision_id="d1",
    )


class _Resp:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._body


def _patch_client(
    monkeypatch: pytest.MonkeyPatch, *, body: dict[str, Any] | None, boom: bool
) -> None:
    import httpx

    class _Client:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *a: Any) -> bool:
            return False

        def post(self, url: str, json: dict[str, Any] | None = None) -> _Resp:
            if boom:
                raise RuntimeError("connection refused")
            assert body is not None
            return _Resp(body)

    monkeypatch.setattr(httpx, "Client", _Client)


def test_apply_success_returns_real_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        body={"result": {"status": "applied", "effect": {"new_level": 510.0}}},
        boom=False,
    )
    res = WorldActuator(twin_url="http://digital-twin:8009/").apply(
        _action()
    )  # trailing slash stripped
    assert res["applied"] is True
    assert res["result"]["effect"]["new_level"] == 510.0


def test_apply_a2a_error_is_not_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch, body={"error": {"code": -32004, "message": "no standing world"}}, boom=False
    )
    res = WorldActuator(twin_url="http://digital-twin:8009").apply(_action())
    assert res["applied"] is False
    assert res["error"]["code"] == -32004


def test_apply_transport_failure_degrades_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, body=None, boom=True)
    res = WorldActuator(twin_url="http://digital-twin:8009").apply(_action())
    assert res["applied"] is False  # never raises (I-7)
    assert "error" in res
