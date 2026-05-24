"""Tests for A2A SDK — JSON-RPC 2.0 agent communication (I-9)."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from synapse_common import clients
from synapse_common.a2a_sdk import (
    A2ARequest,
    A2AResponse,
    AgentCard,
    send_a2a_request,
)
from synapse_common.breakers import reset_registry as reset_breakers


@pytest.fixture(autouse=True)
def _reset_singletons() -> Any:
    """Sprint-7: shared httpx + breaker singletons leak across tests.

    The Sprint-7 SDK uses ``synapse_common.clients.get_client('a2a')``
    (process-shared) and a per-host circuit breaker. Reset both so each
    test sees a fresh state and ``httpx.AsyncClient`` monkey-patches
    take effect.
    """
    clients._REGISTRY.clear()  # type: ignore[attr-defined]
    reset_breakers()
    yield
    clients._REGISTRY.clear()  # type: ignore[attr-defined]
    reset_breakers()


class TestA2ARequest:

    def test_auto_generates_id(self) -> None:
        req = A2ARequest(method="propose", params={"value": 1})
        assert req.id != ""
        assert req.jsonrpc == "2.0"

    def test_explicit_id_preserved(self) -> None:
        req = A2ARequest(method="propose", params={}, id="custom-123")
        assert req.id == "custom-123"

    def test_default_params_empty(self) -> None:
        req = A2ARequest(method="ping")
        assert req.params == {}

    def test_frozen(self) -> None:
        req = A2ARequest(method="ping")
        with pytest.raises(Exception):
            req.method = "other"  # type: ignore[misc]


class TestA2AResponse:

    def test_result_response(self) -> None:
        resp = A2AResponse(id="abc", result={"ok": True})
        assert resp.result == {"ok": True}
        assert resp.error is None

    def test_error_response(self) -> None:
        resp = A2AResponse(id="abc", error={"code": -32600, "message": "Invalid"})
        assert resp.error is not None
        assert resp.result is None


class TestAgentCard:

    def test_construction(self) -> None:
        card = AgentCard(
            name="demand_prophet",
            description="Forecasts demand",
            version="0.1.0",
            url="http://localhost:8001",
            capabilities=["forecast"],
            supported_methods=["propose", "debate_respond"],
        )
        assert card.name == "demand_prophet"
        assert len(card.supported_methods) == 2


_RealAsyncClient = httpx.AsyncClient


class TestSendA2ARequest:

    @pytest.mark.asyncio
    async def test_send_request_success(self) -> None:
        response_body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "result": {"status": "accepted"},
            "id": "will-be-overwritten",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            response_body["id"] = body["id"]
            assert request.url.path == "/a2a"
            assert request.headers["content-type"] == "application/json"
            assert body["method"] == "propose"
            return httpx.Response(200, json=response_body)

        transport = httpx.MockTransport(handler)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                httpx,
                "AsyncClient",
                lambda **kw: _RealAsyncClient(transport=transport, **kw),
            )
            resp = await send_a2a_request(
                target_url="http://agent-a:8000",
                method="propose",
                params={"price": 42.0},
            )

        assert isinstance(resp, A2AResponse)
        assert resp.result == {"status": "accepted"}

    @pytest.mark.asyncio
    async def test_send_request_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        transport = httpx.MockTransport(handler)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                httpx,
                "AsyncClient",
                lambda **kw: _RealAsyncClient(transport=transport, **kw),
            )
            with pytest.raises(httpx.HTTPStatusError):
                await send_a2a_request(
                    target_url="http://agent-a:8000",
                    method="propose",
                    params={},
                )
