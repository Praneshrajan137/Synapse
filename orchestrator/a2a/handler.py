"""
SYNAPSE Orchestrator — A2A JSON-RPC handler (I-9).

Exposes three standard methods:
  1. proposal(decision_context) -> consensus decision
  2. debate_respond(proposals, round_number) -> revised context
  3. execute(consensus_action) -> execution confirmation
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import structlog

from orchestrator.state_machine import OrchestratorStateMachine

logger = structlog.get_logger(__name__)

_JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}


class OrchestratorA2AHandler:
    """A2A handler for the Orchestrator meta-agent.  JSON-RPC 2.0 protocol."""

    def __init__(self, consensus_protocol: Any = None) -> None:
        self._protocol = consensus_protocol
        self._fsm = OrchestratorStateMachine()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a JSON-RPC request to the appropriate method."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id", str(uuid4()))

        try:
            if method == "proposal":
                result = self.proposal(params)
            elif method == "debate_respond":
                result = self.debate_respond(params)
            elif method == "execute":
                result = self.execute(params)
            else:
                return self._error_response(request_id, -32601, f"Method not found: {method}")

            return {"jsonrpc": "2.0", "result": result, "id": request_id}
        except Exception as exc:
            logger.error("a2a_handler_error", method=method, error=str(exc))
            return self._error_response(request_id, -32000, str(exc))

    def proposal(self, decision_context: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("decision_request_received")
        self._fsm.record_tool_call()
        return {
            "status": "consensus_initiated",
            "decision_context": decision_context,
        }

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        round_number = params.get("round_number", 1)
        logger.info("debate_respond", round=round_number)
        self._fsm.record_tool_call()
        return {"status": "debate_round_complete", "round": round_number}

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("execution_complete")
        self._fsm.record_tool_call()
        return {
            "status": "executed",
            "decision_id": consensus_action.get("decision_id", str(uuid4())),
        }

    @staticmethod
    def _error_response(request_id: str, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        }
