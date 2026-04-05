"""
SYNAPSE A2A SDK — Agent-to-Agent communication via JSON-RPC 2.0 (I-9).
A2A Protocol (Google, Linux Foundation) for inter-agent communication.
MCP (Anthropic) for agent-to-tool communication. NEVER conflate.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

import httpx

from synapse_common.models import SynapseBaseModel

logger = logging.getLogger(__name__)

JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}


class A2ARequest(SynapseBaseModel):
    """JSON-RPC 2.0 request for A2A protocol."""
    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] = {}
    id: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            object.__setattr__(self, "id", str(uuid4()))


class A2AResponse(SynapseBaseModel):
    """JSON-RPC 2.0 response for A2A protocol."""
    jsonrpc: str = "2.0"
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    id: str


class AgentCard(SynapseBaseModel):
    """A2A Agent Card — capability declaration per agent."""
    name: str
    description: str
    version: str
    url: str
    capabilities: list[str]
    supported_methods: list[str]


async def send_a2a_request(
    target_url: str,
    method: str,
    params: dict[str, Any],
    timeout: float = 5.0,
) -> A2AResponse:
    """Send A2A JSON-RPC request to another agent."""
    request = A2ARequest(method=method, params=params)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{target_url}/a2a",
            content=json.dumps(
                request.model_dump(mode="json"), **JSON_KWARGS
            ),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return A2AResponse.model_validate(response.json())
