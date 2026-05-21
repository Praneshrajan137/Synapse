"""KV-cache stability test (WS-2 §6, ADR-026 sibling fix).

Regression guard for the
[orchestrator/llm/context_builder.py:73](orchestrator/llm/context_builder.py:73)
fix: flipping a message's ``status`` between ``ACTIVE`` /
``SUPERSEDED`` / ``REJECTED`` must NOT alter the LLM-prompt byte stream.
Status is now emitted on a parallel metadata channel; the prompt body
remains stable.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from synapse_common.models import ContextMessage, MessageStatus

from orchestrator.llm.context_builder import ContextBuilder


def _hash(messages: list[dict[str, str]]) -> str:
    payload = json.dumps(messages, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@pytest.mark.integration
def test_status_flip_does_not_change_prompt_hash() -> None:
    builder = ContextBuilder()
    msg = ContextMessage(
        source="demand_prophet",
        content={"forecast": [1, 2, 3]},
        status=MessageStatus.ACTIVE,
    )
    pending_messages = builder.build_ollama_messages([msg])
    pending_hash = _hash(pending_messages)

    # Flip the status — same logical message lifecycle event, must NOT
    # invalidate the prompt body.
    msg_completed = msg.model_copy(update={"status": MessageStatus.SUPERSEDED})
    completed_messages = builder.build_ollama_messages([msg_completed])
    completed_hash = _hash(completed_messages)

    assert pending_hash == completed_hash, (
        "KV-cache invariant violated: msg.status leaked into the prompt body."
    )


@pytest.mark.integration
def test_metadata_channel_carries_status() -> None:
    builder = ContextBuilder()
    msg = ContextMessage(
        source="orchestrator",
        content={"action": "reorder"},
        status=MessageStatus.REJECTED,
        rejection_reason="below confidence threshold",
    )
    metadata = builder.build_metadata_channel([msg])
    assert metadata[0]["status"] == MessageStatus.REJECTED.value
    assert metadata[0]["rejection_reason"] == "below confidence threshold"
    assert metadata[0]["source"] == "orchestrator"


@pytest.mark.integration
def test_system_prompt_prefix_hash_stable() -> None:
    builder = ContextBuilder()
    assert builder.verify_prefix_stability()
