"""SYNAPSE Orchestrator — KV-cache preservation tests (I-13)."""

from __future__ import annotations

from synapse_common.models import ContextMessage

from orchestrator.llm.context_builder import SYSTEM_PROMPT, ContextBuilder


class TestPrefixStability:
    """INV-ORC-005: System prompt must be byte-identical across invocations."""

    def test_verify_prefix_stability(self) -> None:
        builder = ContextBuilder()
        assert builder.verify_prefix_stability() is True

    def test_system_prompt_is_constant(self) -> None:
        a = ContextBuilder()
        b = ContextBuilder()
        assert a._system_prompt_hash == b._system_prompt_hash

    def test_system_prompt_no_timestamp(self) -> None:
        assert "2026" not in SYSTEM_PROMPT
        assert "timestamp" not in SYSTEM_PROMPT.lower()


class TestMessageBuilding:
    def test_first_message_is_system(self) -> None:
        builder = ContextBuilder()
        messages = builder.build_ollama_messages([])
        assert len(messages) == 1
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SYSTEM_PROMPT

    def test_context_messages_appended_in_order(self) -> None:
        builder = ContextBuilder()
        ctx = [
            ContextMessage(source="agent_a", content={"step": 1}),
            ContextMessage(source="orchestrator", content={"step": 2}),
            ContextMessage(source="agent_b", content={"step": 3}),
        ]
        messages = builder.build_ollama_messages(ctx)
        assert len(messages) == 4
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"

    def test_deterministic_serialization(self) -> None:
        builder = ContextBuilder()
        ctx = [ContextMessage(source="agent_a", content={"b": 2, "a": 1})]
        messages = builder.build_ollama_messages(ctx)
        content = messages[1]["content"]
        # sort_keys must produce {"a":1,"b":2}
        assert '"a":1' in content
        assert '"b":2' in content
        assert content.index('"a"') < content.index('"b"')
